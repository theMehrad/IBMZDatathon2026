"""Nguyen's copy of code/outofrole_minimal.py with two extra inputs for the daily list. The team's script is not changed.

Final setting (chosen on r4.2, confirmed once on r5.2):
    python test/outofrole_email.py 5.2 --feats=n_new_site,n_boss_pc --w=5
        r4.2: 59 -> 63/70 insiders, sysadmins 4 -> 8/10, normal staff listed 230 -> 219
        r5.2: 80 -> 83/99 insiders, sysadmins 2 -> 6/10, normal staff listed 291 -> 279

The two inputs (counted per person per day, built from the tables + LDAP, no rebuild needed):
    n_new_site   visits to websites nobody in the company visited during training (the R1 rule's signal)
    n_boss_pc    logons to one's own supervisor's main computer (supervisor from that month's LDAP file)
Both are rare for normal staff, so with --w=5 each counts 5 points when unusual; the original 9 stay at 1 point.

Options:
    --no-email          the team's original 9 activities only: reproduces their numbers (80/99 on r5.2)
    --feats=a,b         extra inputs to add: n_new_site, n_boss_pc, or the email inputs (n_email_out,
                        n_email_out_ah, n_email_out_att, n_email_rcpt; tested on r4.2 and dropped)
    --w=N               points for n_new_site / n_boss_pc when unusual (default 1)
    --export            also write data/exports_nguyen/r{rel}_cases.jsonl: one record per person per day on the
                        list (why flagged + top 5 evidence facts), label-free, for the Granite step. Never commit it.
    --why-s3            print a per-sysadmin diagnostic (uses the answer key: for understanding only)
    (no --feats)        original 9 + all 4 email inputs, the first experiment; not the final setting


    run: python test/outofrole_email.py 5.2 --feats=n_new_site,n_boss_pc --w=5 --export
    or
    bash run.sh

Changes from the original, each marked "NGUYEN:" below: paths come from the repo folder (or OUTOFROLE_BASE /
OUTOFROLE_CACHE) instead of Mehrad's laptop; tables come from data/cache_nguyen/ (built by build_tables_email.py);
the activity list can include the extra inputs, with the hard-coded 9 replaced by the length of that list;
"active day" still means a day with logon/USB/file/web activity, so the baseline and training weeks are identical
whatever inputs are added; the report also prints results by attack type. Every other setting is unchanged.

Original description:

Inputs: the Parquet tables built by Spark (daily counts, person-computer-day, person-site-day) and the
CERT answer key, used ONLY for grading. Protocol: train on weeks before the cutoff week, test from the
cutoff, labels never used to fit anything. This is the reference the team ports to the LinuxONE server.
"""
import csv, glob, os, re, sys
from pathlib import Path
import numpy as np, pandas as pd

