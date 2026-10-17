"""Least-privilege access recommendation on CERT r4.2 / r5.2.

Question: does a collaborative-filtering recommender (implicit ALS, item-item CF) predict
which computers / websites each employee will legitimately need, better than simple rules
(own history, team, role, popularity, ownership), so that granting "own history + top-K
recommendations" causes fewer approval requests for normal users while still forcing
approval for the insiders' malicious accesses?

Read-only inputs: data/cache/r*/{pc_pairs,dom_pairs} (Spark ETL), raw LDAP snapshots,
answers/insiders.csv and the per-insider malicious event files. Everything is written under
OUT (this script's folder /out).
"""
import glob, json, re, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

BASE = Path("/Users/mehrad/Documents/School/UTD/UTD_as_student/Fall2026/IBM_Z_Datathon_2026")
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
ANS = BASE / "data/answers/answers"
REL = {
    "4.2": dict(cut="2010-06-01", val_cut="2010-05-01", raw=BASE / "data/r4.2/r4.2", work=BASE / "data/cache/r4.2"),
    "5.2": dict(cut="2010-04-01", val_cut="2010-03-01", raw=BASE / "data/r5.2/r5.2", work=BASE / "data/cache/r5.2"),
}
DOM_RE = re.compile(r"^https?://(?:www\.)?([^/:]+)")  # identical to the Spark ETL extraction
K_GRID = {"pc": [1, 2, 3, 5, 10, 20, 50], "dom": [5, 10, 20, 50, 100]}
VAL_K = {"pc": 3, "dom": 20}
SEED = 7


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ----------------------------------------------------------------------------- loading
def load_ldap(cfg):
    files = sorted(glob.glob(str(cfg["raw"] / "LDAP" / "*.csv")))
    before = [f for f in files if Path(f).stem < cfg["cut"][:7]]
    snap = pd.read_csv(before[-1])  # latest snapshot strictly before the cut month
    rest = pd.concat([pd.read_csv(f) for f in files])  # fallback for anyone missing there
    ld = pd.concat([snap, rest]).drop_duplicates("user_id")
    for c in ["business_unit", "functional_unit", "department", "team"]:
        ld[c] = ld[c].astype(str)
    ld["team_key"] = ld.business_unit + "|" + ld.functional_unit + "|" + ld.department + "|" + ld.team
    ld["dept_key"] = ld.business_unit + "|" + ld.functional_unit + "|" + ld.department
    return ld.set_index("user_id")


def load_malicious(ds, insiders):
    """Malicious events by the insider him/herself (answer files also contain other users' lines)."""
    rows = []
    for _, r in insiders.iterrows():
        f = ANS / f"r{ds}-{r.scenario}" / r.details
        for line in open(f, errors="replace"):
            p = line.rstrip("\n").split(",", 6)
            if len(p) < 6 or p[3] != r.user:
                continue
            typ, date, user, pc = p[0], p[2], p[3], p[4]
            dom = None
            if typ == "http":
                m = DOM_RE.match(p[5]); dom = m.group(1).lower() if m else None
            act = p[5] if typ == "logon" else None
            if typ == "email":  # r5.2 email rows carry Send/Receive/View in field 9; r4.2 has none
                f = line.split(",")
                act = f[9] if len(f) > 9 and f[9] in ("Send", "Receive", "View") else None
            rows.append((r.scenario, user, typ, act, pd.to_datetime(date, format="%m/%d/%Y %H:%M:%S"), pc, dom))
    return pd.DataFrame(rows, columns=["scenario", "user", "type", "act", "ts", "pc", "domain"])


class Release:
    pass


