"""Online (day-by-day) early-warning replay on CERT r4.2 / r5.2. Protocol: ../early/prereg.txt (frozen before results).

Usage:  python3.11 online_replay.py r4.2      (development)
        python3.11 online_replay.py r5.2      (confirmation, same code, no changes)
Reads only the local parquet caches and the answer key; writes only to ./results next to this script.
"""
import sys, time, resource
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.stats import norm, binom

import pathlib; BASE = pathlib.Path(__file__).resolve().parents[2]
WORK, ANS = BASE / "data" / "cache", BASE / "data" / "answers" / "answers"
OUT = Path(__file__).resolve().parent / "results"; OUT.mkdir(exist_ok=True)
CUT = {"r4.2": "2010-06-01", "r5.2": "2010-04-01"}
F9 = ["n_logon", "n_logon_ah", "n_usb", "n_usb_ah", "n_file", "n_file_ah", "n_http", "n_http_ah", "n_pcs"]
FEATS = ["n_logon_ah", "n_usb", "n_usb_ah", "n_file", "n_file_ah", "n_http_ah", "n_pcs"]   # R1 daily z
WF = ["n_usb", "n_file", "n_logon_ah", "n_usb_ah", "n_http_ah"]                            # R2 window
HALF, KS, SEED, NSHUF, POOL = 7, (20, 50), 7, 500, 7
LAM = 0.5 ** (1 / HALF)
METHODS = ["a_R2", "b_PCT", "c_FUSE_MAX", "c2_FUSE_STOUF"]
RULES = ["decay7", "maxsofar", "today"]
T0 = time.time()
log = lambda *a: print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def roll(X, w):
    """trailing w-day sum along the last axis (calendar days), using only days <= t"""
    cs = np.concatenate([np.zeros(X.shape[:-1] + (1,), X.dtype), np.cumsum(X, axis=-1)], axis=-1)
    hi = np.arange(1, X.shape[-1] + 1); lo = np.maximum(0, hi - w)
    return cs[..., hi] - cs[..., lo]


def load(rel):
    cut = pd.Timestamp(CUT[rel]); tr_end = cut - pd.Timedelta(days=cut.weekday())   # drop the cutoff week from training
    d = pd.read_parquet(WORK / rel / "daily"); d["day"] = pd.to_datetime(d["day"])
    users = np.array(sorted(d.user.unique())); uix = pd.Index(users)
    day0 = d.day.min(); nd = (d.day.max() - day0).days + 1
    ui, di = uix.get_indexer(d.user), (d.day - day0).dt.days.values
    G = np.zeros((len(F9), len(users), nd), np.float64)
    for k, f in enumerate(F9):
        G[k, ui, di] = d[f].values
    act = np.zeros((len(users), nd), bool); act[ui, di] = True
    c = dict(rel=rel, cut=cut, tr_end=tr_end, users=users, uix=uix, day0=day0, nd=nd, G=G, act=act,
             t_tr=(tr_end - day0).days, t_cut=(cut - day0).days)
    log(f"{rel}: staff {len(users)}, days {nd} ({day0.date()}..{d.day.max().date()}), train days < {tr_end.date()} "
        f"(idx {c['t_tr']}), test from {cut.date()} (idx {c['t_cut']}), test days {nd - c['t_cut']}")
    return c


def labels(c):
    ins = pd.read_csv(ANS / "insiders.csv"); ins = ins[ins.dataset.astype(str) == c["rel"][1:]].copy()
    ins["F"] = pd.to_datetime(ins.start).dt.normalize(); ins["L"] = pd.to_datetime(ins.end).dt.normalize()
    ins["i"] = c["uix"].get_indexer(ins.user)
    assert (ins.i >= 0).all() and (ins.F >= c["cut"]).all(), "insider missing or attack before cutoff"
    ins["Ft"] = (ins.F - c["day0"]).dt.days - c["t_cut"]; ins["Lt"] = (ins.L - c["day0"]).dt.days - c["t_cut"]
    return ins.reset_index(drop=True)


