"""LANL transfer test, step 1: label-free tables from auth.txt.gz in one streaming pass.

    VECLIB_MAXIMUM_THREADS=2 /opt/homebrew/opt/python@3.11/bin/python3.11 code/experiments/lanl_tables.py [--head N]

Reads ONLY data/lanl/auth.txt.gz (never redteam.txt.gz). The file is never decompressed to disk:
`gzcat | grep` streams it, grep keeps the person rows, pandas aggregates them in chunks.

Person filter (fixed before any label was read): the SOURCE user field matches ^U\\d+@DOM\\d+$
(about 31% of rows in a 20M-row sample). Computer accounts (C123$@DOM1), ANONYMOUS LOGON, SYSTEM,
LOCAL SERVICE and the like, and U-accounts on a local or unknown domain (U12@C345, U12@?, 0.4% of
rows) are dropped. The account string user@domain is the person key, as in the red-team file.
Day = time // 86400 (days 0 to 57); hour = (time % 86400) // 3600 (clock offset unknown).

Writes data/cache/lanl/ (git-ignored):
  people.parquet      code -> account (user@domain)
  computers.parquet   code -> computer name (one code space for source and destination)
  dst_pairs.parquet   person x destination computer x day: n (all events), n_logon (orientation LogOn), n_fail
  src_pairs.parquet   person x source computer x day: n, n_logon
  daily.parquet       person x day: n_events, n_logon, n_logoff, n_tgs, n_tgt, n_authmap, n_fail, n_ntlm,
                      n_kerberos, n_network, n_interactive, n_remote (src != dst), n_dst, n_dst_logon, n_src
  hourly.parquet      person x day x hour: n_events, n_logon
  build_log.txt       row counts and runtime
"""
import subprocess, sys, time
import numpy as np, pandas as pd
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[2]
SRC = BASE / "data/lanl/auth.txt.gz"
OUT = BASE / "data/cache/lanl"; OUT.mkdir(parents=True, exist_ok=True)
HEAD = int(sys.argv[sys.argv.index("--head") + 1]) if "--head" in sys.argv else None
CHUNK = 5_000_000
NAMES = ["time", "src_user", "dst_user", "src_pc", "dst_pc", "auth_type", "logon_type", "orient", "result"]
USE = ["time", "src_user", "src_pc", "dst_pc", "auth_type", "logon_type", "orient", "result"]
DT = {"time": np.int32, **{c: "category" for c in USE[1:]}}
PERSON = r"^[0-9]+,U[0-9]+@DOM[0-9]+,"            # first field is time, second the source user
INTERACTIVE = {"Interactive", "RemoteInteractive", "CachedInteractive", "Unlock"}

cmd = f"gzcat '{SRC}'" + (f" | head -n {HEAD}" if HEAD else "") + f" | LC_ALL=C grep -E '{PERSON}'"
proc = subprocess.Popen(["/bin/bash", "-c", cmd], stdout=subprocess.PIPE, bufsize=1 << 24)

people, comps = {}, {}                           # name -> global code, in order of first appearance
def codes(col, table):
    cats = col.cat.categories
    for c in cats:
        if c not in table: table[c] = len(table)
    lut = np.array([table[c] for c in cats], dtype=np.int64)
    return lut[col.cat.codes.values]

def flag(col, values):
    cats = col.cat.categories; hit = np.array([c in values for c in cats])
    return hit[col.cat.codes.values] if len(cats) else np.zeros(len(col), bool)

parts = {"dst": [], "src": [], "daily": [], "hourly": []}
t_start = time.time(); n_rows = 0; last_print = 0
reader = pd.read_csv(proc.stdout, header=None, names=NAMES, usecols=USE, dtype=DT, chunksize=CHUNK, engine="c")
for ch in reader:
    u = codes(ch.src_user, people); s = codes(ch.src_pc, comps); d = codes(ch.dst_pc, comps)
    t = ch.time.values.astype(np.int64); day = t // 86400; hour = (t % 86400) // 3600
    logon = flag(ch.orient, {"LogOn"}); fail = flag(ch.result, {"Fail"})
    one = np.ones(len(ch), np.int32)
    kd = (u << 40) | (d << 8) | day
    parts["dst"].append(pd.DataFrame({"k": kd, "n": one, "n_logon": logon.astype(np.int32), "n_fail": fail.astype(np.int32)})
                        .groupby("k", sort=False).sum())
    ks = (u << 40) | (s << 8) | day
    parts["src"].append(pd.DataFrame({"k": ks, "n": one, "n_logon": logon.astype(np.int32)}).groupby("k", sort=False).sum())
    kh = (u << 16) | (day << 8) | hour
    parts["hourly"].append(pd.DataFrame({"k": kh, "n_events": one, "n_logon": logon.astype(np.int32)}).groupby("k", sort=False).sum())
    ku = (u << 8) | day
    parts["daily"].append(pd.DataFrame({
        "k": ku, "n_events": one, "n_logon": logon, "n_logoff": flag(ch.orient, {"LogOff"}),
        "n_tgs": flag(ch.orient, {"TGS"}), "n_tgt": flag(ch.orient, {"TGT"}), "n_authmap": flag(ch.orient, {"AuthMap"}),
        "n_fail": fail, "n_ntlm": flag(ch.auth_type, {"NTLM"}), "n_kerberos": flag(ch.auth_type, {"Kerberos"}),
        "n_network": flag(ch.logon_type, {"Network"}), "n_interactive": flag(ch.logon_type, INTERACTIVE),
        "n_remote": s != d}).astype({c: np.int32 for c in ["n_logon", "n_logoff", "n_tgs", "n_tgt", "n_authmap", "n_fail",
                                                            "n_ntlm", "n_kerberos", "n_network", "n_interactive", "n_remote"]})
        .groupby("k", sort=False).sum())
    n_rows += len(ch)
    if time.time() - last_print > 60 or len(ch) < CHUNK:
        last_print = time.time(); el = last_print - t_start
        print(f"[{el/60:6.1f} min] person rows {n_rows/1e6:8.1f}M, day {int(day.max())}, people {len(people)}, "
              f"computers {len(comps)}, {n_rows/el/1e6:.2f}M rows/s", flush=True)
        for kname in parts:                       # fold partials so memory stays flat
            if len(parts[kname]) > 8: parts[kname] = [pd.concat(parts[kname]).groupby(level=0).sum()]