def load(ds):
    cfg = REL[ds]; R = Release(); R.ds, R.cfg = ds, cfg
    t = time.time()
    pc = pd.read_parquet(cfg["work"] / "pc_pairs"); pc["day"] = pc.day.astype(str); pc["n"] = 1
    dom = pd.read_parquet(cfg["work"] / "dom_pairs"); dom["day"] = dom.day.astype(str)
    pc = pc.rename(columns={"pc": "item"}); dom = dom.rename(columns={"domain": "item"})
    ins = pd.read_csv(ANS / "insiders.csv", dtype=str)
    ins = ins[ins.dataset == ds].copy(); ins["scenario"] = ins.scenario.astype(int)
    R.insiders = ins
    R.mal = load_malicious(ds, ins)
    R.ldap = load_ldap(cfg)
    users = sorted(set(pc.user) | set(dom.user))
    R.users = np.array(users); R.uidx = {u: i for i, u in enumerate(users)}
    R.nu = len(users)
    R.is_insider = np.isin(R.users, ins.user.values)
    R.scen_of = dict(zip(ins.user, ins.scenario))
    ld = R.ldap.reindex(R.users)
    R.role = ld.role.fillna("?").values
    R.team = ld.team_key.fillna("?").values
    R.dept = ld.dept_key.fillna("?").values
    R.is_admin = R.role == "ITAdmin"
    R.normal = ~R.is_insider
    R.res = {}
    for name, df, malcol in (("pc", pc, "pc"), ("dom", dom, "domain")):
        mal_items = set(R.mal[malcol].dropna())
        items = sorted(set(df.item) | mal_items)
        iidx = {v: i for i, v in enumerate(items)}
        df = df.assign(u=df.user.map(R.uidx).astype(int), i=df.item.map(iidx).astype(int))
        R.res[name] = dict(df=df, items=np.array(items), iidx=iidx, ni=len(items))
    log(f"r{ds}: loaded users={R.nu} insiders={len(ins)} mal_events={len(R.mal)} in {time.time()-t:.0f}s")
    return R


def usage_matrix(df, nu, ni):
    """users x items, value = number of distinct days the user touched the item."""
    g = df.groupby(["u", "i"]).size()
    u = g.index.get_level_values(0).values; i = g.index.get_level_values(1).values
    return sp.csr_matrix((g.values.astype(float), (u, i)), shape=(nu, ni))


# ----------------------------------------------------------------------------- models
def als_implicit(X, rank, alpha, reg, iters=12, seed=SEED):
    """Hu-Koren-Volinsky implicit ALS. X = users x items with values log1p(days); c = 1 + alpha*x."""
    C = X.tocsr().copy(); C.data = alpha * C.data
    Ct = C.T.tocsr()
    rng = np.random.default_rng(seed)
    U = rng.normal(0, 0.01, (C.shape[0], rank)); V = rng.normal(0, 0.01, (C.shape[1], rank))
    I = reg * np.eye(rank)

    def side(C, Y):
        YtY = Y.T @ Y; out = np.zeros((C.shape[0], rank))
        for r in range(C.shape[0]):
            s, e = C.indptr[r], C.indptr[r + 1]
            if s == e:
                continue
            idx = C.indices[s:e]; c1 = C.data[s:e]; Yr = Y[idx]
            out[r] = np.linalg.solve(YtY + (Yr.T * c1) @ Yr + I, Yr.T @ (1.0 + c1))
        return out

    for _ in range(iters):
        U = side(C, V); V = side(Ct, U)
    return U @ V.T


def itemknn(X, weighted):
    """item-item cosine CF: score(u,i) = sum_j x_uj * cos(i,j)."""
    B = X.copy()
    if not weighted:
        B.data[:] = 1.0
    norms = np.sqrt(np.asarray(B.multiply(B).sum(0))).ravel() + 1e-9
    Bn = B.multiply(1.0 / norms).tocsc()
    S = (Bn.T @ Bn).toarray(); np.fill_diagonal(S, 0.0)
    return np.asarray(B @ S)


def rank_matrix(score, own, known):
    """rank of each item among the user's NON-own, train-known items (0 = best). Others -> big."""
    s = score.astype(float).copy()
    s[own] = -np.inf; s[:, ~known] = -np.inf
    order = np.argsort(-s, axis=1, kind="stable")
    R = np.empty_like(order); rows = np.arange(s.shape[0])[:, None]
    R[rows, order] = np.arange(s.shape[1])[None, :]
    R[~np.isfinite(s)] = 10**9
    return R


def recall_new(rank, pairs_u, pairs_i, K):
    """share of new (user,item) pairs that land in the user's top-K."""
    if len(pairs_u) == 0:
        return np.nan
    return float((rank[pairs_u, pairs_i] < K).mean())


def new_pairs(df_before, df_after, users_mask):
    seen = set(zip(df_before.u, df_before.i))
    p = df_after[["u", "i"]].drop_duplicates()
    keep = np.array([(u, i) not in seen for u, i in zip(p.u, p.i)], dtype=bool) & users_mask[p.u.values]
    return p.u.values[keep], p.i.values[keep]


