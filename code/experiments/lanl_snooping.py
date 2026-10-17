"""LANL transfer test, steps 3 and 4: CERT's frozen snooping review (section 1b) on LANL's real logins.

    VECLIB_MAXIMUM_THREADS=2 /opt/homebrew/opt/python@3.11/bin/python3.11 code/experiments/lanl_snooping.py check
    VECLIB_MAXIMUM_THREADS=2 /opt/homebrew/opt/python@3.11/bin/python3.11 code/experiments/lanl_snooping.py match
    VECLIB_MAXIMUM_THREADS=2 /opt/homebrew/opt/python@3.11/bin/python3.11 code/experiments/lanl_snooping.py run
    VECLIB_MAXIMUM_THREADS=2 /opt/homebrew/opt/python@3.11/bin/python3.11 code/experiments/lanl_snooping.py posthoc

check  label-free: (a) the sparse ALS below gives the same scores as outofrole_minimal.als() on small random
       matrices; (b) next-week new-computer recall@K, ALS vs popularity, on training days only; (c) the
       after-hours window. Never opens redteam.txt.gz. Writes evidence/LANL/check.txt.
match  needs evidence/LANL/PREREG.sha256. One pass over auth.txt.gz that keeps the auth rows at the red-team
       keys (time, source user, source, destination); writes data/cache/lanl/redteam_matched.parquet and
       redteam_auth_rows.parquet (git-ignored).
run    needs PREREG.sha256 and the match output. The pre-registered analysis (evidence/LANL/PREREG.txt):
       M1 snooping review, M2 any new computer, B1 new and rare, B2 count of new computers, random, and the
       optional M3 daily list, at the primary cutoff (day 14) and the sensitivity cutoffs (days 7 and 21),
       on LogOn rows (primary) and on all events (secondary). Writes evidence/LANL/results.txt and results.csv.
posthoc  NOT pre-registered, written after the run: why M1 ranks compromised accounts low, and the same flags
       aggregated without the roamer discount or by distinct computers. Writes evidence/LANL/posthoc.txt.
Every mode also keeps a timestamped copy of its output in evidence/LANL/runs/.
Inputs: data/cache/lanl/*.parquet from lanl_tables.py. Labels (redteam.txt.gz) are used only for grading.
"""
import ast, gzip, hashlib, subprocess, sys, time
import numpy as np, pandas as pd, scipy.sparse as sp
from scipy.stats import hypergeom
from sklearn.metrics import average_precision_score
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[2]
CACHE, EV = BASE / "data/cache/lanl", BASE / "evidence/LANL"
MODE = sys.argv[1]
RANK, ALPHA, REG = 16, 10.0, 0.1            # CERT's frozen computer setting (outofrole_minimal.py section 1b)
SURPRISE, ROAM_W, K = 0.5, 50, 20           # surprise threshold, roamer discount, daily list size
PRIMARY_CUT, CUTS, VARIANTS = 14, [14, 7, 21], ["logon", "all"]
RARE = 0.01                                 # B1: used by under 1% of people in training (CERT's evidence-strength rule)


def als_sparse(X, rank=RANK, alpha=ALPHA, reg=REG, iters=12, seed=0):
    """outofrole_minimal.als() on a CSR matrix: same init, same normal equations, solved in one batch per side."""
    rng = np.random.default_rng(seed); P = rng.normal(0, .01, (X.shape[0], rank)); Q = rng.normal(0, .01, (X.shape[1], rank))
    C = X.tocsr().astype(np.float64); C.eliminate_zeros(); C.data = alpha * C.data; Ct = C.T.tocsr()
    def solve(C, Y):
        YtY = Y.T @ Y; YY = (Y[:, :, None] * Y[:, None, :]).reshape(len(Y), -1)
        A = (C @ YY).reshape(-1, rank, rank) + YtY + reg * np.eye(rank)      # YtY + sum_j c_j y_j y_j' + reg I
        B = C.copy(); B.data = 1 + B.data                                     # b = sum over nonzeros of (1 + c_j) y_j
        return np.linalg.solve(A, (B @ Y)[..., None])[..., 0]
    for _ in range(iters): P = solve(C, Q); Q = solve(Ct, P)
    return P, Q


