import sys, pandas as pd, glob, re
import pathlib; B = str(pathlib.Path(__file__).resolve().parents[2]) + "/"
for rel, cut in (("4.2", "2010-06-01"), ("5.2", "2010-04-01")):
    cut = pd.Timestamp(cut); wk0 = cut - pd.Timedelta(days=cut.weekday())
    ins = pd.read_csv(B + "data/answers/answers/insiders.csv"); ins = ins[ins.dataset.astype(str) == rel]
    d = pd.read_parquet(B + f"data/cache/r{rel}/dom_pairs"); d["day"] = pd.to_datetime(d.day)
    trd = set(d[d.day < wk0].domain); te = d[d.day >= cut]
    nov = te[~te.domain.isin(trd)]
    normal = nov[~nov.user.isin(set(ins.user))]
    print(f"r{rel}: org-novel test domains {nov.domain.nunique()}: {sorted(nov.domain.unique())[:8]}")
    print(f"   normal-user visits to them: {normal[['user', 'day']].drop_duplicates().shape[0]} person-days, {normal.user.nunique()} users")
    # malicious http events per scenario: domain from URL
    for sc in sorted(ins.scenario.unique()):
        rows = []
        for f in glob.glob(B + f"data/answers/answers/r{rel}-{sc}/*.csv"):
            for line in open(f):
                if line.startswith("http") and line.split(",")[3] == f.rsplit("-", 1)[-1][:-4]:   # own rows only
                    m = re.search(r"https?://([^/,]+)", line.split(",", 5)[-1]); rows.append(m.group(1).lower().removeprefix("www.") if m else None)
        if rows:
            s = pd.Series(rows); print(f"   scenario {sc}: {len(s)} malicious http events, {s.isin(trd).mean():.1%} on domains seen in training; top: {s.value_counts().head(3).to_dict()}")
