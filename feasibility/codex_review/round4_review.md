## 1. Approach

**The design is defensible; the three headline results do not yet describe one validated system.** Detection is evaluated daily, evidence localization retrospectively, and access control as a static policy simulation.

- **Value:** good. A bounded review list, supporting evidence and access suggestions form a useful workflow.
- **Novelty:** modest algorithmically. The strongest contribution is the integration and disciplined evaluation.
- **Technical depth:** sufficient through causal replay, recommender validation and checked local generation. More models would add little.
- **LinuxONE:** local processing fits the track. Hardware use, runtime and Granite reliability remain build deliverables; laptop results establish none of them.
- **Execution:** plausible if the team prioritizes one working replay and case file. If the web features are cut, the published full-feature numbers cannot describe that fallback.

**The abstract requires an explicit pivot disclosure.** It promised recommender-surprise detection on files and machines. The proposed detector now uses behavioral percentiles, and ALS predicts website use. That is a reasonable evidence-driven change. Say so. CERT activity also establishes neither business need nor existing permissions, so “trims everyone’s access to what they actually need” overclaims.

A skeptical judge will first ask: **“Did the evidence exist when the alert fired?”** Next: “Was 80/99 the preselected result?” and “How much of the easy success comes from synthetic destinations and late S1 labels?”

## 2. Code correctness

Reviewed the six scripts, notebook and recorded outputs. No raw-data reproduction was possible. Small synthetic checks confirmed prefix invariance of the main daily evidence functions and the secondary P@5 bug below.

1. **Daily detection causality and dates: fine.** Rolling sums include day \(d\) and preceding days; percentile references exclude the cutoff week. Detection searches from \(F\), then requires \(D<L\), correctly implementing **\(F\le D<L\)**. This is end-of-day detection: it cannot establish intervention before an action on the same day. See [early_warning_full.py:30](reference/early_warning_full.py), L74–91 and L182–197.

2. **Fusion calibration is causal, but uses test references.** `pooled_p` pools the trailing seven **test** days, including today. That matches its preregistration and is not look-ahead. However, “all references come from training” cannot describe fusion. Its tails are relative ranking scores, not calibrated incident probabilities. [early_warning_full.py:135](reference/early_warning_full.py)

3. **High: evidence localization uses future evidence relative to an alert.** People are selected using maxima across all test weeks; their evidence includes the entire test period. The 98% result therefore does not validate case files opened from the daily list. Training-only rarity does not cure future candidate availability. [evidence_ranking.py:129](reference/evidence_ranking.py), L138–140, L209–217 and L451–457.

4. **Evidence “items” are aggregates, not exact malicious events.** Matching operates on person/day/resource, or an entire USB/after-hours day. A matching item can contain benign activity too. Email and file events are excluded. Currently every insider has a matchable item, so there is no observed person-denominator exclusion; nevertheless, call this **aggregate-item localization**. [evidence_ranking.py:101](reference/evidence_ranking.py), L209–217 and L379–385.

5. **Material bug in the “actions remaining” calculation.** The simple replay reads every timestamp from an insider’s answer file without filtering the event’s user. Those files contain other people’s rows; the other scripts explicitly filter them. The resulting 54%/48% needs recomputation. It is also an **unweighted mean of per-insider fractions**, not the fraction of all malicious actions remaining. [early_warning_simple.py:38](reference/early_warning_simple.py), L41–46; compare [least_privilege_full.py:52](reference/least_privilege_full.py).

6. **Least-privilege split differs from the documented protocol.** The full experiment trains through `day < cut`; the independent checker drops the cutoff week. Both are temporally causal, but they are different experiments. Standardize before claiming exact independent reproduction. [least_privilege_full.py:180](reference/least_privilege_full.py), L205–207; [recommender_als_simple.py:4](reference/recommender_als_simple.py).

7. **Limited future/label dependence remains in least privilege.** The item catalog includes all-period resources and answer-key resources before fitting. Random initialization consequently depends on that catalog. LDAP fallback reads future snapshots. These are avoidable protocol violations, although no material inflation is established; the notebook reports no new hires. Use training-only catalogs and metadata, with unknown-resource handling during grading. Labels otherwise serve grading masks rather than ALS preference fitting. [least_privilege_full.py:39](reference/least_privilege_full.py), L88–105 and L123–133.

8. **ALS tuning is appropriately label-free and inside training.** Fine. But the full script selects hyperparameters separately on each release. Website winners happen to agree; computer settings differ. Describe a frozen **selection procedure**, rather than universally frozen parameters. [least_privilege_full.py:177](reference/least_privilege_full.py), L300–309.