DEVIATIONS = """Deviations from PREREG.txt: none in the split, person filter, login definition, methods, constants, metrics,
matching rule or decision rule.
Run log (every run kept in evidence/LANL/runs/):
- lanl_tables.py: one full pass, 12.5 min, no failures (a 20M-row test pass ran first and its files were deleted).
- check: run once before hashing (12:19 CDT); ALS equivalence and the recall@K sanity check above.
- match attempt 1 FAILED: `grep -F -f` with 715 patterns stalled (BSD grep) and was killed after 8.7 min, no output.
  Attempt 2 searched the time-sorted stream block by block for the same keys (same matching rule), 55 s.
- run 1 (12:30 CDT) gave every number in section 4. Two print-only edits followed (the M3 line listed its after-hours
  hours wrongly as "0..23 wrapped"; the B0 line now also prints the analytic expectation); run 2 regenerated this file
  with identical numbers. A third print-only edit (account names outside the person filter replaced by counts) first
  failed with a SyntaxError before anything ran; after the fix, run 3 regenerated this file, numbers unchanged.
- posthoc: written after run 1 and labelled as such.
Notes, all as pre-registered: 34 of the 749 red-team rows are exact duplicates (715 distinct keys) and each row counts
as a login; 14 red-team rows have no auth row at their full key and still count (a flag depends only on the account
and the destination); 27 red-team rows from 12 accounts on local computer domains (user@C...) fall outside the person
filter and are not gradable (account names are not printed). Every matched auth row is a successful or failed NTLM network LogOn.
"""

def load():
    people = pd.read_parquet(CACHE / "people.parquet"); dst = pd.read_parquet(CACHE / "dst_pairs.parquet")
    daily = pd.read_parquet(CACHE / "daily.parquet"); hourly = pd.read_parquet(CACHE / "hourly.parquet")
    return people, dst, daily, hourly


def rows_for(dst, variant):
    r = dst if variant == "all" else dst[dst.n_logon > 0]
    return r.assign(w=(r.n if variant == "all" else r.n_logon).astype(np.int64))


def fit(rows, cut, N, ncomp):
    """Everything the review needs from training days < cut. Rows are distinct (person, computer, day)."""
    tr = rows[rows.day < cut]
    g = tr.groupby(["user", "dst"]).size()                                     # distinct training days per pair
    gu, gd = g.index.get_level_values(0).values, g.index.get_level_values(1).values
    comps = np.unique(gd); col = np.full(ncomp, -1, np.int64); col[comps] = np.arange(len(comps))
    X = sp.csr_matrix((np.log1p(g.values.astype(float)), (gu, col[gd])), shape=(N, len(comps)))
    P, Q = als_sparse(X)
    trkey = np.sort(gu.astype(np.int64) << 32 | gd)
    cnt = tr.groupby(["user", "dst"]).size().reset_index(name="c").sort_values(["user", "c", "dst"], ascending=[True, False, True], kind="stable")
    main = cnt.drop_duplicates("user").set_index("user").dst                   # most training days; ties: lowest code
    roam = (tr.dst.values != main.reindex(tr.user.values).values)
    roam = pd.Series(roam).groupby(tr.user.values).mean().reindex(np.arange(N)).fillna(0).values
    users_tr = tr.user.nunique(); share = np.zeros(ncomp); share[g.reset_index().dst.value_counts().index] = g.reset_index().dst.value_counts().values / users_tr
    return dict(P=P, Q=Q, col=col, trkey=trkey, roam=roam, share=share, nnz=X.nnz, ncols=len(comps), users_tr=users_tr)


def pair_flags(m, u, d):
    key = u.astype(np.int64) << 32 | d.astype(np.int64)
    pos = np.searchsorted(m["trkey"], key); pos = np.minimum(pos, len(m["trkey"]) - 1)
    new = (m["trkey"][pos] != key) | (d < 0)
    c = np.where(d >= 0, m["col"][np.maximum(d, 0)], -1); known = c >= 0
    pred = np.zeros(len(u)); pred[known] = (m["P"][u[known]] * m["Q"][c[known]]).sum(1)
    surprise = np.where(known, 1 - np.clip(pred, 0, 1), 1.0)
    return dict(M1=new & (surprise >= SURPRISE), M2=new, B1=new & (np.where(d >= 0, m["share"][np.maximum(d, 0)], 0) < RARE), surprise=surprise)


def review_scores(rows, m, cut, N):
    te = rows[rows.day >= cut]; u, d = te.user.values, te.dst.values
    f = pair_flags(m, u, d); wk = te.day.values.astype(int) // 7
    out = {}
    for name in ["M1", "M2", "B1"]:
        x = pd.DataFrame({"u": u, "wk": wk, "f": f[name]}).groupby(["u", "wk"]).f.any().groupby(level=0).sum()
        s = np.zeros(N); s[x.index.values] = x.values
        out[name] = s / (1 + ROAM_W * m["roam"])
    nd = pd.DataFrame({"u": u[f["M2"]], "d": d[f["M2"]]}).groupby("u").d.nunique()
    s = np.zeros(N); s[nd.index.values] = nd.values; out["B2"] = s
    return out, te, f


