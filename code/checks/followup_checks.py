"""Follow-up checks on outofrole_minimal.py: overfitting, keeping baselines fresh, role changes, recommender refresh.

    python followup_checks.py 4.2      (or 5.2)

Runs ../outofrole_minimal.py first (its numbers are unchanged) and reuses its tables and functions.
Labels are used only for grading, as everywhere else.
"""
import contextlib, io, os, runpy, sys
import numpy as np, pandas as pd

REL = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
with contextlib.redirect_stdout(io.StringIO()):
    sys.argv = ["outofrole_minimal.py", REL]; g = runpy.run_path(os.path.join(HERE, "..", "outofrole_minimal.py"))
ins, users, U, normal, T, t0 = g["ins"], g["users"], g["U"], g["normal"], g["T"], g["t0"]
X, ACT, week, days, last7, CUT, TRAIN_END = g["X"], g["ACT"], g["week"], g["days"], g["last7"], g["CUT"], g["TRAIN_END"]
in_time, daily_lists, als, dom = g["in_time"], g["daily_lists"], g["als"], g["dom"]
print(f"== r{REL}: {len(users)} staff, {len(ins)} insiders ==")

# ---------------------------------------------------------------- A. overfitting: how stable is the lead over the baseline?
names = list(ins.index); a = np.array([u in g["FLAG"] for u in names]); b = np.array([u in g["flag_r2"] for u in names])
rng = np.random.default_rng(0); idx = rng.integers(0, len(names), (5000, len(names)))
diff = a[idx].sum(1) - b[idx].sum(1)
print(f"A  in time, own-history list vs 28-day baseline: {a.sum()} vs {b.sum()} (difference {a.sum() - b.sum():+d}); "
      f"bootstrap over insiders, 95% interval {np.percentile(diff, 2.5):+.0f} to {np.percentile(diff, 97.5):+.0f}; "
      f"share of resamples where ours is not ahead {np.mean(diff <= 0):.3f}")

# ---------------------------------------------------------------- B. keeping "normal" fresh: rolling reference weeks
wk_ids = np.unique(week); complete = np.array([(week == w).sum() == 7 for w in wk_ids])
Wall = np.stack([X[:, week == w].sum(1) for w in wk_ids], 1); Aall = np.stack([ACT[:, week == w].any(1) for w in wk_ids], 1)
test_k = np.array([np.searchsorted(wk_ids, week[t0 + t]) for t in range(T)])
def rolling_score(win, lag):                       # reference = the person's active full weeks from (win + lag) to lag weeks ago
    score = np.zeros((len(users), T))
    for k in np.unique(test_k):
        cols = np.where(test_k == k)[0]; ref = [j for j in range(max(0, k - lag - win), k - lag) if complete[j]]
        if not ref: continue
        R, M, x = Wall[:, ref], Aall[:, ref], last7[:, cols]
        less = ((R[:, None] < x[:, :, None]) & M[:, None, :, None]).sum(2); eq = ((R[:, None] == x[:, :, None]) & M[:, None, :, None]).sum(2)
        n = M.sum(1)[:, None, None].astype(float); p = np.where(n > 0, (less + 0.5 * eq) / np.maximum(n, 1), 0)
        score[:, cols] = (p >= 0.99).sum(-1) + 0.01 * p.sum(-1)
    return score
churn = lambda on: np.mean([(on[:, t] & ~on[:, t - 1]).sum() / on[:, t].sum() for t in range(1, T) if on[:, t].sum()])
print(f"B  frozen training weeks (current build): in time {len(g['FLAG'])}/{len(ins)}, normal staff ever listed "
      f"{(g['on_pct'].any(1) & normal).sum()}, daily churn {churn(g['on_pct']):.1%}")
for win, lag in ((26, 4), (13, 4)):
    on = daily_lists(rolling_score(win, lag), decay=True); f, _ = in_time(on)
    print(f"   rolling: last {win} weeks, skipping the most recent {lag}: in time {len(f)}/{len(ins)}, "
          f"normal staff ever listed {(on.any(1) & normal).sum()}, daily churn {churn(on):.1%}")

# ---------------------------------------------------------------- C. how often do roles really change in CERT?
B = "/Users/mehrad/Documents/School/UTD/UTD_as_student/Fall2026/IBM_Z_Datathon_2026"
snaps = sorted(f for f in os.listdir(f"{B}/data/r{REL}/r{REL}/LDAP") if f.endswith(".csv"))
L = {s[:7]: pd.read_csv(f"{B}/data/r{REL}/r{REL}/LDAP/{s}").set_index("user_id") for s in snaps}
months = [m for m in L if m >= CUT.strftime("%Y-%m")]; changed = {"role": set(), "department": set(), "team": set(), "left": set()}
for m0, m1 in zip(sorted(L)[:-1], sorted(L)[1:]):
    if m1 not in months: continue
    a0, a1 = L[m0], L[m1]; both = a0.index.intersection(a1.index)
    for col in ("role", "department", "team"):
        changed[col] |= set(both[(a0.loc[both, col].astype(str) != a1.loc[both, col].astype(str)).values])
    changed["left"] |= set(a0.index.difference(a1.index))
print(f"C  test period ({len(months)} monthly snapshots): staff whose role changed {len(changed['role'])}, department {len(changed['department'])}, "
      f"team {len(changed['team'])}; staff who left {len(changed['left'])} (of whom insiders {len(changed['left'] & set(ins.index))})")

# ---------------------------------------------------------------- D. recommender: retrain monthly or keep the first model?
blocks = pd.date_range(CUT, dom.day.max() + pd.Timedelta(days=1), freq="30D")
nrm = set(users[normal]); res = {"own history only": 0, "recommender trained once": 0, "recommender retrained monthly": 0}
def topk(Xm, own, k=20):
    s = np.where(own, -np.inf, als(Xm) + np.random.default_rng(1).random(Xm.shape) * 1e-9)
    return ((-s).argsort(1).argsort(1) < k) & ~own
first_grant = None
for bi, (s, e) in enumerate(zip(blocks[:-1], blocks[1:])):
    before = dom[dom.day < (TRAIN_END if bi == 0 else s)]
    sites = np.sort(before.domain.unique()); S = {d: j for j, d in enumerate(sites)}
    gb = before.groupby(["user", "domain"]).day.nunique()
    Xm = np.zeros((len(users), len(sites))); Xm[gb.index.get_level_values(0).map(U), gb.index.get_level_values(1).map(S)] = np.log1p(gb.values)
    own = Xm > 0
    grant = topk(Xm, own)
    if first_grant is None: first_grant = {u: {sites[j] for j in np.where(grant[U[u]])[0]} for u in nrm}
    blk = dom[(dom.day >= s) & (dom.day < e) & dom.user.isin(nrm)][["user", "domain"]].drop_duplicates()
    known = blk.domain.isin(S).values; ui = blk.user.map(U).values; si = blk.domain.map(S).fillna(0).astype(int).values
    is_own = known & own[ui, si]; is_new_grant = known & grant[ui, si]
    once = np.array([d in first_grant[u] for u, d in zip(blk.user, blk.domain)])
    res["own history only"] += (~is_own).sum(); res["recommender retrained monthly"] += (~(is_own | is_new_grant)).sum()
    res["recommender trained once"] += (~(is_own | once)).sum()
pm = len(nrm) * (dom.day.max() - CUT).days / 30.44
print("D  access requests per person-month, approved requests kept, own history refreshed each month: "
      + ", ".join(f"{k} {v / pm:.2f}" for k, v in res.items()))
