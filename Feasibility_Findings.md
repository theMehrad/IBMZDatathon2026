# OutOfRole: Feasibility Findings (Oct 16, before the event)

Throwaway test on the full CERT r4.2 data, run on Mehrad's laptop. The test code is not part of the project; the team writes everything from scratch during the event. Only these findings carry over.

## Setup

- Train on Jan to May 2010 (no insider activity starts before June 2010). Test on Jun 2010 to May 2011.
- Scored per **person**: 1,000 employees ranked, checked against the 70 labeled insiders.
- Metrics: P@20 = share of the top 20 who are insiders; hits@70 = insiders in the top 70; AP and AUC over all 1,000.

## Results

| Detector | P@20 | hits@70 | AP | AUC | Top 100 by scenario (of 30 / 30 / 10) |
|---|---|---|---|---|---|
| Rule: days with after-hours USB | 0.30 | 34 | 0.27 | 0.77 | 30 / 4 / 8 |
| Per-person behavior, daily | 1.00 | 38 | 0.68 | 0.94 | 30 / 2 / 10 |
| Per-person behavior, 28-day windows | 1.00 | 38 | 0.73 | 0.96 | 30 / 5 / 9 |
| Naive novelty (new computers + new sites) | 0.30 | 12 | 0.13 | 0.58 | 3 / 4 / 9 |
| ALS novelty (computers + sites) | 0.45 | 14 | 0.18 | 0.70 | 5 / 4 / 10 |
| **Learned combination, without ALS** | 1.00 | 39 | 0.73 | 0.96 | 30 / 6 / 10 |
| **Learned combination, with ALS** | 1.00 | **45 to 46** | **0.77** | 0.97 | 29 / 10 to 11 / 10 |

Learned combination = logistic regression over the detector scores, 5-fold cross-validated and averaged over 5 splits. The ALS result held across three ALS random seeds (45, 45, 46). Adding the naive novelty signal instead of ALS added nothing (39).

## What it means

1. **The recommender alone does not catch insiders.** It must not be pitched as the whole engine.
2. **Per-person behavior baselines do most of the work.** They put 20 of 20 insiders at the top and catch every leaker (scenario 1) and every sysadmin (scenario 3).
3. **ALS earns its place, measurably.** It adds 6 to 7 insiders to the top 70, mostly job-hunters (scenario 2) that the behavior rules miss. A plain "is this new?" check adds nothing, so the gain comes from comparing people with similar colleagues.
4. **wikileaks.org was visited by all 30 leakers and no normal employee;** keylogger sites only by insiders. A "rare site" signal is cheap and strong, and it gives Granite clear facts to explain.
5. **Scenario 2 stays hard.** Job and competitor sites were already part of these people's browsing, and visits rise only 1.3 to 1.5 times over about 55 days. Expect about a third of them caught; say so in the pitch.
6. **Sparsity is not a problem:** the web log has only 475 distinct sites and 1,003 computers.
7. **Speed:** the Spark pass over all logs, including the 14.5 GB web log, took 37 seconds on a 12-core laptop. Budget several minutes on the 3-vCPU LinuxONE server.

## Changes for the build

- Pipeline: Spark ETL, then four detectors (daily behavior, 28-day behavior, rare sites, ALS novelty on computers and sites), then a learned combination, then Granite explanations for the top 10.
- The web log moves from stretch goal to core: both rare sites and ALS need it.
- Pitch ALS as "unexpected for someone like you", backed by the with/without-ALS row above.
- Report two numbers honestly: the label-free combination (39 of 70) and the learned one (45 of 70), noting that the learned one needs past labeled incidents.

---

# Round 2 (late Oct 16): research-driven upgrades and a second dataset

Same throwaway rules as above. New: research from five sources (see `Research_Findings.md`), and an unchanged run on **CERT r5.2** (2,000 staff, 99 insiders, adds **scenario 4: logging into colleagues' computers**; train window ends Apr 1, 2010 because scenario 4 starts Apr 16).

## What held up on both releases

| Signal | r4.2 | r5.2 | Verdict |
|---|---|---|---|
| **Own-history percentile, worst week** (Le & Zincir-Heywood) | top 20 all insiders, AP 0.67 | top 20 all insiders, AP 0.48 (best single signal) | **Core detector** |
| **Unusual-weeks count** (sustained drift) | 13 of 30 job-hunters in top 100 | **20 of 30 scenario 4** in top 100 | Catches slow attacks |
| **Ownership rule**: logins to someone else's personal computer, weekly, discounted for people who already roamed | no scenario 4 in r4.2 | **30 of 30 scenario 4** in top 100, top 20 is 80% insiders | **New, label-free, big win** |
| **ALS peer-of-item on websites** (how close you are to the site's previous visitors) | 16 of its top 25 are insiders | 16 of its top 25 are insiders | The recommender's real job |
| ALS on computers | weak | **worse than plain "new computer"** (7 vs 12 of 30 scenario 4) | Drop it |

**Why ALS fails on computers:** a colleague's computer belongs to someone similar, so collaborative filtering decides the access is normal and forgives exactly the attack. Use the recommender for **shared** resources (websites, shared drives) and an ownership rule for **personal** ones. That's a good, honest line for the pitch.

## What did not hold up

- **Trained combiners** (logistic regression, gradient boosting) break on attack types they never saw: hiding one scenario from training swung results from 0 to 26 of 29 on r5.2. Don't headline them.
- **Statistical fusion** (Fisher, Stouffer, Cauchy, family-first): family-first Stouffer was the best label-free method on r4.2 (top 20 all insiders, 47 of 70 in the top 70) but only matched the best single signal on r5.2. Averaging washes out specialist detectors: fused, the ownership rule kept only 5 of 30 scenario 4 insiders in the top 100.
- **Job-hunters (scenario 2)** stay hard everywhere: 1 to 6 of 30 in most setups. The published work reports the same (12.5 to 74%). Say so.

## Recommended design for the build

**Specialist alert queues** instead of one fused score, the way commercial tools (Splunk, Exabeam, Sentinel) do it. Each alert says *why*, which is also exactly what Granite needs to explain it:

1. **Sudden spike**: own-history percentile (day and week)
2. **Slow drift**: unusual-weeks count
3. **Out-of-role access**: ownership rule on personal computers
4. **Unusual destination**: ALS peer-of-item on websites, plus rare sites

With 25 review slots per queue, fixed in advance: **r5.2: 54 insiders among 88 people reviewed** (26/29 leakers, 7/10 sysadmins, 20/30 scenario 4). r4.2: 40 among 87, because the ownership queue spends 25 slots on a threat r4.2 doesn't contain. In the build, size each queue by a **score threshold** (alert only when a signal is extreme) instead of fixed slots, so an absent threat type produces few alerts.

## Platform notes (from IBM's repos)

- Autoencoder (if kept): Keras with `ibm-zdnn-plugin` or `torch_nnpa` to run on the Telum AI chip.
- Any boosted model: XGBoost exported to Snap ML.
- Spark is not in the image: install OpenJDK 17 and PySpark; there's no pyarrow for s390x, so avoid pandas UDFs.
- Granite: reuse the loan-approval demo's big-endian model file and pre-generate the explanations.
