"""
Evidence localization experiment (CERT r4.2 / r5.2).

QUESTION: when an analyst opens one person, do the top few evidence items under a scorer turn out to be the
answer key's malicious events? Does a collaborative-filtering (CF) surprise score localize them better than
simpler scorers?

=====================  PRE-REGISTRATION (written before any result was computed)  =====================
Split. Train = days before the Monday of the week containing the cutoff (r4.2 cutoff 2010-06-01 -> train < 2010-05-31,
       r5.2 cutoff 2010-04-01 -> train < 2010-03-29). The cutoff week is dropped. Test = days from the following Monday
       (r4.2 >= 2010-06-07, r5.2 >= 2010-04-05). All models and statistics see train only. The answer key is used for
       grading only. LDAP / departure data is never read.
Evidence items (one person's test period): (day, computer) logons [pc_pairs], (day, site) visits [dom_pairs],
       (day, USB) days with a USB connect, (day, after-hours) days with an after-hours logon (before 7:00 or from 19:00).
Malicious item: the insider's own answer-key rows (user == insider) matched exactly: logon row -> (day, pc) item and,
       if a Logon row is after hours, the (day, after-hours) item; http row -> (day, URL domain) item; device row ->
       (day, USB) item. email/file rows have no item and are not matchable.
Scorers (higher = more suspicious):
   NOV      naive novelty, frozen: 1 if the person never used the item in train
   NOV1st   naive novelty, first occurrence: 1 only on the first test day the person uses an item absent from train
   RARE     global rarity: 1 - share of staff who used the item in train (unseen item = 1)
   ALS      recommender surprise: 1 - clip(ALS affinity, 0, 1); one model for computers (+ USB, after-hours
            pseudo-items), one for sites. PRIMARY = TUNED setting (coordinator update, received before any result):
            numpy Hu-Koren-Volinsky ALS on log1p(distinct days), 12 iterations, seed 7; sites rank 64, alpha 0.5,
            reg 1.0; computers r4.2 rank 16, alpha 10, reg 0.1 and r5.2 rank 4, alpha 0.5, reg 0.1 (picked label-free by
            a sibling experiment on the last train month's new pairs). ALS_v3 = the study's Spark MLlib setting (rank 16,
            alpha 10, reg 0.1, maxIter 10, ratings log1p(count)), reported alongside.
   ALSPEER  ALS peer-of-item (study version): 1 - max cosine between the person's ALS vector and the item's train users
            (tuned model; ALSPEER_v3 on the study model)
   KNNPEER  peer-of-item: 1 - share of the person's k=20 most similar users (cosine on binary train usage, all items)
            who used the item in train; 0 if the person used it
   ITEMKNN  item-kNN surprise: 1 - max cosine (over train users) between the item and any item the person used in train
   C1       simple combination, no CF: new to the person first, then by rarity (2*NOV + RARE)
   C2       novelty-gated recommender: 2*NOV + ALS
   AGREE    agreement filter (coordinator request, added before results): cite an item only if it is in the person's top
            20% by RARE and top 20% by ALSPEER (average-rank percentile > 0.8); ranking = cited first, each tier by RARE.
            Also reported "strict": only cited items count, empty slots stay empty.
Ties: every metric is the expected value when tied scores are ordered at random.
Metrics per person, then macro-averaged over insiders with >= 1 matchable malicious item (also per scenario):
   hit@1, hit@3, P@5, rank of first malicious item (median across insiders), misleading rate (share of the person's
   malicious items ranked in the bottom half of their own items; coordinator request), within-person AUC.
PRIMARY METRIC: hit@3, macro over insiders with a matchable item.
PRIMARY COMPARISON: ALS (the proposal's literal "would not recommend" score) versus RARE, NOV and NOV1st.
   ALS (tuned) is declared "better" only if its hit@3 minus the comparator's is > 0 with a paired bootstrap 95% CI (2000
   resamples of insiders) that excludes 0 on BOTH r4.2 and r5.2. Secondary: best CF-based scorer (ALS, ALSPEER,
   KNNPEER, ITEMKNN, C2, AGREE) versus best non-CF scorer (NOV, NOV1st, RARE, C1) by hit@3.
Analyst view: the same metrics for insiders inside the top 100 of a label-free person ranking (weekly own-history
   percentiles: most counts in one test week above everything in the person's train weeks, tie-broken by the sum of
   percentiles in the most unusual week), plus the evidence profile of the flagged normal staff.
Tuning: none. Every setting above is fixed in advance; r4.2 runs first, r5.2 runs with identical code.
Robustness (not used for the verdict): ALS-based scorers re-run with ALS seeds 11 and 23.
POST HOC (added after seeing r4.2, before running r5.2; not part of the verdict): ALSRAW = unclipped -affinity
   (items unseen in train ranked first), because clip(.,0,1) ties every negative affinity at surprise 1.
Note: the tuned computer setting differs by release because the sibling picked it on each release's own train data
   without labels; nothing here was tuned on test data or labels.
=========================================================================================================
Usage: python3.11 evidence_localization.py 4.2|5.2
"""
import csv, glob, os, re, sys, time
import numpy as np
import pandas as pd
from scipy.stats import rankdata