def grade(score, pos):
    s = score + np.random.default_rng(2).random(len(score)) * 1e-9            # same jitter as outofrole_minimal.top100
    order = np.argsort(-s, kind="stable")
    hits = {k: int(pos[order[:k]].sum()) for k in (20, 50, 100)}
    return hits, float(average_precision_score(pos, s)), order


def random_ranking(pos, n=2000):
    rng = np.random.default_rng(7); H = {k: [] for k in (20, 50, 100)}; A = []
    for _ in range(n):
        o = rng.permutation(len(pos)); pp = pos[o]
        for k in H: H[k].append(pp[:k].sum())
        r = np.flatnonzero(pp) + 1; A.append(np.mean(np.arange(1, len(r) + 1) / r))
    return {k: float(np.mean(v)) for k, v in H.items()}, float(np.mean(A)), {k: float(np.percentile(v, 95)) for k, v in H.items()}


def after_hours(hourly, cut):
    tot = hourly[hourly.day < cut].groupby("hour").n_events.sum().reindex(range(24)).fillna(0).values
    h0 = int(np.argmax([tot[[(h + i) % 24 for i in range(12)]].sum() for h in range(24)]))
    work = {(h0 + i) % 24 for i in range(12)}
    return sorted(set(range(24)) - work), h0, tot


F9 = ["n_logon", "n_logon_ah", "n_events", "n_events_ah", "n_fail", "n_remote", "n_dst_logon", "n_dst", "n_src"]
def m3_lists(daily, hourly, cut, N, D=58):
    ah, h0, _ = after_hours(hourly, cut)
    hh = hourly[hourly.hour.isin(ah)].groupby(["user", "day"])[["n_events", "n_logon"]].sum().rename(columns=lambda c: c + "_ah").reset_index()
    dd = daily.merge(hh, on=["user", "day"], how="left").fillna({"n_events_ah": 0, "n_logon_ah": 0})
    X = np.zeros((N, D, len(F9))); X[dd.user.values, dd.day.values.astype(int)] = dd[F9].values
    ACT = np.zeros((N, D), bool); ACT[dd.user.values, dd.day.values.astype(int)] = True
    week = np.arange(D) // 7; ref = [w for w in np.unique(week) if np.arange(D)[week == w].max() < cut]
    W = np.stack([X[:, week == w].sum(1) for w in ref], 1); Wact = np.stack([ACT[:, week == w].any(1) for w in ref], 1)
    cs = np.concatenate([np.zeros((N, 1, len(F9))), X.cumsum(1)], 1)
    last7 = np.stack([cs[:, t + 1] - cs[:, max(0, t - 6)] for t in range(cut, D)], 1)
    T = D - cut; score = np.zeros((N, T))
    for i in range(N):
        r = W[i][Wact[i]]
        if len(r):
            p = ((r[None] < last7[i][:, None]).sum(1) + 0.5 * (r[None] == last7[i][:, None]).sum(1)) / len(r)
            score[i] = (p >= 0.99).sum(1) + 0.01 * p.sum(1)
    jit = np.random.default_rng(0).random(N); lam = 0.5 ** (1 / 7); run = np.zeros(N); on = np.zeros((N, T), bool)
    for t in range(T):
        run = lam * run + score[:, t]; cand = np.where(run > 0)[0]
        on[cand[np.lexsort((jit[cand], run[cand]))[::-1]][:K], t] = True
    return on, ah, h0, len(ref)


