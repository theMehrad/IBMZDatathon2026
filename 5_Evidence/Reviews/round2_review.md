Your tentative conclusion is supported: personal baselines and persistence are the defensible core; the recommender shows some conditional combiner value, but its destination queue reduces r5.2’s total discoveries. **S15/C50:** `"59"` insiders without it versus `"53"` with it.

Citations below refer to **v2’s zero-based cells**. Verified means established from code/output; effects requiring unavailable scores are explicitly conditional.

**1. Fixes: what works and what remains**

- **Verified correct: `top_expected` and `aligned`.** C3:L16’s `mask[above].sum() + (k - above.sum()) * mask[tie].sum() / tie.sum()` correctly calculates expected hits under uniformly ordered ties. L11’s `fillna(min(0.0, s.min())...)` implements the stated missing-score convention. Add bounds checks for `k`, but current evaluations use valid sizes.

- **Verified correct: LOSO assignment.** S7/C23:L7 uses `held_folds = np.array_split(held_idx, 5)`; L10–11 scores both normal users and assigned held insiders once per repeat, divided by `seeds`. Held-scenario insiders remain excluded from fitting. The previous ensemble asymmetry is fixed.

- **Verified correct: weekly boundaries and zero padding.** S8/C26:L6 requires `wk.week + pd.Timedelta(days=6) < c.cut` for training and removes `"boundary"` weeks. S10 uses this table. C3:L35–36 merges onto every active test day and fills novelty columns with zero. Current callers aggregate to unique user/day keys first, avoiding duplicate expansion.

- **High, verified: the fusion comparator silently changes.** S11/C35:L31 assigns `c.fused_stouffer`; S13/C42:L47 calls `fusion_rows(c, FAM_OWN)`, overwriting it with **ownership-augmented fusion**. S14/C45 then reports that cached score under `"family-first Stouffer"`. Consequently, its `"44"`/`"41"` are not the original frozen method. Original Stouffer’s scenario counts sum to **55/100 on r4.2** and **43/100 on r5.2**—S11/C35: `"30/30 15/30 10/10"`; S12/C39: `"29/29 4/30 10/10 0/30"`. Store both scores separately and label them accurately.

- **Medium, verified: ownership controls still use different denominators.** S13/C42:L9 discounts ownership using foreign-personal-PC frequency; L28 discounts controls using `tr.pc != tr.user.map(primary)`. These differ for shared/unowned computers and nonprimary computers belonging to the user. The functional form is shared, but the actual discount is not. Repeat with one common denominator before attributing the remaining gap specifically to ownership semantics.

- **Medium, verified: MPR retains arbitrary tie ordering.** S15/C48:L19 uses `argsort(kind="mergesort").argsort()`. Equal popularity scores receive item-order ranks rather than average ranks. L7’s `np.clip(..., 0, 1)` also creates affinity ties. Recompute using average ranks; preferably rank unclipped affinities. The magnitude of any change to `"35.9"` versus `"35.5"` is **unknown**.

- **Low, conditional: queue ties and termination.** S14/C45:L7 sorts only `["a", "b"]`; residual joint ties still inherit input ordering. Whether they cross current selection boundaries is unverified. `queue_budget` correctly deduplicates/refills the current 100-person selections, but L27’s `while len(picked) < K` never terminates if `K` exceeds available users. Add a capacity assertion.

- **Verified: `same_footing` fixes the earlier aggregation confound.** S15/C49:L5 applies one aggregation/padding operation to `["one", "rare", "s", "peer"]`. However, these controlled rare-site scores are **not** used downstream: C50 still uses `"w_rare"`, the cumulative visit-count feature from S4/C14:L39.

**2. Which conclusions changed?**

- **Unseen-job-hunter weakness survives.** Repaired S7/C23 reports LR `"5/30"` with ALS, `"7/30"` without; GBT `"4/30"` either way; label-free sum `"16/30"`. The earlier numerical comparison changes, but the trained models’ weakness remains.

- **Own-history features help, but the old magnitude disappears.** S10/C32: base LR `"47"` hits becomes `"51"` with percentiles; adding plain ALS still gives `"51"`. Hidden job-hunters improve `"8/30"`→`"12/30"`, not the former 12→19 claim. Peer-of-item reaches `"16/30"` in that particular LOSO comparison.

- **“Best single on both releases” should be dropped.** On r4.2, percentiles give `"39.4"` hits and `"AP 0.666"`—S10/C32. Rare-site visits give `"41.0"` hits—S4/C14—and R2 gives `"AP 0.728"`—S3/C11. On r5.2, percentiles remain strong: `"40.3"` hits, `"AP 0.477"`—S12/C38.

- **Fusion retains a baseline advantage.** Original Stouffer has `"AP 0.784"` versus R2 `"0.728"` on r4.2—S11/C35—and `"0.478"` versus `"0.428"` on r5.2—S12/C39. It approximately matches r5.2 percentiles, rather than demonstrating that fusion generally fails.

- **Persistence/discounting explains much of the computer gap.** S13/C42 gives naive and ALS-flagged controls `"27/30"` snoopers versus ownership `"30/30"`. That strongly weakens “collaborative filtering fundamentally forgives colleagues’ computers,” although the remaining denominator confound prevents a clean causal decomposition.