def tune(R, name):
    """choose ALS / item-kNN hyper-parameters on a validation month INSIDE the train window."""
    res = R.res[name]; df = res["df"]; cfg = R.cfg
    a = df[df.day < cfg["val_cut"]]; b = df[(df.day >= cfg["val_cut"]) & (df.day < cfg["cut"])]
    X = usage_matrix(a, R.nu, res["ni"]); Xl = X.copy(); Xl.data = np.log1p(Xl.data)
    own = X.toarray() > 0; known = np.asarray(X.sum(0)).ravel() > 0
    mask = ~R.is_admin  # admins log into hundreds of PCs; score on the ordinary population
    vu, vi = new_pairs(a, b, mask)
    K = VAL_K[name]; rows = []
    grid = {"pc": dict(rank=(4, 8, 16, 32), alpha=(0.5, 2.0, 10.0), reg=(0.1, 1.0)),
            "dom": dict(rank=(32, 64, 128, 256), alpha=(0.5, 1.0, 2.0, 10.0), reg=(0.1, 1.0))}[name]
    for rank in grid["rank"]:
        for alpha in grid["alpha"]:
            for reg in grid["reg"]:
                S = als_implicit(Xl, rank, alpha, reg)
                rows.append(dict(model="als", rank=rank, alpha=alpha, reg=reg,
                                 recall=recall_new(rank_matrix(S, own, known), vu, vi, K)))
    for w in (False, True):
        S = itemknn(Xl, w)
        rows.append(dict(model="iknn", weighted=w, recall=recall_new(rank_matrix(S, own, known), vu, vi, K)))
    pop = np.asarray((X > 0).sum(0)).ravel().astype(float)
    rows.append(dict(model="pop", recall=recall_new(rank_matrix(np.tile(pop, (R.nu, 1)), own, known), vu, vi, K)))
    t = pd.DataFrame(rows); t["release"] = R.ds; t["resource"] = name; t["val_new_pairs"] = len(vu); t["K"] = K
    return t


# ----------------------------------------------------------------------------- policies
def build_policies(R, name, als_cfg, iknn_w):
    res = R.res[name]; df = res["df"]; cut = R.cfg["cut"]; ni = res["ni"]
    tr = df[df.day < cut]
    X = usage_matrix(tr, R.nu, ni); Xl = X.copy(); Xl.data = np.log1p(Xl.data)
    own = X.toarray() > 0
    known = own.any(0)
    nusers_item = own.sum(0).astype(float)
    pol, ranks = {}, {}
    pol["Own history"] = own.copy()

    def group_union(keys):
        codes, uniq = pd.factorize(keys)
        G = sp.csr_matrix((np.ones(R.nu), (np.arange(R.nu), codes)), shape=(R.nu, len(uniq)))
        cnt = (G.T @ sp.csr_matrix(own.astype(float))).toarray()  # groups x items: #members using item
        return cnt[codes] - own  # teammates other than me

    team_cnt = group_union(R.team)
    pol["Team (all teammates' items)"] = own | (team_cnt > 0)
    pol["Department"] = own | (group_union(R.dept) > 0)
    pol["Role (same job title)"] = own | (group_union(R.role) > 0)
    pol["Org-wide (anything anyone used)"] = own | known[None, :]
    if name == "pc":
        # ownership: a PC is personal if one user holds >=80% of its training login-days
        Xd = X.toarray()
        tot = Xd.sum(0); top_u = Xd.argmax(0); share = np.where(tot > 0, Xd.max(0) / np.maximum(tot, 1), 0)
        personal = (share >= 0.8) & known
        R.res[name]["personal"] = personal; R.res[name]["owner"] = np.where(personal, top_u, -1)
        shared = known & ~personal
        pol["Ownership-aware (own + shared PCs)"] = own | shared[None, :]
        others_personal = personal[None, :] & (R.res[name]["owner"][None, :] != np.arange(R.nu)[:, None])
        pol["Team, ownership-filtered"] = own | ((team_cnt > 0) & ~others_personal)
        R.res[name]["others_personal"] = others_personal
    # ranked expansions
    pop = np.tile(nusers_item, (R.nu, 1))
    ranks["Popularity top-K"] = rank_matrix(pop, own, known)
    ranks["Team-ranked top-K"] = rank_matrix(team_cnt + 0.5 * nusers_item / (nusers_item.max() + 1), own, known)
    t = time.time()
    ranks["ALS top-K"] = rank_matrix(als_implicit(Xl, **als_cfg), own, known)
    ranks["Item-item CF top-K"] = rank_matrix(itemknn(Xl, iknn_w), own, known)
    log(f"  r{R.ds} {name}: CF models fit in {time.time()-t:.0f}s")
    if name == "pc":
        op = R.res[name]["others_personal"]
        for k in ("ALS top-K", "Popularity top-K"):
            s = np.where(ranks[k] < 10**9, -ranks[k].astype(float), -np.inf); s[op] = -np.inf
            ranks[k + ", ownership-filtered"] = rank_matrix(s, own, known)
    return pol, ranks, own, known