# ---------------------------------------------------------------- daily evidence (all causal)
def ev_R2(c):
    G, act, t_tr, t0 = c["G"], c["act"], c["t_tr"], c["t_cut"]
    ntr = act[:, :t_tr].sum(1).clip(min=1)
    idx = [F9.index(f) for f in WF]
    rate = G[idx][:, :, :t_tr].sum(-1) / ntr                          # (5, N) per active training day
    R = roll(G[idx], 28)[:, :, t0:]; nact = roll(act.astype(float), 28)[:, t0:]
    exp = rate[:, :, None] * nact[None]
    return np.clip((R - exp) / np.sqrt(exp + 1), 0, None).sum(0)


def ev_PCT(c):
    G, act, t_tr, t0 = c["G"], c["act"], c["t_tr"], c["t_cut"]
    wd0 = c["day0"].weekday(); wk = (np.arange(c["nd"]) + wd0) // 7    # Mon-Sun week id per day
    nw = wk.max() + 1
    W = np.zeros((len(F9), G.shape[1], nw)); A = np.zeros((G.shape[1], nw))
    for w in range(nw):
        m = wk == w; W[:, :, w] = G[:, :, m].sum(-1); A[:, w] = act[:, m].sum(-1)
    wend = np.array([np.where(wk == w)[0].max() for w in range(nw)])
    trw = wend < t_tr                                                  # weeks fully inside training
    S7 = roll(G, 7)[:, :, t0:]                                         # (9, N, T) trailing 7-day totals
    T = S7.shape[-1]; P = np.zeros((G.shape[1], T, len(F9)))
    for u in range(G.shape[1]):
        ref = W[:, u, trw & (A[u] > 0)].T                              # (nref, 9)
        if len(ref) == 0:
            continue
        x = S7[:, u, :].T[:, None, :]                                  # (T, 1, 9)
        P[u] = ((ref[None] < x).sum(1) + 0.5 * (ref[None] == x).sum(1)) / len(ref)
    return (P >= 0.99).sum(-1) + 0.01 * P.sum(-1)


def ev_Z(c):
    G, act, t_tr, t0 = c["G"], c["act"], c["t_tr"], c["t_cut"]
    idx = [F9.index(f) for f in FEATS]
    X = G[idx][:, :, :t_tr]; m = act[:, :t_tr][None]; n = m.sum(-1).clip(min=1)
    mu = (X * m).sum(-1) / n
    sd = np.sqrt((((X - mu[..., None]) ** 2) * m).sum(-1) / (n - 1).clip(min=1))
    return np.clip((G[idx][:, :, t0:] - mu[..., None]) / (sd[..., None] + 1), 0, None).sum(0)


def ev_novelty(c):
    N, t_tr, t0, T = len(c["users"]), c["t_tr"], c["t_cut"], c["nd"] - c["t_cut"]
    e0 = (c["day0"] - pd.Timestamp("1970-01-01")).days
    out = {}
    # new computers
    t = pq.read_table(WORK / c["rel"] / "pc_pairs", columns=["user", "day", "pc"])
    u = c["uix"].get_indexer(t["user"].to_pandas()); day = t["day"].combine_chunks().cast(pa.int32()).to_numpy() - e0
    p, _ = pd.factorize(t["pc"].to_pandas()); del t
    key = u.astype(np.int64) * (p.max() + 1) + p
    trk = np.unique(key[day < t_tr]); te = (day >= t0) & (u >= 0)
    new = te & ~np.isin(key, trk)
    NP = np.zeros((N, T)); np.add.at(NP, (u[new], day[new] - t0), 1); out["newpc"] = NP
    # rare new sites
    t = pq.read_table(WORK / c["rel"] / "dom_pairs", columns=["user", "day", "domain"])
    day = t["day"].combine_chunks().cast(pa.int32()).to_numpy() - e0
    ud = t["user"].combine_chunks().dictionary_encode()
    u = c["uix"].get_indexer(pd.Index(ud.dictionary.to_pylist()))[ud.indices.to_numpy()]
    dd = t["domain"].combine_chunks().dictionary_encode(); dom = dd.indices.to_numpy().astype(np.int64)
    ndom = len(dd.dictionary); del t, ud, dd
    key = u.astype(np.int64) * ndom + dom
    trk = np.unique(key[day < t_tr])
    pop = np.bincount(trk % ndom, minlength=ndom)                       # distinct training users per domain
    rare = pop < 0.01 * N
    te = (day >= t0) & (u >= 0)
    sel = te & rare[dom]
    sel[sel] = ~np.isin(key[sel], trk)
    RS = np.zeros((N, T)); np.add.at(RS, (u[sel], day[sel] - t0), 1); out["raresite"] = RS
    log(f"novelty: rare domains {rare.sum():,}/{ndom:,}; test person-days with a new PC {int((NP > 0).sum()):,}, "
        f"with a rare new site {int((RS > 0).sum()):,}")
    return out


