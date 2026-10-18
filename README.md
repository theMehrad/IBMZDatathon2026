# OutOfRole · The Debugging Table · IBM Z Datathon 2026

OutOfRole catches employees who misuse their access while they are still active, explains each alert with checked evidence (IBM Granite), and advises on access with a recommender, all on one LinuxONE server. In a day-by-day replay of 2,000 employees' logs it caught **80 of 99 insiders while still active**, twice a standard baseline.

## Start here: one handbook

**[`OutOfRole_Handbook.md`](OutOfRole_Handbook.md)** (also as `OutOfRole_Handbook.pdf`, and as one collapsible online page: https://claude.ai/artifact/JoDjs32y8userQWpMLJfyP) holds everything, each topic once:

the project in one minute · the data · what we built · which method runs at each step and where its code is · the baseline · results · how we got here · how we checked them · real-company use · the LLM · the proposal and the final submission text · what we say openly · the event-day plan · FAQ · glossary

## Everything else supports the handbook

| Folder | What is in it | When to use it |
|---|---|---|
| `code/` | `build_tables.py` (Spark: raw logs to three tables), `outofrole_minimal.py` (the whole system, every headline number in about 20 seconds), `case_file.py` (the Granite step), `checks/`, `experiments/` | To run or port the code; run in that order |
| `evidence/` | `Verified_Numbers.md` (every number with its source), `Study_Notebook.ipynb` (the full study), `Research_Sources.md`, `Proposal_As_Submitted_Oct15.md`, `Reviews/` (11 outside review rounds) | To check a number, show the work, or cite a source |
| `setup/` | `LinuxONE_Setup_Guide.pdf`, `Data_Download_Guide.pdf`, `IBM_Lab_Materials/` | Before and during the event |
| `figures/` | The level-by-level visual used in the handbook | Slides and the video |
| `web/` | Source of the online handbook page | Only to republish the page |

## Dashboard

Run `py code/dashboard.py` on Windows or `python3 code/dashboard.py` on Linux, then open http://127.0.0.1:8000. The dashboard reads existing processed tables and Granite runner outputs without starting Spark, scoring, or inference. See [local dashboard instructions](docs/DASHBOARD.md) for existing-run paths, dependencies, sample mode, and data semantics.

## Data

Not in this repo: the CERT license forbids redistribution. Each teammate downloads it (`setup/Data_Download_Guide.pdf`) into `data/`; the LANL real-login data goes in `data/lanl/`. Everything under `data/` is git-ignored. Older drafts live in `9_Archive/` on Mehrad's laptop, outside the repo; review rounds mention files by their names at the time.