# ----------------------------------------------------------------------------- evaluation
def evaluate(R, name, A, own):
    res = R.res[name]; df = res["df"]; cut = R.cfg["cut"]
    te = df[df.day >= cut]
    out = {}
    for grp, m in (("normal", R.normal), ("normal_nonadmin", R.normal & ~R.is_admin), ("normal_admin", R.normal & R.is_admin)):
        e = te[m[te.u.values]]
        blocked = ~A[e.u.values, e.i.values]
        out[f"{grp}_event_disr"] = blocked.mean()            # share of access-days needing approval
        if name == "dom":
            out[f"{grp}_visit_disr"] = (e.n.values * blocked).sum() / e.n.sum()
        p = e[["u", "i"]].drop_duplicates()
        pb = ~A[p.u.values, p.i.values]
        out[f"{grp}_pair_disr"] = pb.mean()                   # share of distinct (user,item) needing approval
        nusers = m.sum(); months = (pd.Timestamp(te.day.max()) - pd.Timestamp(cut)).days / 30.44
        out[f"{grp}_requests_per_user_month"] = pb.sum() / nusers / months
        isnew = ~own[p.u.values, p.i.values]
        out[f"{grp}_new_recall"] = (A[p.u.values, p.i.values] & isnew).sum() / max(isnew.sum(), 1)
        exp = (A & ~own)[m]
        out[f"{grp}_grant_mean"] = exp.sum(1).mean()           # extra items granted beyond own history
        used = np.zeros_like(A); used[p.u.values, p.i.values] = True
        out[f"{grp}_grant_used_share"] = (exp & used[m]).sum() / max(exp.sum(), 1)  # precision of the grant
        # hit rate: users with >=1 new item who got >=1 of them granted
        pn = p[isnew]; hit = A[pn.u.values, pn.i.values]
        hu = pd.Series(hit).groupby(pn.u.values).any()
        out[f"{grp}_user_hit_rate"] = hu.mean() if len(hu) else np.nan
    # prevention
    mal = R.mal
    col = "pc" if name == "pc" else "domain"
    sets = {"pc": [("logon", (mal.type == "logon") & (mal.act == "Logon")),
                   ("any_on_pc", ~((mal.type == "email") & (mal.act == "Receive")))],
            "dom": [("http", mal.type == "http")]}[name]
    for lab, msk in sets:
        mm = mal[msk & mal[col].notna()]
        u = mm.user.map(R.uidx).values; i = mm[col].map(res["iidx"]).values
        b = ~A[u, i]
        out[f"prev_{lab}_all"] = b.mean() if len(b) else np.nan
        out[f"prev_{lab}_n"] = len(b)
        for s in sorted(R.insiders.scenario.unique()):
            sm = (mm.scenario == s).values
            out[f"prev_{lab}_s{s}"] = b[sm].mean() if sm.sum() else np.nan
            out[f"prev_{lab}_s{s}_n"] = int(sm.sum())
            # insiders with at least one malicious event of this kind forced to approval
            if sm.sum():
                out[f"prev_{lab}_s{s}_users"] = pd.Series(b[sm]).groupby(mm.user.values[sm]).any().mean()
    return out