rc = proc.wait()
assert rc in (0, 1), f"stream failed with exit code {rc}"   # grep exits 1 only when nothing matched

def fold(name): return pd.concat(parts[name]).groupby(level=0).sum()
dst = fold("dst"); k = dst.index.values.astype(np.int64)
dst = dst.reset_index(drop=True).assign(user=(k >> 40).astype(np.int32), dst=((k >> 8) & 0xFFFFFFFF).astype(np.int32),
                                        day=(k & 0xFF).astype(np.int8))[["user", "dst", "day", "n", "n_logon", "n_fail"]]
src = fold("src"); k = src.index.values.astype(np.int64)
src = src.reset_index(drop=True).assign(user=(k >> 40).astype(np.int32), src=((k >> 8) & 0xFFFFFFFF).astype(np.int32),
                                        day=(k & 0xFF).astype(np.int8))[["user", "src", "day", "n", "n_logon"]]
hourly = fold("hourly"); k = hourly.index.values.astype(np.int64)
hourly = hourly.reset_index(drop=True).assign(user=(k >> 16).astype(np.int32), day=((k >> 8) & 0xFF).astype(np.int8),
                                              hour=(k & 0xFF).astype(np.int8))[["user", "day", "hour", "n_events", "n_logon"]]
daily = fold("daily"); k = daily.index.values.astype(np.int64)
cols = list(daily.columns)
daily = daily.reset_index(drop=True).assign(user=(k >> 8).astype(np.int32), day=(k & 0xFF).astype(np.int8))[["user", "day"] + cols]
distinct = pd.DataFrame({
    "n_dst": dst.groupby(["user", "day"]).size(),
    "n_dst_logon": dst[dst.n_logon > 0].groupby(["user", "day"]).size(),
    "n_src": src.groupby(["user", "day"]).size()}).fillna(0).astype(np.int32).reset_index()
daily = daily.merge(distinct, on=["user", "day"], how="left")
for c in ["n_dst", "n_dst_logon", "n_src"]: daily[c] = daily[c].fillna(0).astype(np.int32)
for f in [dst, src, hourly, daily]: f.sort_values([c for c in ["user", "day", "dst", "src", "hour"] if c in f.columns], inplace=True)

suffix = f"_head{HEAD}" if HEAD else ""
pd.DataFrame({"user": np.arange(len(people), dtype=np.int32), "account": list(people)}).to_parquet(OUT / f"people{suffix}.parquet")
pd.DataFrame({"pc": np.arange(len(comps), dtype=np.int32), "name": list(comps)}).to_parquet(OUT / f"computers{suffix}.parquet")
for name, f in [("dst_pairs", dst), ("src_pairs", src), ("hourly", hourly), ("daily", daily)]:
    f.to_parquet(OUT / f"{name}{suffix}.parquet", index=False, compression="zstd")
el = time.time() - t_start
log = (f"lanl_tables.py{' --head ' + str(HEAD) if HEAD else ''}: finished {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
       f"person rows (src_user ~ ^U\\d+@DOM\\d+$): {n_rows:,}; people {len(people):,}; computers {len(comps):,}\n"
       f"dst_pairs {len(dst):,} rows; src_pairs {len(src):,}; daily {len(daily):,}; hourly {len(hourly):,}\n"
       f"sum n over dst_pairs {int(dst.n.sum()):,} (must equal person rows); days {int(daily.day.min())}..{int(daily.day.max())}\n"
       f"runtime {el/60:.1f} min\n")
assert int(dst.n.sum()) == n_rows == int(daily.n_events.sum())
(OUT / f"build_log{suffix}.txt").write_text(log); print(log)
