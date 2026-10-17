**Round 7 items: all fixed.**

| Item | Fixed? | Evidence |
|---|---|---|
| Free-text note loophole | **Yes** | Exactly two keys accepted; no note ([case_file.py:44](reference/case_file.py#L44)). |
| Malformed-value crashes | **Yes** | Types checked before processing ([lines 47–51](reference/case_file.py#L47)). |
| Ranked evidence preserved; metric separated from Granite | **Yes** | Top three always displayed ([line 57](reference/case_file.py#L57)); metric explicitly labelled ([Plain Words:30](OutOfRole_In_Plain_Words.md#L30)). |
| Holdout wording and insider denominator | **Yes** | Corrected at [lines 40](OutOfRole_In_Plain_Words.md#L40) and [72](OutOfRole_In_Plain_Words.md#L72). |
| Access-review proxy wording and regenerated output | **Yes** | Correct console wording ([minimal:211](reference/outofrole_minimal.py#L211)); Part 3 matches the saved output. |

**Remaining problems:** none blocking found in the four requested files. Both scripts compile. Direct validator checks passed all 12 supplied bad replies, 144 additional type combinations, and ranked-display, weak-evidence and empty-case checks. Part 3’s numerical and case-file outputs match the saved output, ignoring blank lines; both subprocesses retain `check=True`.

The numerical review uses the supplied outputs; raw CERT was not rerun here. Granite label accuracy remains unmeasured, and the evidence figures remain pre-Granite, tie-averaged ranking results.

**Verdict: ready** for the local build and pitch.

**Event-day items:** verify s390x dependencies and VM runtime; integrate Granite and exercise its fallback; run the complete Spark → scoring → case-file → dashboard flow on LinuxONE.