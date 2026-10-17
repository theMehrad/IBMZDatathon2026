# OutOfRole · The Debugging Table · IBM Z Datathon 2026

Track: **AI Secured: Innovation Without Exposure.**

OutOfRole spots insiders while they are still active, explains each alert with checked evidence, and suggests which access each person should keep pre-approved. It runs on one LinuxONE server, and people appear only as pseudonyms.

## Start here

0. **[`OutOfRole_In_Plain_Words.md`](OutOfRole_In_Plain_Words.md)** (also as a PDF): the whole project in three pages, in plain words.
1. **[`Build_Plan.md`](Build_Plan.md)** (also as a PDF): what each person builds, in what order, the cut rules, the demo, and the verified numbers.
2. **[`feasibility/Verified_Numbers.md`](feasibility/Verified_Numbers.md)**: the only source for numbers in any slide, doc or video.
3. **[`Data_Access_Guide.md`](Data_Access_Guide.md)**: how to download CERT r4.2 and r5.2 onto the VM.

## Headline results (CERT, settings frozen on r4.2, then r5.2 run unchanged)

| | r4.2 | r5.2 |
|---|---|---|
| Insiders flagged on a 20-name daily list before their last malicious action | 59 of 70 | 80 of 99 |
| Same, 28-day personal baseline on the same 20-name list | 59 | 40 |
| Insiders flagged in time with a real malicious event in their top 3 evidence items (evidence up to the flag day) | 64% | 85% |
| Recommender recall of next new websites, top 20 (popularity) | 21% (14.5%) | 19% (13%) |
| Snoopers in the top 100 of the end-of-period snooping review (recommender) | no snoopers | 27 of 30 |

## What's in this repo

| Path | What it is |
|---|---|
| `Build_Plan.*` | The build plan for October 17 to 18 |
| `feasibility/OutOfRole_Feasibility.ipynb` (+ `.html`) | The full pre-event study: code, explanations and findings per step |
| `feasibility/reference/outofrole_minimal.py`, `case_file.py` | The whole build in about 300 lines: the daily list, evidence, recommender, access advice, and the Granite reply check. Port these to LinuxONE. |
| `feasibility/reference/` | The scripts behind the verified numbers. They are local reference implementations, and we rewrite them on the event server. Paths inside point to Mehrad's laptop. |
| `feasibility/OutOfRole_Plan.*`, `feasibility/Team_Briefing.*` | Plan with findings per step; teammate explainer |
| `feasibility/codex_review/` | Eight rounds of external review (Codex) and our responses; round 8 verdict: ready for the local build and pitch |
| `Research_Findings.md` | Published work, industry practice, LinuxONE notes, sources |
| `Abstract_Submission.md` | The abstract as submitted |
| `output/` | VM, SSH, Docker, Jupyter and PySpark setup guide (its Chapter 9 is superseded by the build plan) |
| `research/` | IBM lab notebooks and setup references |

## Data

The CERT Insider Threat datasets are **not** in this repo, and must not be added. Their license forbids redistribution. Each teammate downloads them directly (see `Data_Access_Guide.md`). `data/` and the derived Parquet caches under `feasibility/work/` are git-ignored.