def run(ds, tunings):
    R = load(ds)
    rows, curves = [], []
    for name in ("pc", "dom"):
        tb = tunings[(tunings.release == ds) & (tunings.resource == name)]
        best = tb[tb.model == "als"].sort_values("recall", ascending=False).iloc[0]
        als_cfg = dict(rank=int(best["rank"]), alpha=float(best.alpha), reg=float(best.reg))
        bk = tb[tb.model == "iknn"].sort_values("recall", ascending=False).iloc[0]
        log(f"  r{ds} {name}: ALS {als_cfg} (val recall {best.recall:.3f}); iknn weighted={bk.weighted}")
        pol, ranks, own, known = build_policies(R, name, als_cfg, bool(bk.weighted))
        for p, A in pol.items():
            rows.append(dict(release=ds, resource=name, policy=p, K=np.nan, **evaluate(R, name, A, own)))
        for p, rk in ranks.items():
            for K in K_GRID[name]:
                A = own | (rk < K)
                curves.append(dict(release=ds, resource=name, policy=p, K=K, **evaluate(R, name, A, own)))
        # least-privilege (revocation) suggestions: training accesses never used again in test,
        # among normal users still active in the final 30 days of data
        df = R.res[name]["df"]; te = df[df.day >= R.cfg["cut"]]
        last = pd.Timestamp(df.day.max()) - pd.Timedelta(days=30)
        active = np.zeros(R.nu, bool); active[te[pd.to_datetime(te.day) >= last].u.unique()] = True
        m = active & R.normal
        used = np.zeros_like(own); used[te.u.values, te.i.values] = True
        R.res[name]["stale"] = {}
        for grp, mm in (("normal", m), ("normal_nonadmin", m & ~R.is_admin)):
            stale = (own & ~used)[mm].sum(1); held = own[mm].sum(1)
            R.res[name]["stale"][grp] = dict(users=int(mm.sum()), mean_held=float(held.mean()), mean_stale=float(stale.mean()),
                                             share_stale=float(stale.sum() / held.sum()),
                                             users_with_any_stale=float((stale > 0).mean()))
    stale = {n: R.res[n]["stale"] for n in ("pc", "dom")}
    # context: how much of the malicious activity is on resources already in the insider's own history
    ctx = {}
    for name, col, msk in (("pc", "pc", (R.mal.type == "logon") & (R.mal.act == "Logon")), ("dom", "domain", R.mal.type == "http")):
        res = R.res[name]; df = res["df"]; tr = df[df.day < R.cfg["cut"]]
        mm = R.mal[msk & R.mal[col].notna()]
        seen = set(zip(tr.u, tr.i)); u = mm.user.map(R.uidx).values; i = mm[col].map(res["iidx"]).values
        ins_own = np.array([(a, b) in seen for a, b in zip(u, i)])
        known_items = set(tr.i)
        normal_users_item = tr[R.normal[tr.u.values]].groupby("i").u.nunique()
        ctx[name] = {}
        for s in sorted(mm.scenario.unique()):
            sm = (mm.scenario == s).values
            ii = i[sm]
            ctx[name][f"s{s}"] = dict(n=int(sm.sum()), in_own_history=float(ins_own[sm].mean()),
                                      item_unseen_in_train=float(np.mean([x not in known_items for x in ii])),
                                      median_normal_users_of_item_in_train=float(np.median([normal_users_item.get(x, 0) for x in ii])),
                                      distinct_items=int(len(set(ii))))
        if name == "pc":
            own_pc = res["owner"]; personal = res["personal"]
            ctx[name]["mal_logon_to_others_personal"] = float(np.mean([personal[b] and own_pc[b] != a for a, b in zip(u, i)]))
    return rows, curves, stale, ctx


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    tpath = OUT / "tuning.csv"
    if stage in ("tune", "all") or not tpath.exists():
        ts = []
        for ds in REL:
            R = load(ds)
            for name in ("pc", "dom"):
                t = time.time(); ts.append(tune(R, name)); log(f"tuned r{ds} {name} in {time.time()-t:.0f}s")
        pd.concat(ts).to_csv(tpath, index=False)
    tunings = pd.read_csv(tpath, dtype={"release": str})
    if stage in ("eval", "all"):
        allr, allc, meta = [], [], {}
        for ds in REL:
            r, c, stale, ctx = run(ds, tunings)
            allr += r; allc += c; meta[ds] = dict(stale=stale, malicious_context=ctx)
        pd.DataFrame(allr).to_csv(OUT / "policies.csv", index=False)
        pd.DataFrame(allc).to_csv(OUT / "curves.csv", index=False)
        json.dump(meta, open(OUT / "meta.json", "w"), indent=1, default=float)
        log("done")