def pooled_p(V, pool=POOL):
    """per day: share of all (person, day) values over the trailing `pool` test days that are >= / mid-p"""
    N, T = V.shape; P_ge = np.ones((N, T)); P_mid = np.ones((N, T))
    for t in range(T):
        ref = np.sort(V[:, max(0, t - pool + 1):t + 1].ravel()); n = len(ref)
        lo = np.searchsorted(ref, V[:, t], "left"); hi = np.searchsorted(ref, V[:, t], "right")
        P_ge[:, t] = (n - lo) / n; P_mid[:, t] = (n - hi + 0.5 * (hi - lo)) / n
    return P_ge, P_mid


def evidence(c):
    E = {"a_R2": ev_R2(c)}; log("R2 done")
    E["b_PCT"] = ev_PCT(c); log("PCT done")
    fam = {"z": ev_Z(c), "pct": E["b_PCT"], **ev_novelty(c)}
    tails, zs = [], []
    for k, V in fam.items():
        pg, pm = pooled_p(V)
        tails.append(-np.log10(pg)); zs.append(norm.isf(np.clip(pm, 1e-12, 1 - 1e-12)))
    E["c_FUSE_MAX"] = np.max(tails, axis=0)
    E["c2_FUSE_STOUF"] = np.clip(np.sum(zs, axis=0) / np.sqrt(len(zs)), 0, None)
    c["fam"] = fam
    log("fusion done")
    return E


# ---------------------------------------------------------------- running score and daily lists
def running(e, rule):
    if rule == "today":
        return e.copy()
    R = np.zeros_like(e); prev = np.zeros(e.shape[0])
    for t in range(e.shape[1]):
        prev = LAM * prev + e[:, t] if rule == "decay7" else np.maximum(prev, e[:, t]); R[:, t] = prev
    return R


def lists(R, K, jit):
    N, T = R.shape; ON = np.zeros((N, T), bool)
    for t in range(T):
        s = R[:, t]; cand = np.where(s > 0)[0]
        if len(cand) <= K:
            ON[cand, t] = True; continue
        order = cand[np.lexsort((jit[cand], s[cand]))[::-1]]
        ON[order[:K], t] = True
    return ON


# ---------------------------------------------------------------- grading
def grade(ON, ins):
    T = ON.shape[1]; rows = []
    for r in ins.itertuples():
        hits = np.where(ON[r.i, r.Ft:])[0]
        D = r.Ft + hits[0] if len(hits) else None
        pre = ON[r.i, max(0, r.Ft - 14):r.Ft].any()
        # POST-HOC diagnostics (added after the r4.2 run, see CHANGELOG): chronic listing before the attack
        hist = ON[r.i, :max(0, r.Ft - 14)]
        w = r.Lt - r.Ft; own = np.nan
        if w >= 1 and len(hist) >= w:   # same-length windows earlier in the person's own test history
            cs = np.concatenate([[0], np.cumsum(hist)]); own = ((cs[w:] - cs[:-w]) > 0).mean()
        rows.append(dict(user=r.user, scenario=r.scenario, F=r.F.date(), L=r.L.date(), span=r.Lt - r.Ft,
                         D=D, delay=(D - r.Ft) if D is not None else np.inf,
                         in_time=D is not None and D < r.Lt, listed_14d_before=bool(pre),
                         ph_fresh_in_time=bool(D is not None and D < r.Lt and not pre),
                         ph_listed_rate_before=hist.mean() if len(hist) else np.nan, ph_own_hist_chance=own))
    return pd.DataFrame(rows)


