# Verified numbers (source of truth, October 17, 2026)

Every document, slide and page must quote only numbers from this file. Each number was produced by the named script and re-run, in most cases by independent code. CERT protocol throughout:

- train before the cutoff (r4.2: 2010-06-01; r5.2: 2010-04-01), with the cutoff week dropped
- labels used only for grading; departures never used
- settings frozen on r4.2, then r5.2 run unchanged

Scripts are in `feasibility/reference/`.

## 1. Early warning (day-by-day replay, no look-ahead)

Method: own-history weekly percentile (the last 7 days vs each of the person's training weeks), a running score that halves every 7 days, and a daily list of the top 20. Scripts: `early_warning_full.py` (pre-registered study) and `early_warning_simple.py` (independent reimplementation; same counts).

| Measure | r4.2 (70 insiders) | r5.2 (99 insiders) |
|---|---|---|
| On the list before their last malicious action ("in time") | 59 (0.843) | 80 (0.808) |
| Same, not already listed in the 14 days before their first malicious action | 38 | 67 |
| In time, 28-day personal baseline (R2) | 33 (0.471) | 28 (0.283) |
| In time, chance (random normal employee's list history), mean / p95 | 0.038 (about 3) / 0.071 | 0.029 (about 3) / 0.061 |
| In time, pre-registered fusion (c, max of family tails) | 0.86 | 0.545 (54) |
| Median delay from first malicious day, days | 1 | 9 |
| Share of each insider's malicious events dated after the flag day (mean) | 0.54 | 0.48 |
| New names per week (analyst load) | 4.8 | 5.3 |
| Normal staff ever listed | 230 of 930 | 291 of 1,901 |
| Share of list slots held by normal staff | 0.60 | 0.63 |

By scenario, in time / median delay in days:

- **r4.2:** S1 leakers 25/30, 0 days; S2 job-hunters 30/30, 11 days; S3 sysadmins 4/10, 1 day.
- **r5.2:** S1 26/29, 0 days; S2 27/30, 21.5 days; S3 2/10, 2 days; S4 snoopers 25/30, 21.5 days.

The primary comparison was pre-registered as fusion (c) vs R2. It passed on both releases (McNemar p < 0.001). The percentile method (b) was chosen as the headline after seeing the results.

**Caveats:**

- 25 of 30 (r4.2) and 24 of 29 (r5.2) S1 leakers show unlabelled after-hours USB activity in the week before their labelled start.
- Insiders make up 5 to 7% of staff, which is unrealistically high.

## 2. Evidence ranking for the case files

Script: `evidence_ranking.py`. Metric: hit@3, meaning at least one answer-key malicious item is among the person's top 3 ranked items.

| Rule | r4.2 | r5.2 |
|---|---|---|
| "New to this person, rarest first" (C1), top-100 flagged insiders | 0.98 | 0.98 |
| C1, all insiders | 0.68 | 0.92 |
| Global rarity only, all insiders | 0.57 | 0.66 |
| Tuned ALS surprise, all insiders | 0.71 | 0.44 |
| Misleading rate (malicious item in the bottom half), C1, all insiders | 0.07 | 0.02 |

**Other findings:**

- The agreement filter (rare AND recommender-surprising) collapses to C1.
- For flagged normal staff, every rule always cites something. Granite therefore needs a weak-evidence flag.

## 3. The recommender's own job: predicting legitimate new websites (normal staff)

Scripts: `recommender_als_simple.py` (independent check) and `least_privilege_full.py`.

| Recall of next new websites | r4.2 | r5.2 |
|---|---|---|
| Popularity, top 5 / 20 / 50 | 0.037 / 0.145 / 0.303 | 0.034 / 0.130 / 0.274 |
| ALS, label-free tuned (rank 64, alpha 0.5, reg 1.0, log1p days, numpy), top 5 / 20 / 50 | 0.073 / 0.211 / 0.386 | 0.062 / 0.190 / 0.356 |
| ALS, v3 notebook setting (rank 16, alpha 10, reg 0.1), top 5 / 20 / 50 | 0.031 / 0.126 / 0.315 | 0.031 / 0.121 / 0.294 |

The v3 notebook's statement that the recommender is "at the popularity baseline on its own job" came from untuned settings, and is superseded.

## 4. Least-privilege advisor (websites, normal staff)

Script: `least_privilege_full.py`.

| Policy | Requests per person-month (r4.2 / r5.2) | Malicious web events needing approval (r4.2 / r5.2) |
|---|---|---|
| Own history only | 2.31 / 3.07 | 71.0% / 87.5% |
| Pre-approve popularity top 20 | 1.97 / 2.67 | 65.5% / 83.7% |
| Pre-approve ALS top 20 | 1.82 / 2.48 | 69.0% / 86.8% |

**New-to-company site rule** (`org_novel_sites.py`): block any site that nobody visited during training.

- **Coverage:** it blocks 100% of S1 wikileaks visits (69 on r4.2, 65 on r5.2) and S3 keylogger-site visits (53, 38).
- **Normal-staff cost:** 8 person-days across 5 people on r4.2, and none on r5.2.
- **S2 job sites:** these were all visited by someone during training, so the rule does not touch them.

**Computers:** no recommender benefit. 93 to 96% of new computers are colleagues' personal PCs, and every method recalls 8% or less.

## 5. Ideas tested and dropped

- **Analyst-feedback re-weighting** (AAD, Das et al. 2016): 57 vs 55 insiders found at 100 reviews (r4.2), and 42 vs 43 (r5.2). Across 40 subsamples the gain is +0.2 ± 0.9 and +0.1 ± 1.0. With job-hunters hidden, it still finds 22 of 30, against 4 to 7 for trained combiners.
- **Recommender as a detector** (site, site × hour, computer × hour, email recipients, sequences, peer groups): no gain over popularity. Site × hour popularity raises r5.2 web novelty from 11.4 to 26.0 expected hits in the top 70, but popularity alone gets that gain. (These runs used the v3 ALS setting; a tuned rerun is pending.)
- **Recommender as explanation evidence:** C1 beats it (section 2).

## 6. Retrospective ranking (v3 notebook, unchanged)

- Own-history percentile: P@20 1.00 on both releases.
- Frozen family-first Stouffer, insiders found in 100 reviews: 55 vs 44 for R2 (r4.2), 43 vs 39 (r5.2).
- Out-of-role persistence view: 27 to 30 of 30 snoopers in the top 100 (r5.2).

## 7. Step ladder: the number at each step and the improvement

Use this table wherever steps are listed: the notebook, the plan, the briefing and the explainer page.

- **Steps 3 to 15** quote the v3 notebook outputs (`scratchpad/v3_outputs.txt`, the executed v3 notebook).
- **Steps 16 to 20** quote sections 1 to 5 above.
- **"found"** = expected insiders in the top 70 (hits@70).
- **"Change"** is measured against the reference named in the row.

| Step | What we tried | Metric | Before (reference) | After | Change | Verdict |
|---|---|---|---|---|---|---|
| 3 | Personal baselines | found, r4.2 / r5.2 | (none) | R2 28-day window: 38 / 36; P@20 1.00 / 0.90 | (the bar to beat) | Baseline |
| 4 | Novelty: rare sites; recommender site surprise | found, r4.2 | R2 38 | Rare sites 41 (r5.2: 8.1); ALS site surprise 5 (AUC 0.71) | Rare +3 on r4.2 but does not transfer; ALS -33 | Rare kept as one family |
| 5 | Learned combiner | found, r4.2 | Behaviour + rare 39 | + naive novelty 41; + ALS 45 (other seeds 44, 45) | +6 | Stress test needed |
| 6 | More signals, second model | found, r4.2 | LR all signals 45 | + ALS 49; gradient boosting 60 | +4; +15 | Needs the unseen-attack test |
| 7 | Hide job-hunters from training | job-hunters in top 100 | (none) | Boosting 4; LR 5 to 7; label-free sum 16 of 30 | Label-free +9 to +12 over trained | Don't headline trained models |
| 8 | Literature: weekly LOF | job-hunters in top 100 | R2 5 of 30 | Weekly LOF 12 to 13 of 30 | +7 to +8 | Slow-drift family |
| 9 | Recommender tweaks | found, r4.2 | ALS site surprise 5 | Site peer-of-item 17 (AUC 0.84) | +12 | Candidate only |
| 10 | Own-history weekly percentile | found / AP, r4.2 | R2 38 / 0.728 | 39.4 / 0.666; P@20 1.00 | +1.4 found | Core detector |
| 11 | Label-free family-first Stouffer | found / AP, r4.2 | R2 38 / 0.728 | 45 / 0.784; all-detector Stouffer 39 | +7 | Frozen for r5.2 |
| 12 | r5.2, pipeline frozen | found / AP, r5.2 | R2 36 / 0.428 | Stouffer 38 / 0.478; percentile AP 0.477 | +2 found | Survives |
| 13 | Snooper signal | snoopers in top 100, r5.2 | Naive new computers 10.9 of 30 | Weekly persistence + roaming discount 27 of 30 (ownership, naive and ALS alike) | +16 | Persistence, not ALS |
| 14 | Equal budget, 100 reviews | insiders found, r4.2 / r5.2 | R2 44 / 39 | Stouffer 55 / 43; four queues 42 / 53 | Stouffer +11 / +4 | Fusion as default |
| 15 | Recommender at its own job (untuned) | MPR, lower is better, r4.2 | Popularity 35.5 | ALS 35.9 | Worse by 0.4 | Superseded by Step 16 |
| 16 | Recommender, tuned without labels | recall@20 of next new sites, r4.2 / r5.2 | Popularity 0.145 / 0.130; v3 setting 0.126 / 0.121 | 0.211 / 0.190 | +0.066 / +0.060 over popularity (1.45x) | Real job found |
| 17 | Least-privilege advisor | requests per person-month, r4.2 / r5.2 | Own history 2.31 / 3.07 | ALS top 20: 1.82 / 2.48 (popularity: 1.97 / 2.67) | -21% / -19% at about the same protection (71.0% to 69.0%; 87.5% to 86.8%) | Build (R4) |
| 17b | New-to-company site rule | wikileaks + keylogger visits blocked | (none) | 100% (r4.2 and r5.2) | Cost: 8 person-days on r4.2, 0 on r5.2 | Build (R4) |
| 18 | Evidence ranking for Granite | hit@3, top-100 flagged insiders, r4.2 / r5.2 | Rarity 0.93 / 0.89 | C1 "new to you, rarest first" 0.98 / 0.98 (tuned ALS, all insiders: 0.71 / 0.44) | +0.05 / +0.09 | Build (R3) |
| 19 | Early warning, day-by-day replay | insiders listed before last malicious action, r4.2 / r5.2 | R2 33 / 28; chance about 3 / 3 | Percentile 59 / 80 (pre-registered fusion 60 / 54) | +26 / +52 over R2 | Headline (R2 role) |
| 20a | Analyst feedback (AAD) | insiders found in 100 reviews, r4.2 / r5.2 | Frozen Stouffer 55 / 43 | 57 / 42 | +2 / -1 (noise: +0.2 ± 0.9) | Dropped |
| 20b | Richer recommender items | web novelty found, r5.2 | Site rarity 11.4 | Site x hour popularity 26.0; CF variants 22 to 25 | +14.6 from context; CF adds nothing | Dropped |
