"""Compare extra inputs for the daily list: runs outofrole_email.py once per setting and prints one table.

    python test/compare_features.py 4.2                                   default: the two sysadmin inputs
    python test/compare_features.py 4.2 n_email_out_ah n_new_site,n_boss_pc   any settings; comma = combined
    python test/compare_features.py 4.2 n_new_site,n_boss_pc@2 n_new_site,n_boss_pc@3   "@N" = new inputs worth N points

Use this on r4.2 only (the tuning release). Pick the final email set from this table, then run r5.2 ONCE with it.
Each run takes about as long as one outofrole_email.py run.
"""
import re, subprocess, sys
from pathlib import Path

REL = sys.argv[1]
if REL != "4.2":
    print("Note: the protocol is to choose features on r4.2 and run r5.2 once. Continuing anyway.\n")
SCRIPT = str(Path(__file__).resolve().parent / "outofrole_email.py")
SETTINGS = sys.argv[2:] or ["n_new_site", "n_boss_pc", "n_new_site,n_boss_pc"]
def _args(s):                                    # "a,b@3" = features a and b, new inputs worth 3 points
    f, _, w = s.partition("@")
    return [f"--feats={f}"] + ([f"--w={w}"] if w else [])
RUNS = [("original 9 (team baseline)", ["--no-email"])] + [("+ " + s.replace(",", " + ").replace("@", " @ weight "), _args(s)) for s in SETTINGS]

rows = []
for name, args in RUNS:
    out = subprocess.run([sys.executable, SCRIPT, REL, *args], capture_output=True, text=True)
    if out.returncode != 0:
        print(f"{name}: FAILED\n{out.stderr[-2000:]}"); sys.exit(1)
    t = out.stdout
    caught = re.search(r"20 names/day: (\d+)/(\d+)", t)
    normal = re.search(r"normal staff ever listed (\d+) over", t)
    churn = re.search(r"daily churn ([\d.]+)%", t)
    later = re.search(r"later days: ([\d.]+) averaged", t)
    scen = re.search(r"by scenario, in time: (.*)", t)
    rows.append((name, f"{caught[1]}/{caught[2]}", normal[1], churn[1] + "%", later[1], scen[1] if scen else ""))
    print(f"done: {name}", flush=True)

hdr = ("setting", "insiders in time", "normal staff listed", "churn", "share after flag", "by scenario")
w = [max(len(str(r[i])) for r in rows + [hdr]) for i in range(len(hdr))]
print(f"\n== r{REL}: extra inputs compared ==")
print("  ".join(h.ljust(w[i]) for i, h in enumerate(hdr)))
for r in rows:
    print("  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))
print("\nGood feature: insiders in time stays the same or rises, normal staff listed stays close to the baseline."
      "\n'share after flag' = share of each insider's malicious events after their flag day (higher = caught earlier).")
