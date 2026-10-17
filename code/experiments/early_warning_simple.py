# Independent re-implementation of the online own-history percentile early warning, plus "share of attack after detection".
import sys, glob, numpy as np, pandas as pd
import pathlib; B = str(pathlib.Path(__file__).resolve().parents[2]) + "/"
rel = sys.argv[1]; K = int(sys.argv[2]) if len(sys.argv) > 2 else 20
cut = pd.Timestamp({"4.2": "2010-06-01", "5.2": "2010-04-01"}[rel]); tr_end = cut - pd.Timedelta(days=cut.weekday())
F = ["n_logon", "n_logon_ah", "n_usb", "n_usb_ah", "n_file", "n_file_ah", "n_http", "n_http_ah", "n_pcs"]
d = pd.read_parquet(B + f"data/cache/r{rel}/daily"); d["day"] = pd.to_datetime(d.day)
days = pd.date_range(d.day.min(), d.day.max()); users = np.sort(d.user.unique())
X = d.set_index(["user", "day"])[F].unstack("day").reindex(index=users)         # wide: (user) x (feat, day)
X = np.stack([X[f].reindex(columns=days).fillna(0).values for f in F], -1)        # (N, D, 9)
act = X[:, :, 0] > 0
# reference: Mon-Sun weekly totals for weeks fully before tr_end, active weeks only
wk = np.array([(x - pd.Timestamp("2009-12-28")).days // 7 for x in days])
ref_weeks = [w for w in np.unique(wk) if days[wk == w].max() < tr_end]
Wt = np.stack([X[:, wk == w].sum(1) for w in ref_weeks], 1)                     # (N, nw, 9)
Wa = np.stack([act[:, wk == w].any(1) for w in ref_weeks], 1)
cs = np.concatenate([np.zeros((len(users), 1, 9)), X.cumsum(1)], 1)
t0 = days.get_loc(cut); T = len(days) - t0
S7 = np.stack([cs[:, t + 1] - cs[:, max(0, t - 6)] for t in range(t0, len(days))], 1)   # trailing 7-day totals (N, T, 9)
score = np.zeros((len(users), T))
for u in range(len(users)):
    r = Wt[u][Wa[u]]
    if len(r) == 0: continue
    less = (r[None, :, :] < S7[u][:, None, :]).sum(1); eq = (r[None, :, :] == S7[u][:, None, :]).sum(1)
    p = (less + 0.5 * eq) / len(r)
    score[u] = (p >= 0.99).sum(1) + 0.01 * p.sum(1)
lam = 0.5 ** (1 / 7); R = np.zeros_like(score); prev = np.zeros(len(users))
for t in range(T): prev = lam * prev + score[:, t]; R[:, t] = prev
rng = np.random.default_rng(0); jit = rng.random(len(users))
ON = np.zeros_like(R, bool)
for t in range(T):
    s = R[:, t]; cand = np.where(s > 0)[0]; o = cand[np.lexsort((jit[cand], s[cand]))[::-1]][:K]; ON[o, t] = True
ins = pd.read_csv(B + "data/answers/answers/insiders.csv"); ins = ins[ins.dataset.astype(str) == rel]
uix = {u: i for i, u in enumerate(users)}; rows = []
for r in ins.itertuples():
    Ft = (pd.Timestamp(r.start).normalize() - cut).days; Lt = (pd.Timestamp(r.end).normalize() - cut).days
    hit = np.where(ON[uix[r.user], Ft:])[0]; D = Ft + hit[0] if len(hit) else None
    f = glob.glob(B + f"data/answers/answers/r{rel}-{r.scenario}/*{r.user}*.csv")[0]
    ev = pd.read_csv(f, header=None, usecols=[2, 3]); ev = pd.to_datetime(ev[ev[3] == r.user][2]).dt.normalize()   # own rows only
    evt = ((ev - cut).dt.days).values
    after = (evt > D).mean() if D is not None else 0.0          # share of malicious events on days after detection
    rows.append(dict(sc=r.scenario, in_time=D is not None and D < Lt, delay=(D - Ft) if D is not None else np.inf,
                     pre=ON[uix[r.user], max(0, Ft - 14):Ft].any(), after=after))
g = pd.DataFrame(rows)
print(f"r{rel} K={K}: in time {g.in_time.sum()}/{len(g)}, fresh in time (not listed 14d before) {(g.in_time & ~g.pre).sum()}, "
      f"median delay {np.median(g.delay):.1f}, share of malicious events after detection day {g.after.mean():.2f}")
print(g.groupby("sc").agg(n=("in_time", "size"), in_time=("in_time", "sum"), med_delay=("delay", "median"), after=("after", "mean")).round(2).to_string())
nrm = ~np.isin(users, ins.user.values)
print(f"normal staff ever listed {ON[nrm].any(1).sum()} of {nrm.sum()}; normal slot share {ON[nrm].sum() / ON.sum():.2f}; weeks {T / 7:.0f}")
