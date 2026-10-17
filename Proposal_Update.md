---
title: "OutOfRole: Updated Proposal"
subtitle: "The Debugging Table · IBM Z Datathon 2026 · Reworded for what our tests showed"
---

# Did the recommender work?

**As the detector, no. In two supporting jobs, yes.**

| Job | Result (r4.2 / r5.2) | Verdict |
|---|---|---|
| Spotting insiders across all attack types | Never beat simple popularity, on any item type | Did not work |
| Live snooping alarm | 9 of 30 snoopers caught in time (r5.2) | Did not work |
| End-of-period snooping review | 27 of 30 snoopers in its top 100, 26 without it | Works, small edge |
| Predicting the access each person will need | 21% / 19% of next new websites, vs 14.5% / 13% for popularity | Works |
| Fewer access requests | 21% / 19% fewer; 28% with monthly retraining | Works |

What actually catches insiders is each person's own normal week: 80 of 99 caught while still active on r5.2, against 40 for a standard baseline.

# The updated proposal, field by field

Each field fits the original form's limits.

**Project:** OutOfRole: early warning for insider misuse, explained by Granite on LinuxONE.

**Problem statement** (173 of 200 characters):
Insiders misuse valid access to leak, steal or snoop. Rules miss them or flood analysts. Teams need early, explained warnings without moving sensitive data off the platform.

**Proposed solution** (179 of 200):
OutOfRole learns each employee's normal week and lists the 20 who drift most each day. Granite on LinuxONE labels each case from checked evidence; a recommender advises on access.

**Audience** (785 of 1,024):
(1) Security analysts: a 20-name daily review list instead of thousands of rule hits. In a day-by-day replay it caught 80 of 99 insiders while still active, twice a standard baseline. (2) Privacy and compliance officers: dated case files that cite their evidence; the AI picks a label and the facts, code writes every sentence, so nothing is invented. (3) Identity and access admins: a Netflix-style recommender predicts the access each person will need (1.45 times better than popularity), cutting access requests by about a fifth, and lists access people stopped using for review. (4) Patients and account holders: monitoring and AI stay on the platform; people appear only as pseudonyms. (5) Organizations running core records on IBM Z: everything runs next to the data on LinuxONE.

**Data and method** (685 of 1,024):
(1) CMU SEI CERT Insider Threat r4.2 and r5.2: synthetic logons, USB, file, web and email logs for 1,000 and 2,000 employees, with an answer key of 70 and 99 insiders used only for grading. (2) Spark builds per-person daily tables; each person's normal weeks are learned from the early months, and the later months are replayed day by day as a live stream. (3) An ALS recommender learns who uses which computers and websites, for snooping reviews and access advice. (4) IBM Granite labels each case from a ranked evidence pack with a fail-closed check. (5) Settings frozen on r4.2, tested unchanged on r5.2; LANL's real authentication logs with red-team labels as an independent check.

# The 30-second pitch

"Malicious insiders were the costliest attack vector in IBM's 2025 breach report, and they hide behind valid logins. OutOfRole learns each employee's normal week and gives analysts a 20-name daily list. In a day-by-day replay of 2,000 employees, it caught 80 of 99 insiders while they were still active, twice a standard baseline. For every alert, IBM Granite on the same LinuxONE server labels the case from checked evidence, and code writes the text, so it cannot invent facts. A Netflix-style recommender keeps access lean, cutting access requests by about a fifth. No data leaves the platform."

# Why this can win

| Judging angle | What we show |
|---|---|
| Real value | A daily list analysts can work through, explained case files for compliance, leaner access for admins |
| Novelty | We measure catching insiders while they are still active, which much published work on this dataset does not report; the AI cannot invent facts; the recommender's job is measured in fewer access requests |
| Technical depth | Per-person anomaly detection, ALS recommender, a constrained LLM, a day-by-day replay with no look-ahead, a resampling check (+27 to +52 insiders on r5.2) |
| LinuxONE and IBM tech | Spark, Granite and the dashboard all on one LinuxONE server; pseudonyms only |
| Credibility | Settings frozen before the test release, an independent validator, 11 outside review rounds, one 253-line program that reproduces every number |

# How to talk about the change from the original abstract

Say it plainly and early, as a strength: "We tested our own idea honestly. The recommender turned out to be a great predictor of what people need, but a weak insider detector, so we used it where it wins (access advice and snooping reviews) and built detection on each person's normal week, which doubled the baseline."

Judges reward a team that tests its own assumptions. They punish one that hides a weak result.

# Three things that would strengthen it at the event

1. **Measure Granite's labels** against the answer key (chance is 1 in 4 on r5.2), so "the AI explains" becomes a number.
2. **Run on LANL's real logs** (already downloaded: 1.05 billion login events, 749 red-team events) to show the approach is not just tuned to synthetic data.
3. **Combine with the baseline for sysadmins:** the baseline catches 8 to 9 of 10 sabotage cases where our list catches 2 to 4. A combined list is a likely quick win; it needs testing.