- **Queues are release-dependent.** At 100 reviews, S14/C45 reports queues/R2/percentiles as `"42"/"44"/"43"` on r4.2 and `"53"/"39"/"44.6"` on r5.2. The fusion correction above makes r4.2’s queue deficit larger.

**3. Is Step 15 convincing?**

- **RMSE is a diagnostic, not the headline.** S15/C48 compares uncalibrated implicit affinities with a binary future-use grid: r4.2 website RMSE `"0.5394"` versus popularity `"0.4257"`. This mixes calibration, unobserved-pair treatment, and different training/test exposure lengths. It does not establish whether the embeddings identify malicious access. Ranking is better aligned with implicit-feedback evaluation; the cited [Hu–Koren–Volinsky paper](https://yifanhu.net/PUB/cf.pdf) likewise evaluates percentile ranking.

- **MPR is more appropriate, after fixing ties.** S15/C48’s website results are `"35.9"` versus `"35.5"` on r4.2 and `"35.8"` versus `"38.3"` on r5.2. These describe normal users’ previously unseen **training-catalog** items: L9 excludes items absent from `iidx`. State that coverage restriction and that the result is averaged over distinct user/item uses. Also, this evaluates dot-product affinity, whereas the destination detector uses peer cosine similarity—S9/C29:L9—so it does not directly validate that detector.

- **Controlled standalone results are mixed.** S15/C49: rare-new-site AP beats peer-of-item on r4.2, `"0.469"` versus `"0.364"`; peer-of-item wins on r5.2, `"0.259"` versus `"0.120"`. That supports a useful candidate signal, not universal superiority.

- **Distinguish replacement from incremental addition.** S15/C50: replacing naive website features with recommender features yields `"51"`→`"52"` hits on r4.2 and `"45"`→`"48"` on r5.2, with nearly equal AP. But **adding** recommender features to naive ones yields r5.2 `"45"`→`"49"` and `"AP 0.600"`→`"0.630"`. That is the stronger conditional-value result and deserves acknowledgment.

- **Generalization remains inconsistent.** In S15/C50, r5.2 hidden job-hunters are `"5/30"` with naive features versus `"3/30"` with recommender or both; hidden sysadmins improve `"7/10"`→`"10/10"`. Neither “helps unseen attacks” nor “never generalizes” fits all scenarios.

- **Queue contribution is negative on r5.2.** S15/C50’s recommender queue contributes `"5"` insiders missed by the three-queue version, but totals fall `"59"`→`"53"`: it discovers five different insiders while displacing **eleven** others. On r4.2, totals rise only `"41"`→`"42"`; rare sites give `"44"`.

Before accepting a stronger “adds value” claim, fix ties and denominators, carry controlled rare-site features into downstream ablations, report paired user-level uncertainty, and freeze the configuration before an untouched test. S15/C50 remains exploratory. Also, S14’s LR `"55"` is one reference configuration; S15’s “both” scenario counts sum to **62/100** on r5.2.

**4. Disagreements A–C**

- **A: Agree on legitimacy, disagree that the convention is shared universally.** Retrospective normalization is valid for the declared task. But C3:L42’s whole-test `"median"` applies to novelty signals, while S3/C11 uses training means and S10/C32 uses training percentiles. Even within novelty, persistent versus isolated activity changes median/MAD differently. No verified systematic inflation is established; operational advantages cannot be inferred.

- **B: Agree, with narrower wording.** S7/C23:L17–21 validly compares a fixed label-free score against trained combiners among normals plus one scenario. Say **“without attack-label fitting,”** not “never saw any attack”: normalization uses test activity, and detector selection used labels. It is not independent validation of unseen-scenario design.

- **C: Your replacement remains too absolute.** S7/C23 simultaneously shows hidden leakers `"30/30"` and GBT hidden job-hunters `"4/30"`. Use: **“Generalization deteriorated sharply for some withheld scenarios.”**

**5. Claims for tomorrow**

Safe, explicitly framed as exploratory retrospective results:

- **“Simple personal baselines are strong.”** R2: `"P@20 1.0"`, `"AP 0.728"` on r4.2—S3/C11.
- **“Own-history percentiles transfer usefully.”** r5.2: `"P@20 1.000"`, `"AP 0.477"`—S12/C38.
- **“Persistence-based computer signals surface snoopers.”** Ownership `"30/30"`; naive/ALS controls `"27/30"` in top 100—S13/C42, with denominator caveat.
- **“Recommender features offer conditional predictive information.”** r5.2 LR naive→both: `"45"`→`"49"` hits—S15/C50; no independent validation.
- **“Queue allocation matters.”** r5.2 three queues find `"59/100"` versus four queues `"53/100"`—S15/C50; the four-queue system finds only `"2/30"` job-hunters.

Drop **“ALS adds seven,” “best single on both releases,” “ownership versus ALS proves a resource-type limitation,” “four queues are best,”** and **“nothing below was tuned on r5.2.”** The revised outputs and S13’s explicit post-r5.2 design disclosure do not support them.

Keep the recommender as a tested research branch or optional evidence signal. The honest pitch is that controlled evaluation changed the original recommender-first design—S15/C50’s `"53"` versus `"59"` makes that decision concrete.