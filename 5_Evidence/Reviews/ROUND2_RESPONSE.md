# Response to your round-1 review (from the study's author)

Thank you. I checked every point against the code and, where needed, the raw data. The notebook has been revised and fully re-executed: `OutOfRole_Feasibility_v2.ipynb` (new) vs `OutOfRole_Feasibility.ipynb` (the version you reviewed). `code_diff_v1_v2.txt` shows every code change. Finding cells in v2 are still placeholders; I will rewrite them from the v2 outputs after this round.

## Accepted and fixed in v2
1. **LOSO scoring asymmetry** (your High). Held-out insiders are now split across the same outer folds and scored once per repeat, exactly like normal staff. All LOSO tables were recomputed.
2. **Weekly boundary week** (your High). The week containing the cutoff is now dropped from both train and test (`week_table`). I agree it was test-data leakage into training. I'd rate it low to medium rather than high: no malicious day fell in it (first malicious events: June 10, 2010 for r4.2, April 16, 2010 for r5.2; cutoffs June 1 and April 1). It's fixed regardless.
3. **Top-k ties.** `metrics` now reports **expected** top-k counts under random ordering of tied scores (`top_expected`), so P@20, hits@70 and per-scenario counts no longer depend on user-ID order. Queue selection breaks ties with a related signal chosen a priori (`SECOND`).
4. **Missing users scored at the minimum observed value.** Missing now means 0 (or the minimum when negative scores exist): `aligned()`.
5. **Novelty normalization ignored zero-novelty days.** `robust_max` now runs over every active test day, with 0 on days without novelty (`pad_days`). It's still retrospective by design (whole-test-period typical day); see disagreement A.
6. **Feature-description mismatches.** Step 4 now says distinct new items per active day; Step 6 says 28-day totals vs the team's median total.
7. **Equal-budget comparison.** Step 14 now refills the four queues round-robin to exactly 100 different people and compares them with R2, the best single signal, family-first Stouffer and the trained combiner, all at 100.
8. **Ownership confound.** Step 13 now gives the naive "new computer" signal and a recommender-flagged computer signal the *same* weekly counting and roaming discount as the ownership rule.
9. **Peer-of-item vs plain-ALS aggregation confound.** New Step 15 compares naive, rare, recommender-surprise and peer-of-item website signals on identical footing (same per-day aggregation, same zero padding).
10. **Recommender contribution.** New Step 15: the recommender's own accuracy (RMSE on the visit grid, and mean percentile rank of first-time uses vs a popularity baseline); the combiner with none / naive / recommender / both website signals, under CV and the repaired LOSO; and the queues at 100 people with the destination queue powered by the recommender, rare sites, naive novelty, or removed.

## Verified facts you questioned
- **wikileaks.org:** across the **entire** r4.2 web log (train and test), exactly 30 users ever visited it, and all 30 are scenario-1 insiders. The claim holds; the notebook will show this check.
- **r5.2 departures:** 29 insiders are still employed at the end, all scenario 4; one snooper left. The Finding was wrong ("the 30 snoopers stay") and will be corrected.
- **"1.3 to 1.5 times" job-hunter site lift:** this came from an exploratory check outside the notebook. I will remove the number or add the computation.
- **Research_Findings "10 people"** vs the notebook's 11: will be reconciled to the notebook.
- **LANL:** you're right; "real access logs are never released" is false as written. It will become "real access logs with insider labels are very rare (LANL releases real authentication logs with red-team labels)".

## Where I disagree, and why. Please push back if you think I'm wrong.
- **A. Retrospective normalization.** For a user-level *retrospective triage* ranking, normalizing against the person's own test-period behavior is a legitimate design, as long as it's labeled as such. It isn't an operational, timely detector, and we'll say so. Do you see any way it inflates the comparison *between* methods, given they all use the same convention?
- **B. `loso_unsup` "misleading".** The label-free score is unchanged when a scenario's labels are hidden, because it never uses labels. Its LOSO number answers the fair question: how does a method that never saw any attack rank this attack type among normal staff, against a trained method that saw the other types? The population normalization is transductive, but label-free. I think the comparison is valid if described that way. Agree?
- **C. "Memorizes known attacks".** Accepted as too strong; it will become "does not generalize to an attack type it didn't see in training".

## What I'd like from you in round 2
1. Review `code_diff_v1_v2.txt` for mistakes in the fixes themselves, especially `top_expected`, the LOSO fold assignment, `week_table`, `pad_days`, `queue_budget`, `det_owner_ablation`, `als_accuracy` and `same_footing`.
2. Read the v2 outputs, Steps 7 and 10 to 15. Which conclusions changed after the fixes, and which survive? Be quantitative and quote the v2 numbers.
3. Judge Step 15. Is it a fair, convincing measure of the recommender's contribution? Is RMSE vs popularity on an implicit-feedback grid meaningful here, or is the percentile-rank result the one to present? What would you want to see before accepting "the recommender adds value"?
4. Respond to disagreements A to C.
5. Give a final short list of the claims the team can safely make to IBM judges tomorrow, each with the supporting v2 number, and the claims they should drop.

## My own first read of v2 (please verify against the outputs, don't take it on trust)
- The recommender's own accuracy (Step 15, cell 48) is roughly at the popularity baseline: MPR of first-time site uses 35.9% vs 35.5% (r4.2), 35.8% vs 38.3% (r5.2); its RMSE is worse than popularity (uncalibrated implicit scores).
- On identical footing (cell 49), "rare new sites" beats peer-of-item on r4.2 (hits 40.4 vs 17, AP 0.469 vs 0.364), while peer-of-item beats it on r5.2 (31 vs 11.4, AP 0.259 vs 0.120).
- Combiner ablation (cell 50): the recommender's gain over naive website novelty is +1 hit on r4.2 (52 vs 51) and +3 on r5.2 (48 vs 45), with AP about equal. Equal-budget queues: on r5.2, dropping the destination queue gives 59 vs 53; on r4.2, 41 vs 42.
- Ownership ablation (cell 42): with identical weekly counting and roaming discount, naive 27/30 and recommender-flagged 27/30 vs ownership 30/30 snoopers. So most of the earlier "ownership vs ALS" gap came from aggregation, as you suspected.
- Equal budget at 100 (cell 45): r4.2 queues 42 vs R2 44, pw_hi_max 43, Stouffer 44, trained LR 63; r5.2 queues 53 vs R2 39, pw_hi_max 44.6, Stouffer 41, trained LR 55.
- Repaired LOSO (cell 23): hidden job-hunters, LR 5 to 7, GBT 4, label-free sum 16.
My tentative conclusion: the recommender should not be presented as a main contributor. The defensible core is the personal baselines plus own-history percentiles, plus a persistence-based out-of-role signal for snoopers. Do you agree? What is the most honest way to keep, or drop, the recommender in the pitch, given that the team's original abstract was built on it?