# ====================================================================== check (label-free)
if MODE == "check":
    lines = []; say = lambda s="": (print(s, flush=True), lines.append(s))
    src = (BASE / "code/outofrole_minimal.py").read_text(); tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "als")
    ns = {"np": np}; exec(compile(ast.Module([fn], []), "outofrole_minimal.als", "exec"), ns)
    say("(a) sparse ALS vs outofrole_minimal.als (rank 16, alpha 10, reg 0.1, 12 iterations, seed 0)")
    rng = np.random.default_rng(11)
    for (n, m, dens) in [(300, 200, 0.05), (500, 120, 0.02), (80, 400, 0.10)]:
        Xd = np.where(rng.random((n, m)) < dens, np.log1p(rng.integers(1, 15, (n, m))), 0.0)
        Xd[rng.integers(0, n, 5)] = 0                                           # some people with no history
        ref = ns["als"](Xd, rank=RANK, alpha=ALPHA, reg=REG); P, Q = als_sparse(sp.csr_matrix(Xd)); mine = P @ Q.T
        flip = ((1 - np.clip(ref, 0, 1)) >= .5) != ((1 - np.clip(mine, 0, 1)) >= .5)
        say(f"    {n}x{m}, density {dens}: max |difference| {np.abs(ref - mine).max():.2e}, surprise>=0.5 flips {int(flip.sum())}")
    people, dst, daily, hourly = load(); N = len(people); ncomp = len(pd.read_parquet(CACHE / "computers.parquet"))
    say(f"\ntables: {N:,} people, {ncomp:,} computers, {len(dst):,} person x destination x day rows, days {int(dst.day.min())}..{int(dst.day.max())}")
    say("\n(b) label-free sanity check: train days 0-6, predict new computers in days 7-13; people with a training row only;")
    say("    a new computer = a (person, computer) pair in days 7-13 not seen in days 0-6; computers unseen in days 0-6 count as misses")
    for variant in VARIANTS:
        rows = rows_for(dst, variant); tr = rows[rows.day < 7]; te = rows[(rows.day >= 7) & (rows.day < 14)]
        g = tr.groupby(["user", "dst"]).size(); gu = g.index.get_level_values(0).values; gd = g.index.get_level_values(1).values
        comps = np.unique(gd); col = np.full(ncomp, -1); col[comps] = np.arange(len(comps))
        X = sp.csr_matrix((np.log1p(g.values.astype(float)), (gu, col[gd])), shape=(N, len(comps)))
        t0 = time.time(); P, Q = als_sparse(X); t_als = time.time() - t0
        hist = np.unique(gu); tp = te[te.user.isin(hist)][["user", "dst"]].drop_duplicates()
        tk = tp.user.values.astype(np.int64) << 32 | tp.dst.values; trk = gu.astype(np.int64) << 32 | gd
        tp = tp[~np.isin(tk, trk)]; known = col[tp.dst.values] >= 0; n_new = len(tp)
        pu, pi = tp.user.values[known], col[tp.dst.values[known]]
        pop = np.asarray((X > 0).sum(0)).ravel().astype(float) + np.random.default_rng(1).random(len(comps)) * 1e-6
        res = {}
        for name in ["popularity", "ALS r16 a10 reg0.1"]:
            hit = {k: 0 for k in (5, 20, 50)}
            by_user = pd.Series(pi).groupby(pu).apply(np.array)
            for b0 in range(0, len(hist), 2000):
                blk = hist[b0:b0 + 2000]
                S = np.tile(pop, (len(blk), 1)) if name == "popularity" else P[blk] @ Q.T
                S[(X[blk] > 0).toarray()] = -np.inf
                rk = (-S).argsort(1).argsort(1)
                for j, uu in enumerate(blk):
                    if uu in by_user.index:
                        r = rk[j, by_user[uu]]
                        for k in hit: hit[k] += int((r < k).sum())
            res[name] = {k: v / n_new for k, v in hit.items()}
        say(f"    {variant:5s} rows: {len(hist):,} people, {len(comps):,} computers, {n_new:,} new pairs ({known.mean():.1%} on computers seen in days 0-6); ALS fit {t_als:.1f}s")
        for name, r in res.items(): say(f"        {name:20s} " + "  ".join(f"R@{k} {v:.3f}" for k, v in r.items()))
    ah, h0, tot = after_hours(hourly, PRIMARY_CUT)
    say(f"\n(c) after-hours window (M3), training days < {PRIMARY_CUT}: busiest 12 hours start at hour {h0}; after hours = {ah}")
    say("    person events by hour of day (training days): " + " ".join(f"{int(x/1e3)}k" for x in tot))
    EV.mkdir(parents=True, exist_ok=True); (EV / "check.txt").write_text(f"lanl_snooping.py check, {time.strftime('%Y-%m-%d %H:%M:%S')}\n" + "\n".join(lines) + "\n")
    (EV / "runs").mkdir(exist_ok=True); (EV / "runs" / f"check_{time.strftime('%Y%m%d_%H%M%S')}.txt").write_text("\n".join(lines) + "\n")
    sys.exit(0)

assert (EV / "PREREG.sha256").exists(), "pre-register first"
want = (EV / "PREREG.sha256").read_text().split()[0]
assert hashlib.sha256((EV / "PREREG.txt").read_bytes()).hexdigest() == want, "PREREG.txt changed after hashing"