REL = sys.argv[1]
BASE = "/Users/mehrad/Documents/School/UTD/UTD_as_student/Fall2026/IBM_Z_Datathon_2026"
ANS = f"{BASE}/data/answers/answers"
WORK = f"{BASE}/data/cache/r{REL}"
OUT = os.path.dirname(os.path.abspath(__file__))
CUT = pd.Timestamp({"4.2": "2010-06-01", "5.2": "2010-04-01"}[REL])
TRAIN_END = CUT - pd.Timedelta(days=CUT.weekday())          # Monday of the cutoff week (exclusive)
TEST_START = TRAIN_END + pd.Timedelta(days=7)                # following Monday (inclusive)
K_PEER, TOP_PEOPLE, SEED, NBOOT = 20, 100, 7, 2000
DOMRE = re.compile(r"^https?://(?:www\.)?([^/:]+)")
F9 = ["n_logon", "n_logon_ah", "n_usb", "n_usb_ah", "n_file", "n_file_ah", "n_http", "n_http_ah", "n_pcs"]
USB, AH = "<USB>", "<AH>"
T0 = time.time()
LOG = open(f"{OUT}/results_r{REL}.txt", "w")


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s); LOG.write(s + "\n"); LOG.flush()


say(f"r{REL}: train < {TRAIN_END.date()}, test >= {TEST_START.date()} (cutoff week dropped)")

