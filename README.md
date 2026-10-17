# OutOfRole · The Debugging Table · IBM Z Datathon 2026

OutOfRole catches employees who misuse their access while they are still active, explains each alert with checked evidence (IBM Granite), and advises on access with a recommender. It runs on one LinuxONE server.

**Headline:** in a day-by-day replay of 2,000 employees' logs, a 20-name daily list caught **80 of 99 insiders while still active**, twice a standard baseline (40).

## Which file do I need?

| I want to... | Open | Form |
|---|---|---|
| Understand the project in 5 minutes | `1_Read_First/OutOfRole_Summary.pdf` | 3 pages |
| Understand everything: methods, results, checks, FAQ | `1_Read_First/OutOfRole_Team_Guide.pdf`, or the Team Guide page (online, collapsible) | 11 pages |
| Know what I build at the event, and when | `2_Event_Day/Build_Plan.pdf`, or the Build Plan page | 6 pages |
| Set up the VM and download the data | `2_Event_Day/LinuxONE_Setup_Guide.pdf` and `2_Event_Day/Data_Download_Guide.pdf` | guides |
| Do the two IBM labs (Granite, AI on Z) | `2_Event_Day/IBM_Lab_Materials/` | notebooks |
| Write the final submission or the pitch | `3_Submission/Proposal_Final_Wording.pdf` | 2 pages |
| See what we originally submitted | `3_Submission/Proposal_As_Submitted_Oct15.md` | 1 page |
| Run the code | `4_Code/` (see "The code" below) | Python |
| Check a number before quoting it | `5_Evidence/Verified_Numbers.md` | every number with its source |
| Read the full study with code and outputs | `5_Evidence/Study_Notebook.ipynb` (GitHub shows it) | notebook |
| See how the study evolved and why | `5_Evidence/Study_Report.pdf` | 5 pages |
| Find a published source or real-world case | `5_Evidence/Research_Sources.md` | list |
| See the outside reviews | `5_Evidence/Reviews/` (11 rounds) | Markdown |

## The online pages

These are private claude.ai pages. Share each one from its Share menu before sending the link.

| Page | Use it for | Link |
|---|---|---|
| **OutOfRole Team Guide** | Start here: the whole project, collapsible, with FAQ | https://claude.ai/artifact/JoDjs32y8userQWpMLJfyP |
| **OutOfRole Build Plan** | Event day: roles, hours, cut rules, demo | https://claude.ai/artifact/R2z3vjiUdhJJm1J4hGszDC |
| **OutOfRole Deep Dive** | Optional: interactive simulators and the full method catalog | https://claude.ai/artifact/1doUJaccJU4xsBGJbHcx4L |

Their source files are in `6_Web_Pages/`.

## The code

Run in this order (Python 3.11 with pandas, numpy, scipy and pyspark; Java 17 for Spark):

| Step | File | What it does | Part of the project |
|---|---|---|---|
| 0 | `4_Code/build_tables.py 4.2` | Spark turns the raw logs into three tables in `data/cache/` | Data |
| 1 | `4_Code/outofrole_minimal.py 4.2` | The whole system; prints every headline number in about 20 seconds | Daily list (lines 43 to 94), snooping review (97 to 122), evidence ranking (124 to 186), recommender and access advice (188 to 215), new-site rule (217 to 221) |
| 2 | `4_Code/case_file.py` | The Granite step: evidence pack, prompt, reply check, fallback; runs a self-test | Case files |
| optional | `4_Code/checks/followup_checks.py 4.2` | Resampling, rolling baseline, role changes, monthly retraining | Robustness |
| reference | `4_Code/experiments/` | The original study scripts behind the evidence | Evidence |

The same methods, with explanations, are in the notebook: Step 1 (tables), Step 3 (baseline), Steps 10 and 19 (daily list), Step 13 (snooping), Steps 16 and 17 (recommender and access), Step 18 (evidence), and Part 3 (the one-file run).

## Data

Not in this repo: the CERT license forbids redistribution. Each teammate downloads it (`2_Event_Day/Data_Download_Guide.pdf`) into `data/`. The LANL dataset (real login logs with red-team labels) goes in `data/lanl/`. Everything under `data/` is git-ignored.

## Folder map

| Folder | Holds |
|---|---|
| `1_Read_First/` | The summary and the team guide |
| `2_Event_Day/` | Build plan, setup and data guides, IBM lab materials |
| `3_Submission/` | The proposal as submitted and the final wording |
| `4_Code/` | The build code, checks and study experiments |
| `5_Evidence/` | Verified numbers, study report, notebook, sources, reviews |
| `6_Web_Pages/` | Sources of the three online pages |

Older drafts and setup scraps live in `9_Archive/` on Mehrad's laptop and are not in the repo. Review rounds 1 to 11 mention files by their names at the time; the table above gives today's names.