9. **Ties are mostly handled honestly.** Daily lists use fixed random tie keys; evidence hit@3 correctly averages over tied permutations. However, popularity recommendations use alphabetical tie order in the full script and random jitter in the checker. Report tie sensitivity. The secondary `p5_strict` incorrectly applies a second short-list penalty: two cited malicious items produce 0.16 instead of 0.40. This does **not** affect headline hit@3. [least_privilege_full.py:152](reference/least_privilege_full.py); [evidence_ranking.py:315](reference/evidence_ranking.py), L349–352.

10. **Analyst-load metrics need their qualifiers.** “New names/week” means first-ever entrants, excluding the first two full weeks. Returning cases are omitted. “Normal slot share” classifies identities across the entire replay, so an insider’s pre-attack appearances are not counted as benign slots. Neither is operational alert precision. [early_warning_full.py:231](reference/early_warning_full.py)

11. **Requests and protection use different assumptions.** Requests count each disallowed person/site pair once across the whole test period, divided by person-months. “Prevention” counts every malicious event outside the original static allow-list. That does not simulate approvals granting access, subsequent malicious reuse, or actual intervention. There is also a minor missing inclusive day in the exposure denominator. [least_privilege_full.py:253](reference/least_privilege_full.py), L263–296.

12. **The organization-novelty check needs the same answer parser.** It does not filter answer rows to the named insider. Its normal-cost count is person/day/**domain** rows, potentially multiple per person-day. The rule is “absent from training,” rather than dynamically “never visited.” [org_novel_sites.py:7](reference/org_novel_sites.py), L11–20.

The feedback and richer-recommender producing scripts are absent. Their tables support descriptive comparisons, not a full leakage audit. Paired early-warning outcomes are also absent, preventing independent verification of the quoted McNemar p-values; the implemented test formula is fine.

## 3. Conclusions

### Headline claims and Steps 16–20

| Claim | Assessment |
|---|---|
| **59/70 and 80/99 in time — Step 19** | Supported by the summaries under the specified day-level definition. Present as a **selected secondary result**. |
| **Pre-registered success** | The registered primary comparison is FUSE-MAX: **60/70 and 54/99**, versus **33/70 and 28/99**. PCT was pre-specified, but its promotion to headline was post hoc. The artifacts do not establish promotion before r5.2. Both releases had already informed earlier development. |
| **Chance ≈3** | Correct for random **normal-person trajectories**. It is a conditional reference, not general chance performance for a randomly staffed 20-name list. Excluding insider trajectories removes many frequently listed profiles. Add a permutation across the complete roster, preserving list size and churn. |
| **Before about half their malicious actions** | Hold pending the answer-row fix. Then say “mean per-insider share of labeled events occurring on later days.” This estimates remaining opportunity, not prevention. |
| **About five new names/week** | Numerically correct with the qualifications above. Also show **30.2/32.6 distinct people per week** and **60%/63% normal-identity slots**. |
| **98% evidence hit@3 — Step 18** | Supported only for retrospective top-100 selected insiders: **42 and 44 people**. It cannot describe first-alert case files. |
| **ALS recall@20 ≈21%/19% — Step 16** | Supported approximately. This is recall over distinct new person/site pairs across the held-out period, including unknown-site misses. Replace “legitimate need” with “future observed use by answer-key-normal staff.” |
| **Requests 2.31→1.82 / 3.07→2.48 — Step 17** | Supported as simulated request equivalents. ALS adds **20 extra grants** beyond history. Only about **28%/41%** of those extra grants are subsequently used. That contradicts “only what they need.” |
| **About the same protection** | State the actual static coverage change: **71.0→69.0% / 87.5→86.8%**. No noninferiority or actual prevention is established. |
| **100% Wikileaks/keylogger blocking — Step 17b** | Plausible benchmark coverage, subject to parser cleanup. Attribute it entirely to the frozen catalog rule. It is a particularly favorable synthetic-data property. |
| **Feedback dropped — Step 20a** | Fine: the primary r5.2 result loses one discovery. Hidden-S2 comparison should include frozen fusion’s **19/30**, alongside AAD’s **22/30**, rather than only weak supervised baselines. |
| **Richer recommenders dropped — Step 20b** | Reasonable. Qualify “adds nothing” as no reliable incremental gain in the tested configurations. The “tuned rerun pending” statement is stale: tuned outputs are present. |

**The early-warning comparison matches daily list size, but not churn or cumulative review exposure.**

| K=20 | In-time catches, r4.2/r5.2 | Daily churn, r4.2/r5.2 |
|---|---:|---:|
| R2 + decay | 33 / 28 | 3.8% / 4.3% |
| R2 without extra decay | **59 / 40** | **9.1% / 8.9%** |
| PCT + decay | **59 / 80** | **9.2% / 11.3%** |

Thus the r4.2 advantage disappears against an already-reported R2 variant at almost identical churn. The r5.2 advantage remains substantial. Show this comparison prominently. Sources: [r4.2 summary](results/early/r4.2_summary.csv) and [r5.2 summary](results/early/r5.2_summary.csv).

**S1 timing needs explicit caution.** Unlabeled precursor activity does not justify relabeling it malicious. A median delay of zero partly reflects people already listed before official onset. Fresh in-time totals fall to **38/70 and 67/99**; fresh S1 catches are only **7/30 and 15/29**. Say “median delay from the first labeled malicious day was zero,” rather than “leakers are flagged the same day.” The job-hunter/snooper delays are also medians. “Sysadmin sabotage mostly missed” is fine.

**ALS now has a real, limited role.** At equal 20-grant budgets it outperforms popularity on future use and static malicious-access coverage. The matched-disruption outputs strengthen that case: at the reported matched costs, ALS coverage is **68.7% versus 60.4%**, and **85.9% versus 81.5%**. Those are descriptive interpolated trade-offs; their producing code is missing. Prediction quality still does not authorize automatic grants.

### Historical ladder, Steps 3–15

Notebook citations use zero-based cells.

| Steps | Verdict |
|---|---|
| **1–2** | Loading and label-date checks: fine. Attack-free labeled dates do not establish a globally leakage-free study. |
| **3–4** | Reported retrospective counts are supported. Rare-site transfer failure is correctly acknowledged. |
| **5–6** | CV gains are supported exploratory comparisons. They do not establish prospective or unseen-attack superiority. |
| **7** | **16 versus 4–7** is correct in the restricted normal-plus-held-scenario population. “Label-free wins” needs that scope. Repaired LOSO assignment is fine. |
| **8** | **12–13 versus 5** job-hunters: fine retrospectively. |
| **9** | **5→17** expected hits: supported, retrospective and exploratory. |
| **10** | **38→39.4** is supported, while AP falls **0.728→0.666**. “Core” is a design choice, not evidence of universal superiority. |
| **11–12** | Frozen Stouffer’s **45/38 hits@70** and AP advantages are supported. This is a different fusion from online FUSE-MAX. |
| **13** | **10.9→27** changes aggregation and discounting. Under common controls, ownership, naive novelty and ALS all reach **27/30**. Attribute the gain accordingly. |
| **14** | **55/43 versus 44/39 at 100 reviews**: fine. Keep explicitly retrospective; “default ranking” is superseded by the daily design. |
| **15** | Untuned MPR comparison is supported but cannot be directly read as the predecessor of recall@20: tuning, metric and evaluation details change. |

Two further corrections: “C1 beats the recommender” is too broad—r4.2 all-insider hit@3 favors several CF scorers. “Agreement collapses to C1” is also inaccurate for tuned r5.2: **0.891 versus 0.922**.

## 4. Improvements

Ranked by judging impact relative to effort:

| Priority | Concrete change | Effort | Test locally tonight? |
|---|---|---:|---|
| **1** | Evaluate C1 on evidence available at the actual daily alert, including benign alerts and alerts before labeled onset. Report first-alert hit@3 and unsupported-case frequency. | 2–3 h | **Yes, with cached data.** Adapt the two existing replay/evidence scripts; C1 needs no CF fitting. |
| **2** | Correct the pitch and result table: selected PCT versus registered fusion, retrospective evidence qualification, macro event fraction, simulated access policy. | 30 min | **Yes, CSV-only.** |
| **3** | Establish one cutoff specification and answer parser. Assert owner-filtered F/L, unique cache keys and training-only catalog membership. Preserve exact detector details, including the `0.01*sum(percentiles)` term. | 1–2 h | **Yes, with caches/answers.** |
| **4** | Add R2-without-decay, full-roster trajectory permutation and cumulative unique-review comparisons. Show existing workload sensitivities instead of choosing another winner. | 1–2 h | Existing comparisons **now**; new null needs replay data. |
| **5** | Smoke-test Granite/model loading and the full sample pipeline on LinuxONE immediately. Measure runtime and peak memory; verify sample outputs against the reference. | 1 h initially | Target VM required. |
| **6** | Validate case-file citations, values, units and dates against the evidence pack. Include benign, weak-evidence and hostile-log-text cases; use a deterministic fallback. | 1–2 h | Checker locally; model behavior on VM. |
| **7** | Present ALS’s matched-budget trade-off and unused grants. Make access changes reviewable suggestions; specify approval persistence before claiming request savings plus protection. | 1–2 h | Existing curves **now**; sequential policy requires a small extension. |

The fallback detector must be re-evaluated if web features disappear. Further tuning tonight cannot restore an untouched test set.

## 5. Verdict

Present the causal daily replay, disclose that PCT was promoted after results, show the stronger R2 comparison, and retain ALS as a separately evaluated website-access advisor. Keep Granite as a checked summarizer with an explicit weak-evidence state. Cut the universal “legitimate need,” prevention and commercial-tool superiority claims, plus the 98% first-alert implication. **The single most important fix is to evaluate and demonstrate each case file using only evidence available when its alert fires.**