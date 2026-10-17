# Independent check of the least-privilege claim: ALS vs popularity recall@K on normal users' new websites.
import sys, numpy as np, pandas as pd, scipy.sparse as sp
B = "/Users/mehrad/Documents/School/UTD/UTD_as_student/Fall2026/IBM_Z_Datathon_2026/"
rel = sys.argv[1]; cut = pd.Timestamp({"4.2": "2010-06-01", "5.2": "2010-04-01"}[rel])
wk0 = cut - pd.Timedelta(days=cut.weekday())          # Monday of the cutoff week, dropped from training
ins = pd.read_csv(B + "data/answers/answers/insiders.csv"); ins = set(ins[ins.dataset.astype(str) == rel].user)
d = pd.read_parquet(B + f"feasibility/work/r{rel}/dom_pairs"); d["day"] = pd.to_datetime(d.day)
tr = d[d.day < wk0]; te = d[d.day >= cut]
users = sorted(d.user.unique()); items = sorted(tr.domain.unique())
ui = {u: k for k, u in enumerate(users)}; ii = {x: k for k, x in enumerate(items)}
g = tr.groupby(["user", "domain"]).day.nunique().reset_index()
X = sp.csr_matrix((np.log1p(g.day.values), (g.user.map(ui), g.domain.map(ii))), shape=(len(users), len(items)))
own = X > 0
def als(X, f, alpha, reg, iters=12, seed=0):
    rng = np.random.default_rng(seed); U = rng.normal(0, .01, (X.shape[0], f)); V = rng.normal(0, .01, (X.shape[1], f))
    C = X.copy(); C.data = alpha * C.data; Ct = C.T.tocsr()
    def solve(C, Y):
        YtY = Y.T @ Y; out = np.zeros((C.shape[0], f))
        for r in range(C.shape[0]):
            s, e = C.indptr[r], C.indptr[r + 1]; idx = C.indices[s:e]; c = C.data[s:e]
            Yi = Y[idx]; A = YtY + (Yi.T * c) @ Yi + reg * np.eye(f); b = (Yi.T * (1 + c)).sum(1)
            out[r] = np.linalg.solve(A, b)
        return out
    for _ in range(iters): U = solve(C, V); V = solve(Ct, U)
    return U @ V.T
# test: new (user, domain) pairs for normal users; domains unseen in training count as misses
tp = te[te.user.isin(set(users) - ins)][["user", "domain"]].drop_duplicates()
tp = tp[~tp.set_index(["user", "domain"]).index.isin(g.set_index(["user", "domain"]).index)]
known = tp.domain.isin(ii); n_new = len(tp)
pu = tp[known].user.map(ui).values; pi = tp[known].domain.map(ii).values
def recall(S, K):
    S = np.where(own.toarray(), -np.inf, S)
    rk = (-S).argsort(1).argsort(1)                     # 0 = best
    return (rk[pu, pi] < K).sum() / n_new
pop = np.asarray((X > 0).sum(0)).ravel().astype(float); P = np.tile(pop, (len(users), 1)) + np.random.default_rng(1).random((len(users), len(items))) * 1e-6
print(f"r{rel}: users {len(users)}, train domains {len(items)}, new normal pairs {n_new:,} ({known.mean():.1%} on known domains)")
for name, S in [("popularity", P), ("ALS r64 a0.5 reg1 (agent's pick)", als(X, 64, .5, 1.0)), ("ALS r16 a10 reg0.1 (notebook v3)", als(X, 16, 10., .1))]:
    print(f"  {name:34s}" + "  ".join(f"R@{K} {recall(S, K):.3f}" for K in (5, 20, 50)))