# ====================================================================== match (first use of labels)
if MODE == "match":
    rt = pd.read_csv(BASE / "data/lanl/redteam.txt.gz", header=None, names=["time", "user", "src", "dst"])
    # The file is sorted by time, so each block of the stream is searched only for the red-team seconds inside its
    # time range, with a C-level find of "\n<time>,". (Run 1 used `grep -F -f` with 715 patterns; BSD grep stalled
    # at a few MB per minute and was killed after 8.7 min with no output. Same matching rule, faster search.)
    times = np.array(sorted(set(rt.time))); t0 = time.time(); out = []
    proc = subprocess.Popen(["gzcat", str(BASE / "data/lanl/auth.txt.gz")], stdout=subprocess.PIPE, bufsize=1 << 26)
    carry, nblk = b"\n", 0
    while True:
        chunk = proc.stdout.read(1 << 26)
        if not chunk: break
        buf = carry + chunk; cut = buf.rfind(b"\n"); body, carry = buf[:cut], buf[cut:]; nblk += 1
        lo = int(body[1:body.index(b",", 1)]); last = body[body.rfind(b"\n") + 1:]; hi = int(last[:last.index(b",")])
        for t in times[(times >= lo) & (times <= hi)]:
            pre = b"%d," % t; q = body.find(b"\n" + pre)
            while q >= 0:
                e = body.find(b"\n", q + 1); line = body[q + 1:e if e >= 0 else len(body)]
                if not line.startswith(pre): break
                out.append(line.decode()); q = e
        if nblk % 100 == 0: print(f"  block {nblk} (64 MB each), time {hi:,}, {len(out):,} lines at red-team seconds, {time.time() - t0:.0f}s", flush=True)
    assert proc.wait() == 0 and carry.strip() == b"", "stream ended early or the last line was not newline-terminated"
    names = ["time", "src_user", "dst_user", "src_pc", "dst_pc", "auth_type", "logon_type", "orient", "result"]
    a = pd.DataFrame([l.split(",") for l in out], columns=names); a["time"] = a.time.astype(int)
    keys = set(zip(rt.time, rt.user)); a = a[[k in keys for k in zip(a.time, a.src_user)]]
    key = list(zip(rt.time, rt.user, rt.src, rt.dst)); ks = set(key)
    hit = a[[k in ks for k in zip(a.time, a.src_user, a.src_pc, a.dst_pc)]]                 # auth rows at a red-team key (semi-join)
    hit.to_parquet(CACHE / "redteam_auth_rows.parquet", index=False)
    per = hit.groupby(["time", "src_user", "src_pc", "dst_pc"]).size()
    rt["n_auth"] = [int(per.get(k, 0)) for k in key]; rt.to_parquet(CACHE / "redteam_matched.parquet", index=False)
    print(f"match: {len(rt)} red-team rows ({len(ks)} distinct keys), {len(out):,} candidate auth lines, {len(a):,} at an exact (time, user); "
          f"{len(hit):,} auth rows at a full key; red-team rows with >=1 auth row {int((rt.n_auth > 0).sum())}; {time.time() - t0:.0f}s")
    sys.exit(0)