REL = sys.argv[1]; USE_EMAIL = "--no-email" not in sys.argv
PICK = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--feats=")), None)   # NGUYEN: e.g. --feats=n_email_out_att
WEIGHT = float(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--w=")), 1))      # NGUYEN: points for n_new_site / n_boss_pc
_here = Path(__file__).resolve()
BASE = os.environ.get("OUTOFROLE_BASE", str(_here.parents[1] if (_here.parents[1] / "data").exists() else _here.parents[2]))   # NGUYEN: repo root (works from test/ or code/nguyen/)
WORK = os.environ.get("OUTOFROLE_CACHE", f"{BASE}/data/cache_nguyen") + f"/r{REL}"   # NGUYEN: own cache folder
ANS = f"{BASE}/data/answers/answers"
CUT = pd.Timestamp({"4.2": "2010-06-01", "5.2": "2010-04-01"}[REL])
TRAIN_END = CUT - pd.Timedelta(days=CUT.weekday())            # Monday of the cutoff week (that week is dropped)
F9 = ["n_logon", "n_logon_ah", "n_usb", "n_usb_ah", "n_file", "n_file_ah", "n_http", "n_http_ah", "n_pcs"]
EMAIL = ["n_email_out", "n_email_out_ah", "n_email_out_att", "n_email_rcpt"]                # NGUYEN: new
K, HALF_LIFE = 20, 7                                           # daily list size; running score halves every 7 days

# ------------------------------------------------------------------ load
daily = pd.read_parquet(f"{WORK}/daily"); daily["day"] = pd.to_datetime(daily.day)
pcs = pd.read_parquet(f"{WORK}/pc_pairs"); pcs["day"] = pd.to_datetime(pcs.day)
dom = pd.read_parquet(f"{WORK}/dom_pairs"); dom["day"] = pd.to_datetime(dom.day)

# ---- NGUYEN: two sysadmin-focused inputs, computed from the tables above + LDAP (no rebuild needed) ----------------
# n_new_site: visits to websites that NOBODY in the company visited during training (the R1 rule, now fed into M1).
#             The "seen" list is frozen at TRAIN_END, so each day only uses the past.
# n_boss_pc:  logging on to the main computer of one's own supervisor (supervisor from that month's LDAP file;
#             each person's main computer = the one they logged on to on the most training days).
NEW = ["n_new_site", "n_boss_pc"]
seen_sites = set(dom.loc[dom.day < TRAIN_END, "domain"])
ns = dom[(dom.day >= TRAIN_END) & ~dom.domain.isin(seen_sites)].groupby(["user", "day"]).n.sum().rename("n_new_site")
main_of = (pcs[pcs.day < TRAIN_END].groupby(["user", "pc"]).size().reset_index(name="d")
           .sort_values(["user", "d", "pc"], ascending=[True, False, True]).drop_duplicates("user").set_index("user").pc)
LDAP = sorted(glob.glob(f"{BASE}/data/r{REL}/r{REL}/LDAP/*.csv"))
assert LDAP, f"no LDAP files in data/r{REL}/r{REL}/LDAP/"
sup = []
for f in LDAP:                                   # columns by position: name first, user_id second, supervisor last
    l = pd.read_csv(f, dtype=str, keep_default_na=False)
    name2id = dict(zip(l.iloc[:, 0], l.iloc[:, 1]))
    sup.append(pd.DataFrame({"month": pd.Period(os.path.basename(f)[:7], "M"), "user": l.iloc[:, 1],
                             "boss": l.iloc[:, -1].map(name2id)}))
sup = pd.concat(sup).dropna(subset=["boss"])
lp = pcs.assign(month=pcs.day.dt.to_period("M")).merge(sup, on=["month", "user"], how="left")
lp["boss_pc"] = lp.boss.map(main_of)
lp = lp[(lp.pc == lp.boss_pc) & (lp.pc != lp.user.map(main_of))]              # the boss's PC, and not one's own
bp = lp.groupby(["user", "day"]).size().rename("n_boss_pc")
daily = daily.merge(pd.concat([ns, bp], axis=1).reset_index(), on=["user", "day"], how="left")
daily[NEW] = daily[NEW].fillna(0)
print(f"   NGUYEN inputs: {len(seen_sites)} sites seen in training; supervisor links in {len(LDAP)} LDAP files; "
      f"{int((daily.n_boss_pc > 0).sum())} person-days with a logon to the boss's PC; "
      f"{int((daily.n_new_site > 0).sum())} person-days with a never-seen site")

OPTIONAL = EMAIL + NEW
if PICK: assert set(PICK) <= set(OPTIONAL), f"--feats must be from {OPTIONAL}"
CHOSEN = (PICK or EMAIL) if USE_EMAIL else []
missing = [f for f in CHOSEN if f not in daily.columns]
assert not missing, f"missing columns {missing}: run build_tables_email.py first"
FEATS = F9 + CHOSEN                                                                 # NGUYEN: the activity list
WVEC = np.array([WEIGHT if f in NEW else 1.0 for f in FEATS])                      # NGUYEN: points per unusual activity
daily_act = daily[daily[F9].sum(axis=1) > 0]       # NGUYEN: staff, days and 'active day' come from the original 9 only
ins = pd.read_csv(f"{ANS}/insiders.csv"); ins = ins[ins.dataset.astype(str) == REL].set_index("user")
users = np.sort(daily_act.user.unique()); U = {u: i for i, u in enumerate(users)}; normal = ~np.isin(users, ins.index)
days = pd.date_range(daily_act.day.min(), daily_act.day.max()); t0 = days.get_loc(CUT); T = len(days) - t0
ACT = np.zeros((len(users), len(days)), bool); ACT[daily_act.user.map(U).values, (daily_act.day - days[0]).dt.days.values] = True
assert not daily.duplicated(['user', 'day']).any() and not pcs.duplicated(['user', 'day', 'pc']).any()
assert ins.index.isin(users).all() and (pd.to_datetime(ins.start) >= CUT).all(), 'every insider present, every attack after the cutoff'

def als(Xc, rank=64, alpha=0.5, reg=1.0, iters=12, seed=0):                      # Hu-Koren-Volinsky implicit ALS
    rng = np.random.default_rng(seed); P = rng.normal(0, .01, (Xc.shape[0], rank)); Q = rng.normal(0, .01, (Xc.shape[1], rank))
    C = alpha * Xc
    def solve(C, Y):
        out, YtY = np.zeros((C.shape[0], rank)), Y.T @ Y
        for r in range(C.shape[0]):
            nz = np.nonzero(C[r])[0]; c = C[r, nz]; Yr = Y[nz]
            out[r] = np.linalg.solve(YtY + (Yr.T * c) @ Yr + reg * np.eye(rank), (Yr.T * (1 + c)).sum(1))
        return out
    for _ in range(iters): P = solve(C, Q); Q = solve(C.T, P)
    return P @ Q.T

# ------------------------------------------------------------------ 1. early warning: own-history weekly percentile
X = daily.set_index(["user", "day"])[FEATS].unstack("day").reindex(index=users)
X = np.stack([X[f].reindex(columns=days).fillna(0).values for f in FEATS], -1)             # person x day x activity
week = np.array([(d - pd.Timestamp("2009-12-28")).days // 7 for d in days])
ref = [w for w in np.unique(week) if days[week == w].max() < TRAIN_END]                  # full training weeks only
W = np.stack([X[:, week == w].sum(1) for w in ref], 1); Wact = np.stack([ACT[:, week == w].any(1) for w in ref], 1)
cs = np.concatenate([np.zeros((len(users), 1, len(FEATS))), X.cumsum(1)], 1)   # NGUYEN: was a hard-coded 9
last7 = np.stack([cs[:, t + 1] - cs[:, max(0, t - 6)] for t in range(t0, len(days))], 1)  # trailing 7 days, past only
pct_score = np.zeros((len(users), T))
UNUSUAL = np.zeros((len(users), T, len(FEATS)), bool)                                  # NGUYEN: kept for --export
for i in range(len(users)):
    r = W[i][Wact[i]]
    if len(r):
        p = ((r[None] < last7[i][:, None]).sum(1) + 0.5 * (r[None] == last7[i][:, None]).sum(1)) / len(r)
        UNUSUAL[i] = p >= 0.99
        pct_score[i] = (p >= 0.99) @ WVEC + 0.01 * p.sum(1)          # activities above every normal week (NGUYEN: weighted)

def r2_score():                                                                         # baseline: 28-day personal window
    idx = [F9.index(f) for f in ["n_usb", "n_file", "n_logon_ah", "n_usb_ah", "n_http_ah"]]
    act = ACT; ntr = act[:, :(TRAIN_END - days[0]).days].sum(1).clip(min=1)
    rate = X[:, :(TRAIN_END - days[0]).days][:, :, idx].sum(1) / ntr[:, None]
    c = np.concatenate([np.zeros((len(users), 1, len(idx))), X[:, :, idx].cumsum(1)], 1)
    ca = np.concatenate([np.zeros((len(users), 1)), act.cumsum(1)], 1)
    R = np.stack([c[:, t + 1] - c[:, max(0, t - 27)] for t in range(t0, len(days))], 1)
    n = np.stack([ca[:, t + 1] - ca[:, max(0, t - 27)] for t in range(t0, len(days))], 1)
    exp = rate[:, None, :] * n[:, :, None]
    return np.clip((R - exp) / np.sqrt(exp + 1), 0, None).sum(-1)

def daily_lists(score, decay, k=K):
    jit = np.random.default_rng(0).random(len(users)); lam = 0.5 ** (1 / HALF_LIFE); run = np.zeros(len(users))
    on = np.zeros(score.shape, bool)
    for t in range(T):
        run = lam * run + score[:, t] if decay else score[:, t]
        cand = np.where(run > 0)[0]; on[cand[np.lexsort((jit[cand], run[cand]))[::-1]][:k], t] = True
    return on

def own_events(user, scen):
    f = glob.glob(f"{ANS}/r{REL}-{scen}/*{user}*.csv")[0]
    return [r for r in csv.reader(open(f, errors="replace")) if len(r) > 4 and r[3] == user]

EVENTS = {u: own_events(u, r.scenario) for u, r in ins.iterrows()}
def in_time(on):
    flag, after = {}, {}                                         # after = share of own malicious events on later days
    for u, r in ins.iterrows():
        F, L = (pd.Timestamp(r.start).normalize() - CUT).days, (pd.Timestamp(r.end).normalize() - CUT).days
        h = np.where(on[U[u], F:])[0]
        if len(h) and F + h[0] < L:
            flag[u] = F + h[0]
            evd = np.array([(pd.to_datetime(e[2]).normalize() - CUT).days for e in EVENTS[u]])
            after[u] = (evd > flag[u]).mean()
    return flag, after

on_pct = daily_lists(pct_score, decay=True); on_r2 = daily_lists(r2_score(), decay=False)
FLAG, after = in_time(on_pct); flag_r2, _ = in_time(on_r2)
churn = lambda on: np.mean([(on[:, t] & ~on[:, t - 1]).sum() / K for t in range(1, T)])

# ------------------------------------------------------------------ 1b. snooping list: computers the recommender would never suggest
pc_tr, pc_te = pcs[pcs.day < TRAIN_END], pcs[pcs.day >= CUT]
comps = np.sort(pc_tr.pc.unique()); Cx = {c: j for j, c in enumerate(comps)}
gp = pc_tr.groupby(["user", "pc"]).day.nunique()
Xp = np.zeros((len(users), len(comps))); Xp[gp.index.get_level_values(0).map(U), gp.index.get_level_values(1).map(Cx)] = np.log1p(gp.values)
pred_pc = als(Xp, rank=16, alpha=10.0, reg=0.1)                                   # study's computer setting
tu_, tc_ = pc_te.user.map(U).values, pc_te.pc.map(Cx).fillna(-1).astype(int).values
new_pc = np.where(tc_ >= 0, Xp[tu_, np.maximum(tc_, 0)] == 0, True)
surprise = np.where(tc_ >= 0, 1 - np.clip(pred_pc[tu_, np.maximum(tc_, 0)], 0, 1), 1.0)
main_pc = pc_tr.groupby(["user", "pc"]).size().reset_index().sort_values(0, ascending=False).drop_duplicates("user").set_index("user").pc
roam = (pc_tr.pc != pc_tr.user.map(main_pc)).groupby(pc_tr.user).mean()          # training share of logins away from one's main PC
def weekly_count(flag):                                                           # weeks with a flagged login, discounted for roamers
    wk = pc_te.assign(f=flag, week=pc_te.day.dt.to_period("W").dt.start_time).groupby(["user", "week"]).f.any()
    return (wk.groupby(level=0).sum() / (1 + 50 * roam.reindex(wk.groupby(level=0).sum().index).fillna(0))).reindex(users).fillna(0)
def top100(score, scen, k=100):
    who = set(ins.index[ins.scenario == scen]); s = score + np.random.default_rng(2).random(len(users)) * 1e-9
    return sum(u in who for u in users[np.argsort(-s.values)[:k]]), len(who)
snoop = {"recommender would never suggest": weekly_count(new_pc & (surprise >= 0.5)), "any computer new to the person": weekly_count(new_pc)}

def snoop_lists(flag, k=10):                                                       # live: weeks with a flagged login so far
    d = pc_te.assign(f=flag)[lambda x: x.f]; d = d.assign(week=d.day.dt.to_period("W").dt.start_time)
    first = d.groupby(["user", "week"]).day.min().reset_index()                     # first flagged day of each flagged week
    inc = np.zeros((len(users), T)); np.add.at(inc, (first.user.map(U).values, (first.day - CUT).dt.days.values), 1)
    score = inc.cumsum(1) / (1 + 50 * roam.reindex(users).fillna(0).values[:, None])
    return daily_lists(score, decay=False, k=k)
on_snoop = snoop_lists(new_pc & (surprise >= 0.5)); on_snoop_naive = snoop_lists(new_pc)

# ------------------------------------------------------------------ 2. evidence for Granite: "new to you, rarest first"
EVIDENCE_START = CUT                                                   # replay day zero: lists and case evidence start here
DOMRE = re.compile(r"^https?://(?:www\.)?([^/:]+)")
mal = set()
for u, evs in EVENTS.items():
    for e in evs:
        ts = pd.to_datetime(e[2]); d = ts.normalize()
        if e[0] == "logon":
            mal.add((u, d, "pc", e[4]))
            if e[5] == "Logon" and (ts.hour < 7 or ts.hour >= 19): mal.add((u, d, "ah", "AH"))
        elif e[0] == "http" and (m := DOMRE.match(e[5])): mal.add((u, d, "dom", m.group(1).lower()))
        elif e[0] == "device": mal.add((u, d, "usb", "USB"))

def hit_at(s, m, k):                                       # P(a malicious item in the top k), ties in random order
    k = min(k, len(s)); kth = np.sort(s)[::-1][k - 1]
    if m[s > kth].any(): return 1.0
    tie = s == kth; r, n, g = k - (s > kth).sum(), tie.sum(), m[tie].sum()
    return 0.0 if g == 0 else 1.0 if n - g < r else 1 - np.prod([(n - g - j) / (n - j) for j in range(r)])

def items(df, kind, col):
    return df[["user", "day", col]].rename(columns={col: "item"}).assign(kind=kind)
def usb_ah(d):
    d = d[d[F9].sum(axis=1) > 0]                                                       # NGUYEN: same rows as the original
    return pd.concat([d[d.n_usb > 0].assign(item="USB", kind="usb"), d[d.n_logon_ah > 0].assign(item="AH", kind="ah")])[["user", "day", "item", "kind"]]
space = {"pc": "pc", "usb": "pc", "ah": "pc", "dom": "dom"}                              # USB / after-hours live with computers
train_items = pd.concat([items(pcs[pcs.day < TRAIN_END], "pc", "pc"), items(dom[dom.day < TRAIN_END], "dom", "domain"),
                         usb_ah(daily[daily.day < TRAIN_END])])
train_items["sp"] = train_items.kind.map(space)
used = set(zip(train_items.user, train_items.sp, train_items.item))
share = (train_items.drop_duplicates(["user", "sp", "item"]).groupby(["sp", "item"]).size() / len(users)).to_dict()

listed = set(users[on_pct.any(1) | on_snoop.any(1)])                   # everyone who ever reaches either daily list
listed |= set(users[np.argsort(-snoop['recommender would never suggest'].values)[:100]])   # and the snooping review's top 100
keep = lambda df: df[df.user.isin(listed) & (df.day >= EVIDENCE_START)]
CASE = pd.concat([items(keep(pcs), "pc", "pc"), items(keep(dom), "dom", "domain"), usb_ah(keep(daily))]).drop_duplicates()
CASE["sp"] = CASE.kind.map(space)
CASE["new"] = [(u, s, i) not in used for u, s, i in zip(CASE.user, CASE.sp, CASE.item)]
CASE["share"] = [share.get((s, i), 0.0) for s, i in zip(CASE.sp, CASE.item)]
CASE["score"] = 2 * CASE.new + (1 - CASE.share)                       # C1: new to this person first, then rarest
CASE = dict(tuple(CASE.groupby("user")))

def case_items(u, t):                                                  # label-free: what the analyst sees for u on day t
    it = CASE.get(u)
    return it[it.day <= CUT + pd.Timedelta(days=int(t))] if it is not None else None

def hit3(u, t, col="score", rare_only=False):
    it = case_items(u, t)
    if it is None or not len(it): return 0.0
    s = (1 - it.share.values) if rare_only else it[col].values
    m = np.array([(u, d, k, i) in mal for d, k, i in zip(it.day, it.kind, it.item)])
    return hit_at(s, m, 3)

def strong(u, t):                                                      # label-free evidence strength
    it = case_items(u, t)
    return bool(it is not None and (it.new & (it.share < 0.01)).any())

first = {u: int(np.argmax(on_pct[U[u]])) for u in listed if on_pct[U[u]].any()}   # first day on the daily list, from replay day zero
ev_graded = (np.mean([hit3(u, t) for u, t in FLAG.items()]), np.mean([hit3(u, t, rare_only=True) for u, t in FLAG.items()]))
ins_first = {u: t for u, t in first.items() if u in ins.index}
pre_onset = np.mean([t < (pd.Timestamp(ins.loc[u, "start"]).normalize() - CUT).days for u, t in ins_first.items()])
ev_first = np.mean([hit3(u, t) for u, t in ins_first.items()])
strong_ins = np.mean([strong(u, t) for u, t in FLAG.items()])
strong_ins_first = np.mean([strong(u, t) for u, t in ins_first.items()])
strong_nrm = np.mean([strong(u, t) for u, t in first.items() if u not in ins.index])

# ------------------------------------------------------------------ 3 and 4. recommender: predict next sites, pre-approve them
sites = np.sort(dom[dom.day < TRAIN_END].domain.unique()); S = {d: j for j, d in enumerate(sites)}
g = dom[dom.day < TRAIN_END].groupby(["user", "domain"]).day.nunique()
Xs = np.zeros((len(users), len(sites))); Xs[g.index.get_level_values(0).map(U), g.index.get_level_values(1).map(S)] = np.log1p(g.values)
own = Xs > 0
def top20(score):
    s = np.where(own, -np.inf, score + np.random.default_rng(1).random(score.shape) * 1e-9)
    return ((-s).argsort(1).argsort(1) < 20) & ~own
grant = {"popularity": top20(np.tile(own.sum(0).astype(float), (len(users), 1))), "recommender": top20(als(Xs))}
te = dom[dom.day >= CUT][["user", "domain"]].drop_duplicates()
te = te[te.user.isin(users[normal])]; tu, ti = te.user.map(U).values, te.domain.map(S).fillna(-1).astype(int).values
known = ti >= 0; months = (dom.day.max() - CUT).days / 30.44
allowed = lambda A: np.where(known, A[tu, np.maximum(ti, 0)], False)
new_pair = known & ~own[tu, np.maximum(ti, 0)]
n_new = (~known | new_pair).sum()                                                    # unknown sites count as misses
recall = {k: (allowed(A) & new_pair).sum() / n_new for k, A in grant.items()}
requests = {"own history": (~allowed(own)).sum() / normal.sum() / months}
requests.update({k: (~allowed(own | A)).sum() / normal.sum() / months for k, A in grant.items()})
used_share = {k: (allowed(A) & new_pair).sum() / A[normal].sum() for k, A in grant.items()}
mal_web = [(U[u], DOMRE.match(e[5]).group(1).lower()) for u in ins.index for e in EVENTS[u] if e[0] == "http" and DOMRE.match(e[5])]
held = lambda A: np.mean([not (d in S and A[i, S[d]]) for i, d in mal_web])                 # malicious visits needing approval
coverage = {"own history": held(own), **{k: held(own | A) for k, A in grant.items()}}

te_all = dom[dom.day >= CUT][["user", "domain"]].drop_duplicates()
te_all = te_all[te_all.domain.isin(S)]
used_test = np.zeros_like(own); used_test[te_all.user.map(U).values, te_all.domain.map(S).values] = True
still = normal & ACT[:, -30:].any(1)
stale = own & ~used_test                                                   # access held but not used again: revoke?

# ------------------------------------------------------------------ 5. block sites nobody here visited in training
mal_sites = [(r.scenario, DOMRE.match(e[5]).group(1).lower()) for u, r in ins.iterrows() for e in EVENTS[u]
             if e[0] == "http" and DOMRE.match(e[5])]
blocked = {s: np.mean([d not in S for sc, d in mal_sites if sc == s]) for s in (1, 3)}
nov = dom[(dom.day >= CUT) & ~dom.domain.isin(S) & dom.user.isin(users[normal])]

# ------------------------------------------------------------------ report
# ------------------------------------------------------------------ NGUYEN: --export  (flagged people + their evidence, for the Granite step)
# One JSON line per person per day on the 20-name list. Label-free: built only from logs up to that day, never the answer key.
# Written under data/ (git-ignored): it is derived from CERT data, which must not be redistributed.
if "--export" in sys.argv:
    import json
    NAMES = {"n_logon": "logons", "n_logon_ah": "after-hours logons", "n_usb": "USB connections", "n_usb_ah": "after-hours USB connections",
             "n_file": "files copied", "n_file_ah": "after-hours file copies", "n_http": "web visits", "n_http_ah": "after-hours web visits",
             "n_pcs": "computers used", "n_new_site": "visits to never-seen websites", "n_boss_pc": "logons to the supervisor's computer",
             "n_email_out": "emails to outside addresses", "n_email_out_ah": "after-hours emails to outside addresses",
             "n_email_out_att": "outside emails with attachments", "n_email_rcpt": "email recipients"}
    owner = {pc: u for u, pc in main_of.items()}                                        # computer -> whose main computer it is
    boss_pc = {(r.user, r.month): main_of.get(r.boss) for r in sup.itertuples()}         # (person, month) -> supervisor's main computer
    dd = daily.set_index(["user", "day"])
    lam = 0.5 ** (1 / HALF_LIFE); run = np.zeros(len(users)); seen_before = set()
    out_dir = Path(BASE) / "data" / "exports_nguyen"; out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"r{REL}_cases.jsonl"; n_rows = 0
    with open(out, "w") as fh:
        for t in range(T):
            run = lam * run + pct_score[:, t]
            day = CUT + pd.Timedelta(days=t)
            for i in np.where(on_pct[:, t])[0]:
                u = users[i]; ref_w = W[i][Wact[i]]
                why = [{"activity": NAMES.get(f, f), "this_week": int(last7[i][t][k]), "normal_max": int(ref_w[:, k].max()) if len(ref_w) else 0}
                       for k, f in enumerate(FEATS) if UNUSUAL[i, t, k]]
                it = case_items(u, t); facts = []
                if it is not None and len(it):
                    for k, r in enumerate(it.sort_values(["score", "day"], ascending=[False, False]).head(5).itertuples()):
                        f = {"id": f"E{k + 1}", "date": str(r.day)[:10], "kind": r.kind, "item": str(r.item),
                             "new_to_person": bool(r.new), "staff_share": round(float(r.share), 4)}
                        if r.kind == "pc":
                            f["supervisors_computer"] = boss_pc.get((u, r.day.to_period("M"))) == r.item
                            f["someone_elses_main_computer"] = owner.get(r.item, u) != u
                        if r.kind == "dom": f["never_seen_in_company"] = r.item not in seen_sites
                        if r.kind == "usb" and (u, r.day) in dd.index:
                            row = dd.loc[(u, r.day)]
                            f["usb_connections_that_day"] = int(row.n_usb); f["files_copied_that_day"] = int(row.n_file)
                        if r.kind == "ah" and (u, r.day) in dd.index:
                            f["after_hours_logons_that_day"] = int(dd.loc[(u, r.day)].n_logon_ah)
                        facts.append(f)
                strong = any(f["new_to_person"] and f["staff_share"] < 0.01 for f in facts)
                fh.write(json.dumps({"release": REL, "day": str(day.date()), "person": u, "first_day_on_list": u not in seen_before,
                                     "running_score": round(float(run[i]), 2), "why_flagged": why, "facts": facts,
                                     "strength": "strong" if strong else "weak"}) + "\n")
                seen_before.add(u); n_rows += 1
    print(f"   NGUYEN export: {n_rows} records ({len(seen_before)} people, 20 per day) written to {out}")

n = len(ins)
print(f"== r{REL}: {len(users)} staff, {n} insiders; daily list uses {len(FEATS)} activities ({', '.join(FEATS[9:]) if len(FEATS) > 9 else 'original 9 only'}) ==")
print(f"1  early warning, 20 names/day: {len(FLAG)}/{n} insiders listed before their last malicious action "
      f"(28-day baseline: {len(flag_r2)}/{n}); daily churn {churn(on_pct):.1%} vs {churn(on_r2):.1%}")
print(f"   share of each insider's malicious events on later days: {sum(after.values()) / n:.2f} averaged over all insiders "
      f"(missed = 0), {np.mean(list(after.values())):.2f} over those flagged in time; "
      f"normal staff ever listed {(on_pct.any(1) & normal).sum()} over {T / 7:.0f} weeks")
print(f"2  evidence top 3 holds a malicious item: C1 {ev_graded[0]:.2f} vs rarity {ev_graded[1]:.2f} (in-time insiders, evidence up to the "
      f"graded flag day); at each insider's first alert {ev_first:.2f} ({pre_onset:.0%} of first alerts come before labelled onset)")
print(f"   label-free evidence strength (an item not in the person's training history, used by under 1% of staff): at first alert, "
      f"insiders {strong_ins_first:.0%} vs normal staff {strong_nrm:.0%}; insiders at the graded in-time day {strong_ins:.0%}")
print(f"3  next new sites caught by top 20: recommender {recall['recommender']:.3f} vs popularity {recall['popularity']:.3f}")
print("4  access requests per person-month: " + ", ".join(f"{k} {v:.2f}" for k, v in requests.items())
      + f"; share of the recommender's extra grants later used {used_share['recommender']:.2f}")
print("   malicious web visits that would need approval (static coverage): " + ", ".join(f"{k} {v:.1%}" for k, v in coverage.items()))
print(f"   end-of-period access-review proxy: {stale[still].sum() / own[still].sum():.1%} of training person-site pairs not revisited "
      f"({stale[still].sum(1).mean():.1f} per person; {(stale[still].sum(1) > 0).mean():.0%} of people have at least one)")
print("   by scenario, in time: " + ", ".join(f"S{s} {sum(ins.loc[u, 'scenario'] == s for u in FLAG)}/{(ins.scenario == s).sum()}" for s in sorted(ins.scenario.unique())))   # NGUYEN: new
if "--why-s3" in sys.argv:                       # NGUYEN: diagnosis only (uses the answer key, so never use it to pick settings)
    dd = daily.set_index(["user", "day"])
    print(f"   S3 detail (points for new inputs: {WEIGHT:g}); day 0 = first malicious day:")
    for u, r in ins[ins.scenario == 3].iterrows():
        F = (pd.Timestamp(r.start).normalize() - CUT).days; d0 = CUT + pd.Timedelta(days=F)
        v = dd.loc[(u, d0)] if (u, d0) in dd.index else None
        rank = int((pct_score[:, F] > pct_score[U[u], F]).sum()) + 1
        listed = [int(t - F) for t in np.where(on_pct[U[u]])[0] if F - 3 <= t <= F + 3]
        print(f"     {u}: day-0 new_site={int(v.n_new_site) if v is not None else 0} boss_pc={int(v.n_boss_pc) if v is not None else 0}; "
              f"day-0 score {pct_score[U[u], F]:.2f}, rank {rank}; listed on days {listed}; in time: {u in FLAG}")
flag_snoop, _ = in_time(on_snoop); flag_snoop_naive, _ = in_time(on_snoop_naive); flag_any, _ = in_time(on_pct | on_snoop)
s4 = set(ins.index[ins.scenario == 4])
if s4:
    print("6  snooping review (end of period, retrospective): weekly logins to computers outside the person's profile, snoopers in the top 100: "
          + ", ".join(f"{k} {top100(v, 4)[0]}/{top100(v, 4)[1]} (top 20: {top100(v, 4, 20)[0]})" for k, v in snoop.items()))
    print(f"   live snooping list, 10 names a day: snoopers listed before their last malicious action {len(s4 & set(flag_snoop))}/{len(s4)} "
          f"(any new computer: {len(s4 & set(flag_snoop_naive))}); with the 20-name list, snoopers {len(s4 & set(flag_any))}/{len(s4)} "
          f"(20-name list alone {len(s4 & set(FLAG))}); all insiders {len(flag_any)}/{n} (alone {len(FLAG)})")
else:
    print("6  snooping view: this release has no snoopers (scenario 4 exists only in r5.2)")
print(f"   snooping list load: normal staff ever on it {(on_snoop.any(1) & normal).sum()}; on either list {((on_pct | on_snoop).any(1) & normal).sum()}")
print(f"5  new-to-company rule blocks wikileaks {blocked[1]:.0%} and keylogger sites {blocked[3]:.0%}; "
      f"cost {len(nov[['user', 'day']].drop_duplicates())} normal person-days")