# ---------------- answer key (grading only) ----------------
ins = pd.read_csv(f"{ANS}/insiders.csv")
ins = ins[ins.dataset.astype(str) == REL]
SCEN = dict(zip(ins.user, ins.scenario))
rows = []
for f in sorted(glob.glob(f"{ANS}/r{REL}-*/*.csv")):
    who = os.path.basename(f)[:-4].split("-")[-1]
    with open(f, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.reader(fh):
            if r[3] != who:
                continue
            rows.append((who, r[0], pd.Timestamp(pd.to_datetime(r[2], format="%m/%d/%Y %H:%M:%S")), r[4], r[5] if len(r) > 5 else ""))
ev = pd.DataFrame(rows, columns=["user", "type", "ts", "pc", "x"])
ev["day"] = ev.ts.dt.normalize()
mal = set()
for u, t, ts, pc, x, day in ev.itertuples(index=False):
    if t == "logon":
        mal.add((u, day, "pc", pc))
        if x == "Logon" and (ts.hour < 7 or ts.hour >= 19):
            mal.add((u, day, "ah", AH))
    elif t == "http":
        m = DOMRE.match(x)
        if m:
            mal.add((u, day, "dom", m.group(1).lower()))
    elif t == "device":
        mal.add((u, day, "usb", USB))
say(f"answer-key rows of insiders: {len(ev)}, earliest {ev.ts.min()}, rows before test start: {(ev.day < TEST_START).sum()}")

# ---------------- caches ----------------
daily = pd.read_parquet(f"{WORK}/daily"); daily["day"] = pd.to_datetime(daily["day"])
pcs = pd.read_parquet(f"{WORK}/pc_pairs"); pcs["day"] = pd.to_datetime(pcs["day"])
dom = pd.read_parquet(f"{WORK}/dom_pairs"); dom["day"] = pd.to_datetime(dom["day"])
for d in (daily, pcs, dom):
    d["user"] = d["user"].astype(str)
pcs["pc"] = pcs.pc.astype(str); dom["domain"] = dom.domain.astype(str)
USERS = sorted(daily.user.unique()); UIDX = {u: i for i, u in enumerate(USERS)}; N = len(USERS)
tr_d, te_d = daily[daily.day < TRAIN_END], daily[daily.day >= TEST_START]
tr_pc, te_pc = pcs[pcs.day < TRAIN_END], pcs[pcs.day >= TEST_START]
tr_dom, te_dom = dom[dom.day < TRAIN_END], dom[dom.day >= TEST_START]
say(f"staff {N}, insiders {len(SCEN)}, load {time.time() - T0:.0f}s")

# ---------------- label-free person ranking (weekly own-history percentiles) ----------------
wk = daily.assign(week=daily.day.dt.to_period("W").dt.start_time).groupby(["user", "week"])[F9].sum().reset_index()
wtr, wte = wk[wk.week + pd.Timedelta(days=6) < TRAIN_END], wk[wk.week >= TEST_START].copy()
ref = {u: g[F9].values for u, g in wtr.groupby("user")}
P = np.zeros((len(wte), len(F9)))
for i, (u, row) in enumerate(zip(wte.user.values, wte[F9].values)):
    r = ref.get(u)
    if r is not None and len(r):
        P[i] = ((r < row).sum(axis=0) + 0.5 * (r == row).sum(axis=0)) / len(r)
wte["ps"], wte["ph"] = P.sum(axis=1), (P >= 0.99).sum(axis=1)
pr = wte.groupby("user").agg(hi=("ph", "max"), mx=("ps", "max")).reindex(USERS).fillna(0)
pr = pr.sample(frac=1, random_state=SEED).sort_values(["hi", "mx"], ascending=False, kind="mergesort")
TOP = list(pr.index[:TOP_PEOPLE])
say(f"person ranking: insiders in top {TOP_PEOPLE}: {sum(u in SCEN for u in TOP)} "
    f"({', '.join(f'S{s}:{sum(SCEN.get(u) == s for u in TOP)}' for s in sorted(set(SCEN.values())))})")

EVAL = sorted(set(SCEN) | set(TOP))

# ---------------- train usage matrices ----------------
pc_cnt = tr_pc.groupby(["user", "pc"]).size().rename("c").reset_index().rename(columns={"pc": "item"})
usb_cnt = tr_d[tr_d.n_usb > 0].groupby("user").size().rename("c").reset_index().assign(item=USB)
ah_cnt = tr_d[tr_d.n_logon_ah > 0].groupby("user").size().rename("c").reset_index().assign(item=AH)
SPACE = {"pc": pd.concat([pc_cnt, usb_cnt, ah_cnt], ignore_index=True),
         "dom": tr_dom.groupby(["user", "domain"]).n.sum().rename("c").reset_index().rename(columns={"domain": "item"})}
SPACE_DAYS = {"pc": SPACE["pc"],
              "dom": tr_dom.groupby(["user", "domain"]).size().rename("c").reset_index().rename(columns={"domain": "item"})}
TUNED = {"dom": (64, 0.5, 1.0), "pc": {"4.2": (16, 10.0, 0.1), "5.2": (4, 0.5, 0.1)}[REL]}
IIDX, BIN = {}, {}
for sp, cnt in SPACE.items():
    items = sorted(cnt.item.unique()); IIDX[sp] = {v: i for i, v in enumerate(items)}
    B = np.zeros((N, len(items)), np.float32)
    B[cnt.user.map(UIDX).values, cnt.item.map(IIDX[sp]).values] = 1
    BIN[sp] = B
    say(f"space {sp}: {len(items)} items, {len(cnt)} train pairs")

# ---------------- ALS (Spark MLlib, as in the study) ----------------
from pyspark.sql import SparkSession
from pyspark.ml.recommendation import ALS

spark = (SparkSession.builder.master("local[4]").appName("evidence-localization")
         .config("spark.driver.memory", "6g").config("spark.sql.shuffle.partitions", "16")
         .config("spark.ui.showConsoleProgress", "false").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")


def als_numpy(sp, seed, iters=12):
    """Hu-Koren-Volinsky implicit ALS (as in the sibling's lp_experiment.als_implicit). c = alpha * log1p(days)."""
    from scipy.sparse import csr_matrix
    rank, alpha, reg = TUNED[sp]; cnt = SPACE_DAYS[sp]
    C = csr_matrix((alpha * np.log1p(cnt.c.values.astype(float)), (cnt.user.map(UIDX).values, cnt.item.map(IIDX[sp]).values)),
                   shape=(N, len(IIDX[sp])))
    Ct = C.T.tocsr(); rng = np.random.default_rng(seed)
    U = rng.normal(0, 0.01, (C.shape[0], rank)); V = rng.normal(0, 0.01, (C.shape[1], rank)); I = reg * np.eye(rank)

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
    return U, V


def train_als(sp, seed):
    cnt = SPACE[sp]
    sdf = spark.createDataFrame(pd.DataFrame({"u": cnt.user.map(UIDX).astype(int), "i": cnt.item.map(IIDX[sp]).astype(int),
                                              "r": np.log1p(cnt.c).astype(float)}))
    m = ALS(userCol="u", itemCol="i", ratingCol="r", implicitPrefs=True, alpha=10.0, rank=16, regParam=0.1,
            maxIter=10, seed=seed).fit(sdf)
    U = np.zeros((N, 16)); V = np.zeros((len(IIDX[sp]), 16))
    for r in m.userFactors.collect(): U[r.id] = r.features
    for r in m.itemFactors.collect(): V[r.id] = r.features
    return U, V


# ---------------- evidence items for evaluated people ----------------
ev_set = set(EVAL)
it = pd.concat([
    te_pc[te_pc.user.isin(ev_set)].assign(kind="pc", sp="pc").rename(columns={"pc": "item"})[["user", "day", "kind", "sp", "item"]],
    te_dom[te_dom.user.isin(ev_set)].assign(kind="dom", sp="dom").rename(columns={"domain": "item"})[["user", "day", "kind", "sp", "item"]],
    te_d[(te_d.n_usb > 0) & te_d.user.isin(ev_set)].assign(kind="usb", sp="pc", item=USB)[["user", "day", "kind", "sp", "item"]],
    te_d[(te_d.n_logon_ah > 0) & te_d.user.isin(ev_set)].assign(kind="ah", sp="pc", item=AH)[["user", "day", "kind", "sp", "item"]],
], ignore_index=True).drop_duplicates(["user", "day", "kind", "item"]).reset_index(drop=True)
it["mal"] = [(u, d, k, i) in mal for u, d, k, i in zip(it.user, it.day, it.kind, it.item)]
n_mal_key = len([m for m in mal if m[1] >= TEST_START])
say(f"evidence items: {len(it):,} for {len(EVAL)} people; malicious items matched {it.mal.sum()} of {n_mal_key} key-derived items")

it["u"] = it.user.map(UIDX).values
it["ii"] = -1
for sp in ("pc", "dom"):
    msk = it.sp == sp
    it.loc[msk, "ii"] = it.loc[msk, "item"].map(IIDX[sp]).fillna(-1).astype(int).values
known = it.ii.values >= 0


def lookup(mats):
    """mats[sp] = (users x items) matrix restricted to rows EVAL order -> per-item value; unknown items get NaN"""
    out = np.full(len(it), np.nan)
    for sp in ("pc", "dom"):
        msk = (it.sp.values == sp) & known
        out[msk] = mats[sp][it.u.values[msk], it.ii.values[msk]]
    return out


used = np.nan_to_num(lookup(BIN), nan=0.0)
S = {}
S["NOV"] = 1.0 - used
first = it.groupby(["user", "kind", "item"]).day.transform("min")
S["NOV1st"] = ((used == 0) & (it.day.values == first.values)).astype(float)
pop = {sp: BIN[sp].sum(axis=0) / N for sp in BIN}
S["RARE"] = np.where(known, 1.0 - np.nan_to_num(lookup({sp: np.broadcast_to(pop[sp], BIN[sp].shape) for sp in BIN}), nan=0.0), 1.0)

# user kNN peer-of-item on joint binary usage
J = np.hstack([BIN["pc"], BIN["dom"]]); Jn = J / (np.linalg.norm(J, axis=1, keepdims=True) + 1e-9)
eval_u = sorted(it.u.unique())
KP = {sp: np.zeros_like(BIN[sp]) for sp in BIN}
for u in eval_u:
    sim = Jn @ Jn[u]; sim[u] = -np.inf
    if np.linalg.norm(J[u]) == 0:
        continue                                                   # no train history: no peers
    nb = np.argpartition(-sim, K_PEER)[:K_PEER]
    for sp in BIN:
        KP[sp][u] = BIN[sp][nb].mean(axis=0)
S["KNNPEER"] = np.where(used > 0, 0.0, 1.0 - np.nan_to_num(lookup(KP), nan=0.0))

# item kNN: max cosine between the item and the person's train items (same space)
IK = {sp: np.zeros_like(BIN[sp]) for sp in BIN}
for sp in BIN:
    B = BIN[sp]; Bn = B / (np.linalg.norm(B, axis=0, keepdims=True) + 1e-9)
    Sim = Bn.T @ Bn
    for u in eval_u:
        mine = np.flatnonzero(B[u])
        if len(mine):
            IK[sp][u] = Sim[:, mine].max(axis=1)
S["ITEMKNN"] = 1.0 - np.nan_to_num(lookup(IK), nan=0.0)


def als_scores(seed, kind="tuned"):
    pred, peer = {}, {}
    for sp in BIN:
        U, V = als_numpy(sp, seed) if kind == "tuned" else train_als(sp, seed)
        pred[sp] = np.zeros_like(BIN[sp]); peer[sp] = np.zeros_like(BIN[sp])
        Un = U / (np.linalg.norm(U, axis=1, keepdims=True) + 1e-9)
        vis = BIN[sp].T > 0                                        # items x users
        for u in eval_u:
            pred[sp][u] = V @ U[u]
            s = Un @ Un[u]
            peer[sp][u] = np.where(vis, s[None, :], -np.inf).max(axis=1)
    lp = lookup(pred)
    a = 1.0 - np.clip(np.nan_to_num(lp, nan=0.0), 0, 1)       # unseen item: affinity 0 -> surprise 1
    p = np.where(known, 1.0 - np.nan_to_num(lookup(peer), nan=0.0), 1.0)
    raw = np.where(known, -np.nan_to_num(lp, nan=0.0), 1e9)    # post hoc: unclipped
    return a, np.clip(p, 0, None), raw


def within_pct(x):
    return pd.Series(x).groupby(it.user.values).rank(method="average", pct=True).values


def add_cf(Sd, a, p, raw, tag=""):
    Sd["ALS" + tag], Sd["ALSPEER" + tag], Sd["ALSRAW" + tag] = a, p, raw
    Sd["C2" + tag] = 2 * Sd["NOV"] + a
    cited = (within_pct(Sd["RARE"]) > 0.8) & (within_pct(p) > 0.8)
    Sd["AGREE" + tag] = 2 * cited + Sd["RARE"]
    return cited


S["C1"] = 2 * S["NOV"] + S["RARE"]
a, p, raw = als_scores(SEED, "tuned")
CITED = add_cf(S, a, p, raw)
a, p, raw = als_scores(SEED, "v3")
CITED_V3 = add_cf(S, a, p, raw, "_v3")
ORDER = ["NOV", "NOV1st", "RARE", "C1", "ALS", "ALSPEER", "KNNPEER", "ITEMKNN", "C2", "AGREE",
         "ALS_v3", "ALSPEER_v3", "C2_v3", "AGREE_v3", "ALSRAW", "ALSRAW_v3"]
_ins = it.user.isin(set(SCEN)).values
say(f"clip ties: share of insider items at ALS surprise exactly 1: tuned {np.mean(S['ALS'][_ins] == 1):.3f}, "
    f"v3 {np.mean(S['ALS_v3'][_ins] == 1):.3f}; share with RARE exactly 1: {np.mean(S['RARE'][_ins] == 1):.4f}")
CF = ["ALS", "ALSPEER", "KNNPEER", "ITEMKNN", "C2", "AGREE", "ALS_v3", "ALSPEER_v3", "C2_v3", "AGREE_v3"]
say(f"scoring done {time.time() - T0:.0f}s")


# ---------------- tie-aware per-person metrics ----------------
def person_metrics(s, m, kinds=None):
    n = len(s); out = {"n": n, "n_mal": int(m.sum())}
    if n == 0 or m.sum() == 0:
        return out
    order = np.argsort(-s, kind="mergesort"); ss, mm = s[order], m[order]
    st = np.r_[0, np.flatnonzero(ss[1:] != ss[:-1]) + 1]; T = np.diff(np.r_[st, n]); gm = np.add.reduceat(mm.astype(int), st)
    above = np.r_[0, np.cumsum(gm)[:-1]]; end = st + T

    def at_k(k):
        k = min(k, n); g = np.searchsorted(end, k, side="left"); r = k - st[g]
        if above[g] > 0:
            hit = 1.0
        elif gm[g] == 0 or r == 0:
            hit = 0.0
        else:
            hit = 1.0 if T[g] - gm[g] < r else 1.0 - np.prod((T[g] - gm[g] - np.arange(r)) / (T[g] - np.arange(r)))
        return hit, above[g] + r * gm[g] / T[g]

    out["hit1"] = at_k(1)[0]; out["hit3"] = at_k(3)[0]; out["p5"] = at_k(5)[1] / 5
    g0 = np.flatnonzero(gm > 0)[0]; out["first"] = st[g0] + (T[g0] + 1) / (gm[g0] + 1)
    lo = (n + 1) // 2 + 1                                          # bottom-half positions: lo..n
    fg = np.maximum(0, end - np.maximum(st + 1, lo) + 1) / T          # share of each tie block in the bottom half
    f_item = np.empty(n); f_item[order] = np.repeat(fg, T)
    out["mislead"] = f_item[m].mean()
    nb = n - m.sum()
    out["auc"] = (rankdata(s)[m].sum() - m.sum() * (m.sum() + 1) / 2) / (m.sum() * nb) if nb else np.nan
    if kinds is not None:
        for k in ("pc", "dom", "usb", "ah"):
            mk = m & (kinds == k)
            out[f"mis_{k}"] = f_item[mk].mean() if mk.any() else np.nan
    return out


def strict_metrics(s, m, cited):
    sub = person_metrics(s[cited], m[cited])
    return {"hit3_strict": sub.get("hit3", 0.0), "p5_strict": sub.get("p5", 0.0) * min(5, cited.sum()) / 5 if cited.sum() else 0.0,
            "cited": int(cited.sum()), "mal_cited_share": (m & cited).sum() / m.sum() if m.sum() else np.nan}


groups = {u: idx for u, idx in it.groupby("user").indices.items()}
recs = []
for u in EVAL:
    idx = groups.get(u, np.array([], int)); m = it.mal.values[idx]; kinds = it.kind.values[idx]
    for name in ORDER:
        r = {"user": u, "scen": SCEN.get(u, 0), "in_top": u in TOP, "scorer": name, **person_metrics(S[name][idx], m, kinds)}
        if name.startswith("AGREE"):
            r.update(strict_metrics(S[name][idx], m, (CITED if name == "AGREE" else CITED_V3)[idx]))
        recs.append(r)
R = pd.DataFrame(recs)
R.to_csv(f"{OUT}/per_person_r{REL}.csv", index=False)

COLS = ["hit1", "hit3", "p5", "first", "mislead", "auc"]


def summarize(df, label):
    g = df.groupby("scorer")
    t = pd.DataFrame({"hit@1": g.hit1.mean(), "hit@3": g.hit3.mean(), "P@5": g.p5.mean(), "medFirstRank": g["first"].median(),
                      "mislead": g.mislead.mean(), "withinAUC": g.auc.mean()}).reindex(ORDER).round(3)
    say(f"\n--- {label} (people with a matchable malicious item: {df.user.nunique()}) ---")
    say(t.to_string())
    return t


matchable = R[(R.n_mal > 0) & (R.scen > 0)]
say(f"\ninsiders: {len(SCEN)}; with >= 1 matchable malicious item: {matchable.user.nunique()} "
    f"(by scenario: {matchable.groupby('scen').user.nunique().to_dict()}); median items per insider "
    f"{int(R[(R.scen > 0) & (R.scorer == 'NOV')].n.median())}")
summ = {"all": summarize(matchable, f"r{REL} ALL INSIDERS")}
for sc in sorted(matchable.scen.unique()):
    summ[f"S{sc}"] = summarize(matchable[matchable.scen == sc], f"r{REL} scenario {sc}")

# misleading rate by item kind
mk = matchable.groupby("scorer")[["mis_pc", "mis_dom", "mis_usb", "mis_ah"]].mean().reindex(ORDER).round(3)
say("\n--- misleading rate by item kind (share of malicious items of that kind in the bottom half), all insiders ---")
say(mk.to_string())
for sc in sorted(matchable.scen.unique()):
    say(f"scenario {sc}: " + "; ".join(f"{s}: " + ", ".join(f"{k[4:]}={v:.2f}" for k, v in row.items() if pd.notna(v))
                                       for s, row in matchable[matchable.scen == sc].groupby("scorer")[["mis_pc", "mis_dom", "mis_usb", "mis_ah"]].mean().reindex(ORDER).iterrows()))

# explicit check: logon items of scenario-4 snoopers (r5.2) / scenario-3 (supervisor PC)
for sc in (3, 4):
    sel = it[(it.user.map(SCEN) == sc) & (it.kind == "pc")]
    if not sel.mal.any():
        continue
    say(f"\n--- scenario {sc}: computer-logon items only (event-level, within person) ---")
    rr = []
    for name in ORDER:
        vals = []
        for u, g in sel.groupby("user"):
            pm = person_metrics(S[name][g.index.values], g.mal.values)
            if pm["n_mal"]:
                vals.append(pm)
        d = pd.DataFrame(vals)
        rr.append({"scorer": name, "people": len(d), "withinAUC(logons)": d.auc.mean(), "mislead(logons)": d.mislead.mean(),
                   "hit@3(logons)": d.hit3.mean()})
    say(pd.DataFrame(rr).set_index("scorer").round(3).to_string())
    m_ = sel.mal.values
    say(f"pooled logon items: malicious {m_.sum()}, benign {(~m_).sum()}; malicious new-to-person share {S['NOV'][sel.index][m_].mean():.2f}, "
        f"mean ALS surprise malicious {S['ALS'][sel.index][m_].mean():.3f} vs benign {S['ALS'][sel.index][~m_].mean():.3f}; "
        f"mean RARE malicious {S['RARE'][sel.index][m_].mean():.3f} vs benign {S['RARE'][sel.index][~m_].mean():.3f}")

# diagnostic: pooled AUC among NEW-to-person computer logons of all evaluated people (insiders + flagged staff)
newlog = it[(it.kind == "pc") & (S["NOV"] == 1)]
for sc in (3, 4):
    y = (newlog.mal & (newlog.user.map(SCEN) == sc)).values
    keep = y | ~newlog.mal.values
    if y.sum() == 0:
        continue
    yy = y[keep]
    say(f"\n--- scenario {sc}: malicious new logons ({yy.sum()}) vs all benign new logons of evaluated people ({(~yy).sum()}), pooled AUC ---")
    say(", ".join(f"{n_} {(rankdata(S[n_][newlog.index.values][keep])[yy].sum() - yy.sum() * (yy.sum() + 1) / 2) / (yy.sum() * (~yy).sum()):.3f}"
                  for n_ in ORDER))

# AGREE filter detail
for agn in ("AGREE", "AGREE_v3"):
  ag = matchable[matchable.scorer == agn]
  say(f"\n--- {agn} filter, insiders: strict hit@3 {ag.hit3_strict.mean():.3f}, strict P@5 {ag.p5_strict.mean():.3f}, "
    f"share of malicious items cited {ag.mal_cited_share.mean():.3f}, median cited items {ag.cited.median():.0f} ---")
  for sc in sorted(ag.scen.unique()):
    a_ = ag[ag.scen == sc]
    say(f"  scenario {sc}: strict hit@3 {a_.hit3_strict.mean():.3f}, strict P@5 {a_.p5_strict.mean():.3f}, malicious cited {a_.mal_cited_share.mean():.3f}")

# ---------------- primary comparison: paired bootstrap ----------------
rng = np.random.default_rng(SEED)
H = matchable.pivot(index="user", columns="scorer", values="hit3")
say("\n--- PRIMARY: hit@3 difference, paired bootstrap 95% CI over insiders ---")
bidx = rng.integers(0, len(H), size=(NBOOT, len(H)))
for a_, b_ in [("ALS", "RARE"), ("ALS", "NOV"), ("ALS", "NOV1st"), ("ALS", "C1"), ("AGREE", "RARE"), ("C2", "C1"),
               ("ALS_v3", "RARE"), ("ALS_v3", "NOV"), ("ALS", "ALS_v3"), ("ALSRAW", "RARE"), ("ALSRAW_v3", "RARE"), ("ALSRAW", "NOV"), ("ALSRAW", "C1")]:
    d = (H[a_] - H[b_]).values; bs = d[bidx].mean(axis=1)
    say(f"{a_} - {b_}: {d.mean():+.3f}  CI [{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}]")
best_cf = summ["all"].loc[CF, "hit@3"].idxmax(); best_ncf = summ["all"].loc[["NOV", "NOV1st", "RARE", "C1"], "hit@3"].idxmax()
d = (H[best_cf] - H[best_ncf]).values; bs = d[bidx].mean(axis=1)
say(f"SECONDARY best CF ({best_cf}) - best non-CF ({best_ncf}): {d.mean():+.3f}  CI [{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}]")

# ---------------- analyst view: top-100 flagged people ----------------
tm = matchable[matchable.in_top]
if len(tm):
    summarize(tm, f"r{REL} TOP-{TOP_PEOPLE} FLAGGED INSIDERS")
    say("by scenario (hit@3 / P@5 / mislead): " + "; ".join(
        f"S{sc} n={g.user.nunique()}: " + ", ".join(f"{s} {r.hit3:.2f}/{r.p5:.2f}/{r.mislead:.2f}" for s, r in g.groupby("scorer")[["hit3", "p5", "mislead"]].mean().reindex(["RARE", "NOV", "C1", "ALS", "AGREE", "ALS_v3"]).iterrows())
        for sc, g in tm.groupby("scen")))
top_norm = [u for u in TOP if u not in SCEN]; top_ins = [u for u in TOP if u in SCEN]
say(f"\n--- top {TOP_PEOPLE}: {len(top_ins)} insiders, {len(top_norm)} normal staff ---")
prof = []
for name in ORDER:
    mx = {u: (np.sort(S[name][groups[u]])[::-1][:3].mean() if u in groups else 0.0) for u in TOP}
    y = np.array([u in SCEN for u in TOP]); v = np.array([mx[u] for u in TOP])
    auc = (rankdata(v)[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()) if 0 < y.sum() < len(y) else np.nan
    kinds = pd.Series(np.concatenate([it.kind.values[groups[u]][np.argsort(-S[name][groups[u]], kind="mergesort")[:3]] for u in top_norm if u in groups]))
    prof.append({"scorer": name, "AUC top3-mean score, insider vs normal (within top100)": round(auc, 3),
                 **{f"normal top3 share {k}": round((kinds == k).mean(), 2) for k in ("pc", "dom", "usb", "ah")}})
say(pd.DataFrame(prof).set_index("scorer").to_string())
sub = [u for u in TOP if SCEN.get(u) != 1]; y = np.array([u in SCEN for u in sub])
if 0 < y.sum() < len(y):
    say(f"same AUC without scenario-1 insiders ({y.sum()} insiders vs {(~y).sum()} normal): " + ", ".join(
        f"{n_} {(rankdata(np.array([np.sort(S[n_][groups[u]])[::-1][:3].mean() if u in groups else 0.0 for u in sub]))[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()):.3f}"
        for n_ in ORDER))
note = "(top-3 kind shares use stable order within ties, so tie-heavy scorers show ID-order artifacts)"
say(note)
for agn, cm in (("AGREE", CITED), ("AGREE_v3", CITED_V3)):
  ci = {u: int(cm[groups[u]].sum()) if u in groups else 0 for u in TOP}
  for lab_, grp in (("insiders", top_ins), ("normal staff", top_norm)):
    c_ = np.array([ci[u] for u in grp])
    if len(c_):
        say(f"{agn} cited items, {lab_}: zero cited {np.mean(c_ == 0):.2f}, median {np.median(c_):.0f}, IQR {np.percentile(c_, 25):.0f}-{np.percentile(c_, 75):.0f}")
rare_cnt = {u: int(((S["RARE"][groups[u]] >= 0.99) & (S["NOV"][groups[u]] == 1)).sum()) if u in groups else 0 for u in TOP}
for lab_, grp in (("insiders", top_ins), ("normal staff", top_norm)):
    c_ = np.array([rare_cnt[u] for u in grp])
    if len(c_):
        say(f"reference, items new to the person AND used by <1% of staff in train, {lab_}: zero {np.mean(c_ == 0):.2f}, median {np.median(c_):.0f}")

# ---------------- robustness: other ALS seeds ----------------
say("\n--- robustness: ALS seeds (hit@3 / P@5 / mislead, all matchable insiders) ---")
mi = matchable.user.unique()
for sd in (SEED, 11, 23):
    Sd = dict(S)
    if sd != SEED:
        a2, p2, r2 = als_scores(sd, "tuned"); add_cf(Sd, a2, p2, r2)
        a2, p2, r2 = als_scores(sd, "v3"); add_cf(Sd, a2, p2, r2, "_v3")
    vals = {n_: [] for n_ in ("ALS", "ALSPEER", "C2", "AGREE", "ALS_v3", "ALSPEER_v3", "ALSRAW", "ALSRAW_v3")}
    for u in mi:
        idx = groups[u]; m = it.mal.values[idx]
        for n_ in vals:
            pm = person_metrics(Sd[n_][idx], m); vals[n_].append((pm["hit3"], pm["p5"], pm["mislead"]))
    say(f"seed {sd}: " + "; ".join(f"{n_} " + "/".join(f"{x:.3f}" for x in np.mean(v, axis=0)) for n_, v in vals.items()))

spark.stop()
say(f"\ndone in {time.time() - T0:.0f}s")