# ====================================================================== posthoc (NOT pre-registered; written after seeing the run)
if MODE == "posthoc":
    lines = []; say = lambda s="": (print(s, flush=True), lines.append(s))
    people, dst, daily, hourly = load(); N = len(people); ncomp = len(pd.read_parquet(CACHE / "computers.parquet"))
    acct = dict(zip(people.account, people.user))
    rt = pd.read_csv(BASE / "data/lanl/redteam.txt.gz", header=None, names=["time", "user", "src", "dst"]); rt["day"] = rt.time // 86400
    rtp = rt[rt.user.isin(acct)]
    say(f"POST HOC diagnostics, {time.strftime('%Y-%m-%d %H:%M:%S')}. Written after the pre-registered run; they explain it and change no verdict.")
    for variant in VARIANTS:
        rows = rows_for(dst, variant)
        for cut in CUTS:
            m = fit(rows, cut, N, ncomp); sc, te, f = review_scores(rows, m, cut, N)
            pos = np.zeros(N, bool); pos[[acct[a] for a in set(rtp.user[rtp.day >= cut])]] = True
            say(f"\n---- {variant} rows, train days 0-{cut - 1} ({int(pos.sum())} positives of {N:,})")
            _, _, order = grade(sc["M1"], pos); rank = np.empty(N, int); rank[order] = np.arange(N)
            act = m["roam"] > 0
            say(f"why M1 fails: its top 100 have mean roam {m['roam'][order[:100]].mean():.3f} (people with one training computer); "
                f"median roam of positives {np.median(m['roam'][pos]):.3f} vs other people with a roam above 0 {np.median(m['roam'][~pos & act]):.3f}; "
                f"median M1 rank of positives {int(np.median(rank[pos])):,} (best {int(rank[pos].min()):,})")
            for name in ["M1", "M2"]:
                wk = np.round(sc[name] * (1 + ROAM_W * m["roam"]))
                say(f"    {name} test weeks with a flagged login, quartiles: positives {np.percentile(wk[pos], [25, 50, 75]).tolist()}, "
                    f"other people with any flag {np.percentile(wk[~pos & (wk > 0)], [25, 50, 75]).tolist()}; people with any flag {int((wk > 0).sum()):,}")
            u, d = te.user.values, te.dst.values
            alt = {"M1 weeks, no roam discount": np.round(sc["M1"] * (1 + ROAM_W * m["roam"])),
                   "M2 weeks, no roam discount": np.round(sc["M2"] * (1 + ROAM_W * m["roam"]))}
            for name, flagname in [("distinct new computers (= B2)", "M2"), ("distinct new AND surprising computers", "M1"),
                                   ("distinct new AND rare computers", "B1")]:
                x = pd.DataFrame({"u": u[f[flagname]], "d": d[f[flagname]]}).groupby("u").d.nunique()
                v = np.zeros(N); v[x.index.values] = x.values; alt[name] = v
            say(f"    {'score':40s} top20 top50 top100     AP")
            for name, v in alt.items():
                h, ap, _ = grade(v, pos); say(f"    {name:40s} {h[20]:5d} {h[50]:5d} {h[100]:6d} {ap:6.4f}")
            if (variant, cut) == ("logon", PRIMARY_CUT):
                ded = rtp[rtp.day >= cut].drop_duplicates(["time", "user", "src", "dst"])
                fr = pair_flags(m, np.array([acct[a] for a in ded.user]), np.array([dict(zip(pd.read_parquet(CACHE / "computers.parquet").name,
                                pd.read_parquet(CACHE / "computers.parquet").pc)).get(c, -1) for c in ded.dst]))
                say(f"    event level with duplicate red-team rows removed: {len(ded)} rows; flagged M1 {int(fr['M1'].sum())}, M2 {int(fr['M2'].sum())}, B1 {int(fr['B1'].sum())}")
    (EV / "posthoc.txt").write_text("\n".join(lines) + "\n")
    (EV / "runs").mkdir(exist_ok=True); (EV / "runs" / f"posthoc_{time.strftime('%Y%m%d_%H%M%S')}.txt").write_text("\n".join(lines) + "\n")
    sys.exit(0)

# ====================================================================== run (pre-registered analysis)
assert MODE == "run"
T0 = time.time(); lines = []; say = lambda s="": (print(s, flush=True), lines.append(s)); csv_rows = []
people, dst, daily, hourly = load(); N = len(people); ncomp = len(pd.read_parquet(CACHE / "computers.parquet"))
acct = dict(zip(people.account, people.user)); comp_code = dict(zip(pd.read_parquet(CACHE / "computers.parquet").name, pd.read_parquet(CACHE / "computers.parquet").pc))
rt = pd.read_csv(BASE / "data/lanl/redteam.txt.gz", header=None, names=["time", "user", "src", "dst"]); rt["day"] = rt.time // 86400
mt = pd.read_parquet(CACHE / "redteam_matched.parquet"); mm = pd.read_parquet(CACHE / "redteam_auth_rows.parquet")
rt["in_people"] = rt.user.isin(acct); local_dom = bool(rt.user[~rt.in_people].str.match(r"^U\d+@C\d+$").all())
say(f"LANL transfer test, run {time.strftime('%Y-%m-%d %H:%M:%S')}; PREREG sha256 {want}")
say(f"universe: {N:,} people (src_user ~ ^U\\d+@DOM\\d+$), {ncomp:,} computers")
say(f"red team: {len(rt)} rows, {rt.user.nunique()} accounts, days {rt.day.min()}..{rt.day.max()}; rows whose account is in the person universe {int(rt.in_people.sum())}"
    f" ({rt[rt.in_people].user.nunique()} accounts); outside it: {int((~rt.in_people).sum())} rows from {rt.user[~rt.in_people].nunique()} accounts, "
    f"all U-accounts on a computer domain (user@C...): {local_dom}")
say(f"matching to auth rows (time, user, source, destination): {int((mt.n_auth > 0).sum())} of {len(rt)} red-team rows matched "
    f"({len(mt) - len(mt.drop_duplicates(['time', 'user', 'src', 'dst']))} duplicate red-team rows); "
    f"{len(mm)} matched auth rows; orientation {mm.orient.value_counts().to_dict()}; auth type {mm.auth_type.value_counts().to_dict()}; "
    f"logon type {mm.logon_type.value_counts().to_dict()}; result {mm.result.value_counts().to_dict()}")