def summarize(g):
    dl = g.delay.values
    return {"n": len(g), "median delay": np.median(dl), "p90 delay": np.quantile(dl, 0.9, method="higher"),
            "<=1d": (dl <= 1).mean(), "<=7d": (dl <= 7).mean(), "<=30d": (dl <= 30).mean(),
            "in time (D<L)": g.in_time.mean(), "never": np.isinf(dl).mean(), "pre-F listed": g.listed_14d_before.mean(),
            "PH fresh in time": g.ph_fresh_in_time.mean(), "PH listed rate before": g.ph_listed_rate_before.mean(),
            "PH own-hist chance": g.ph_own_hist_chance.mean(), "PH own-hist n": int(g.ph_own_hist_chance.notna().sum())}


def chance(ON, ins, normal, rng):
    """identity shuffle: each insider gets the list trajectory of a random normal employee"""
    On = ON[normal]
    H = np.array([On[:, r.Ft:max(r.Ft + 1, r.Lt)].any(1) if r.Lt > r.Ft else np.zeros(len(On), bool)
                  for r in ins.itertuples()])                           # in-time window [F, L)
    H7 = np.array([On[:, r.Ft:r.Ft + 8].any(1) for r in ins.itertuples()])
    sc = ins.scenario.values; res = {}
    sims = np.zeros((NSHUF, 2 + len(set(sc))))
    for s in range(NSHUF):
        pick = rng.permutation(len(On))[:len(ins)]
        it = H[np.arange(len(ins)), pick]; w7 = H7[np.arange(len(ins)), pick]
        sims[s, 0], sims[s, 1] = it.mean(), w7.mean()
        for j, k in enumerate(sorted(set(sc))):
            sims[s, 2 + j] = it[sc == k].mean()
    res["in time"] = (sims[:, 0].mean(), np.quantile(sims[:, 0], 0.95))
    res["<=7d"] = (sims[:, 1].mean(), np.quantile(sims[:, 1], 0.95))
    for j, k in enumerate(sorted(set(sc))):
        res[f"S{k} in time"] = (sims[:, 2 + j].mean(), np.quantile(sims[:, 2 + j], 0.95))
    return res


def burden(ON, c, is_ins):
    T = ON.shape[1]; t0 = c["t_cut"]
    wk = (np.arange(T) + t0 + c["day0"].weekday()) // 7
    full = [w for w in np.unique(wk) if (wk == w).sum() == 7]
    first = np.where(ON.any(1), ON.argmax(1), -1)
    per_wk = [ON[:, wk == w].any(1).sum() for w in full]
    per_wk_norm = [(ON[:, wk == w].any(1) & ~is_ins).sum() for w in full]
    new_wk = [((first >= 0) & np.isin(first, np.where(wk == w)[0])).sum() for w in full[2:]]
    size = ON.sum(0)
    churn = np.mean([(ON[:, t] & ~ON[:, t - 1]).sum() / max(1, size[t]) for t in range(1, T)])
    ever = ON.any(1)
    return {"people/week": np.mean(per_wk), "normal/week": np.mean(per_wk_norm), "new entrants/week": np.mean(new_wk),
            "normal slot share": (ON[~is_ins].sum() / max(1, size.sum())), "daily churn": churn,
            "normal ever listed": int((ever & ~is_ins).sum()), "insiders ever listed": int((ever & is_ins).sum())}


def mcnemar(a, b):
    x, y = int((a & ~b).sum()), int((~a & b).sum())
    p = 1.0 if x + y == 0 else min(1.0, 2 * binom.cdf(min(x, y), x + y, 0.5))
    return x, y, p


def top_expected(v, mask, k):
    thr = np.sort(v)[::-1][k - 1]; above, tie = v > thr, v == thr
    return mask[above].sum() + (k - above.sum()) * mask[tie].sum() / tie.sum()