say(f"red-team rows by day: {rt.day.value_counts().sort_index().to_dict()}")

for variant in VARIANTS:
    rows = rows_for(dst, variant)
    for cut in CUTS:
        tag = f"{variant} rows, train days 0-{cut - 1}, test days {cut}-57" + ("  [PRIMARY]" if (variant, cut) == ("logon", PRIMARY_CUT) else "")
        say(f"\n==================== {tag}")
        t0 = time.time(); m = fit(rows, cut, N, ncomp); t_fit = time.time() - t0
        sc, te, f = review_scores(rows, m, cut, N)
        rtp = rt[rt.in_people]; pos_acc = set(rtp.user[rtp.day >= cut]); tr_acc = set(rtp.user[rtp.day < cut])
        pos = np.zeros(N, bool); pos[[acct[a] for a in pos_acc]] = True; P_ = int(pos.sum())
        say(f"ALS: {N:,} x {m['ncols']:,} matrix, {m['nnz']:,} nonzeros, fit {t_fit:.1f}s; people with training rows {m['users_tr']:,}")
        say(f"gradable compromised accounts (red-team rows in the test window): {P_}; of them also red-team in training: {len(pos_acc & tr_acc)}; "
            f"red-team only in training (kept in the ranking as non-positives): {len(tr_acc - pos_acc)}")
        say(f"people with a test row {te.user.nunique():,}; test rows {len(te):,}; flagged rows M1 {int(f['M1'].sum()):,}, M2 {int(f['M2'].sum()):,}, B1 {int(f['B1'].sum()):,}; "
            f"median roam {np.median(m['roam'][m['roam'] > 0]) if (m['roam'] > 0).any() else 0:.3f}")
        rh, rap, r95 = random_ranking(pos)
        say(f"{'method':38s} top20 top50 top100     AP   (positives {P_} of {N:,})")
        say(f"{'B0 random (mean of 2000 rankings)':38s} {rh[20]:5.2f} {rh[50]:5.2f} {rh[100]:6.2f} {rap:6.4f}   (analytic top100 {100 * P_ / N:.2f}; p95 top100 {r95[100]:.0f}; chance AP = P/N = {P_ / N:.4f})")
        csv_rows.append(dict(variant=variant, cut=cut, method="B0 random", positives=P_, people=N, top20=rh[20], top50=rh[50], top100=rh[100], ap=rap))
        res = {}
        for name, label in [("M1", "M1 snooping review (new and surprising)"), ("M2", "M2 any computer new to the person"),
                            ("B1", "B1 new and rare (<1% of people)"), ("B2", "B2 count of distinct new computers")]:
            hits, ap, order = grade(sc[name], pos); res[name] = (hits, ap)
            pv = hypergeom.sf(hits[100] - 1, N, P_, 100)
            say(f"{label:38s} {hits[20]:5d} {hits[50]:5d} {hits[100]:6d} {ap:6.4f}   (top100 hypergeometric p vs random {pv:.1e})")
            csv_rows.append(dict(variant=variant, cut=cut, method=label, positives=P_, people=N, top20=hits[20], top50=hits[50], top100=hits[100], ap=ap, p_top100=pv))
        # ---------------- event level
        rte = rtp[rtp.day >= cut].copy()
        u = np.array([acct[a] for a in rte.user]); d = np.array([comp_code.get(c, -1) for c in rte.dst])
        say(f"red-team test rows whose destination never appears in a person row: {int((d < 0).sum())}")
        fr = pair_flags(m, u, d)
        mv = mm[(mm.time // 86400 >= cut) & mm.src_user.isin(acct)]
        if variant == "logon": mv = mv[mv.orient == "LogOn"]
        mu = np.array([acct[a] for a in mv.src_user], dtype=np.int64); md = np.array([comp_code.get(c, -1) for c in mv.dst_pc], dtype=np.int64)
        fm = pair_flags(m, mu, md) if len(mv) else {k: np.zeros(0, bool) for k in ["M1", "M2", "B1"]}
        w = te.w.values; tot = w.sum() - len(mv)
        say(f"event level: {len(rte)} red-team rows in the test window ({int((~fr['M2']).sum())} on a computer the account used in training); "
            f"other person {'LogOn ' if variant == 'logon' else ''}events in the test window {tot:,}")
        for name in ["M1", "M2", "B1"]:
            s_rt = fr[name].mean(); s_ot = ((w * f[name]).sum() - fm[name].sum()) / tot
            say(f"    {name}: red-team rows flagged {int(fr[name].sum())}/{len(rte)} = {s_rt:.3f}; other events flagged {s_ot:.5f}; lift {s_rt / s_ot if s_ot > 0 else float('inf'):.1f}x")
            csv_rows.append(dict(variant=variant, cut=cut, method=f"event {name}", positives=len(rte), share_redteam=s_rt, share_other=s_ot, lift=s_rt / s_ot if s_ot else np.nan))
        say(f"    red-team rows: median ALS surprise {np.median(fr['surprise']):.3f}; share with surprise >= 0.5 {np.mean(fr['surprise'] >= .5):.3f}")
        # ---------------- decision rule (primary only)
        if (variant, cut) == ("logon", PRIMARY_CUT):
            h1, h2 = res["M1"][0][100], res["M2"][0][100]; exp = 100 * P_ / N; pv = hypergeom.sf(h1 - 1, N, P_, 100)
            beats = h1 >= 5 * exp and pv < 0.001
            verdict = ("TRANSFERS" if beats and h1 >= h2 else "PARTIAL: the novelty signal transfers, the recommender adds nothing over M2" if beats
                       else "DOES NOT TRANSFER")
            say(f"DECISION (pre-registered): M1 top100 {h1} vs random expectation {exp:.2f} (5x = {5 * exp:.2f}), p {pv:.1e}; M2 top100 {h2} -> {verdict}")
            primary_verdict = verdict
        # ---------------- M3 daily list (only on the logon pass; it does not use the pair table)
        if variant == "logon":
            on, ah, h0, nref = m3_lists(daily, hourly, cut, N)
            firsts = rtp[rtp.day >= cut].groupby("user").day.min(); lasts = rtp.groupby("user").day.max()
            ci = cc = 0; ei = ec = 0.0; pk = 20 / N
            for a, F in firsts.items():
                i = acct[a]; L = int(lasts[a]); F = int(F)
                ci += bool(on[i, F - cut:L - cut + 1].any()); cc += bool(on[i, F - cut:L - cut].any())
                ei += 1 - (1 - pk) ** (L - F + 1); ec += 1 - (1 - pk) ** (L - F)
            listed = int(on.any(1).sum())
            say(f"M3 daily list (20 a day, {nref} reference week(s), after hours = hours {ah}, busiest 12-hour block starts at {h0}): "
                f"on the list between first and last red-team day inclusive {ci}/{P_} (random lists {ei:.2f}); CERT rule, before the last red-team day {cc}/{P_} "
                f"(random {ec:.2f}); distinct people ever listed {listed:,}")
            csv_rows.append(dict(variant="activity", cut=cut, method="M3 daily list", positives=P_, people=N, caught_inclusive=ci, caught_cert=cc,
                                 random_inclusive=ei, random_cert=ec))
say(f"\nprimary verdict: {primary_verdict}")
say(f"runtime {(time.time() - T0) / 60:.1f} min")
sec = lambda title, body: f"\n{'#' * 100}\n# {title}\n{'#' * 100}\n{body.rstrip()}\n"
match_log = sorted((EV / "runs").glob("match_attempt*.txt"))
report = (f"OutOfRole LANL transfer test: all numbers. PREREG.txt sha256 {want} (hashed before redteam.txt.gz was opened).\n"
          + sec("1. Table build (lanl_tables.py, label-free)", (CACHE / "build_log.txt").read_text())
          + sec("2. Label-free checks (lanl_snooping.py check, run before hashing)", (EV / "check.txt").read_text())
          + sec("3. Matching red-team rows to auth rows (lanl_snooping.py match, after hashing)", "\n".join(f"[{f.name}]\n" + f.read_text() for f in match_log))
          + sec("4. PRE-REGISTERED ANALYSIS (lanl_snooping.py run)", "\n".join(lines))
          + (sec("5. POST HOC diagnostics (lanl_snooping.py posthoc; NOT pre-registered, change no verdict)", (EV / "posthoc.txt").read_text())
             if (EV / "posthoc.txt").exists() else "")
          + sec("6. Deviations and run log", DEVIATIONS))
(EV / "results.txt").write_text(report); pd.DataFrame(csv_rows).to_csv(EV / "results.csv", index=False)
(EV / "runs").mkdir(exist_ok=True); (EV / "runs" / f"run_{time.strftime('%Y%m%d_%H%M%S')}.txt").write_text("\n".join(lines) + "\n")   # every run kept