def main(rel):
    c = load(rel); ins = labels(c)
    N = len(c["users"]); is_ins = np.zeros(N, bool); is_ins[ins.i] = True; normal = np.where(~is_ins)[0]
    E = evidence(c); del c["G"]
    jit = np.random.RandomState(SEED).rand(N)
    rng = np.random.RandomState(SEED)
    summ, scen, burd, per = [], [], [], []
    ON_store = {}
    for m in METHODS:
        for rule in RULES:
            R = running(E[m], rule)
            if rule == "maxsofar":   # sanity vs the retrospective study: end-of-test ranking
                v = R[:, -1]
                log(f"sanity {m} max-so-far at end of test: insiders in top 20 = {top_expected(v, is_ins, 20):.1f}, "
                    f"top 100 = {top_expected(v, is_ins, 100):.1f}")
            for K in KS:
                ON = lists(R, K, jit); g = grade(ON, ins); ON_store[(m, rule, K)] = ON
                row = {"release": rel, "method": m, "rule": rule, "K": K, **summarize(g)}
                ch = chance(ON, ins, normal, rng)
                row["chance in time (mean)"], row["chance in time (p95)"] = ch["in time"]
                row["chance <=7d (mean)"] = ch["<=7d"][0]
                row.update(burden(ON, c, is_ins))
                caught = int(g.in_time.sum()); row["normal ever listed per in-time catch"] = row["normal ever listed"] / max(1, caught)
                summ.append(row)
                for k, gg in g.groupby("scenario"):
                    scen.append({"release": rel, "method": m, "rule": rule, "K": K, "scenario": k, **summarize(gg),
                                 "chance in time (mean)": ch[f"S{k} in time"][0], "chance in time (p95)": ch[f"S{k} in time"][1]})
                g.insert(0, "K", K); g.insert(0, "rule", rule); g.insert(0, "method", m); per.append(g)
        log(f"{m} graded")
    S, SC, P = pd.DataFrame(summ), pd.DataFrame(scen), pd.concat(per)
    S.to_csv(OUT / f"{rel}_summary.csv", index=False); SC.to_csv(OUT / f"{rel}_scenarios.csv", index=False)
    P.to_csv(OUT / f"{rel}_per_insider.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
    cols = ["method", "rule", "K", "median delay", "p90 delay", "<=1d", "<=7d", "<=30d", "in time (D<L)", "never",
            "pre-F listed", "chance in time (mean)", "chance in time (p95)"]
    print(f"\n===== {rel}: delay and coverage (all insiders, n={len(ins)}) =====")
    print(S[cols].round(3).to_string(index=False))
    print(f"\n----- {rel}: POST-HOC diagnostics (not pre-registered) -----")
    print(S[["method", "rule", "K", "in time (D<L)", "PH fresh in time", "PH listed rate before", "PH own-hist chance",
             "PH own-hist n"]].round(3).to_string(index=False))
    bcols = ["method", "rule", "K", "people/week", "normal/week", "new entrants/week", "normal slot share", "daily churn",
             "normal ever listed", "insiders ever listed", "normal ever listed per in-time catch"]
    print(f"\n===== {rel}: analyst burden =====")
    print(S[bcols].round(3).to_string(index=False))
    print(f"\n===== {rel}: per scenario, primary rule (decay7) =====")
    print(SC[SC.rule == "decay7"].drop(columns=["release", "rule"]).round(3).to_string(index=False))
    print(f"\n===== {rel}: paired comparison, in time, decay7 (x = only first method, y = only second) =====")
    for K in KS:
        gp = P[(P.rule == "decay7") & (P.K == K)].set_index(["method", "user"]).in_time
        for m in ["b_PCT", "c_FUSE_MAX", "c2_FUSE_STOUF"]:
            x, y, p = mcnemar(gp[m].values, gp["a_R2"].values)
            print(f"K={K}: {m} vs a_R2: {m} only {x}, a_R2 only {y}, exact McNemar p = {p:.3f}")
    log(f"done; peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30:.2f} GB")


if __name__ == "__main__":
    main(sys.argv[1])
