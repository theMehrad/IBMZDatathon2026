Citations use **S = step, C = zero-based notebook cell, L = source line**. “Verified” means established from code or recorded output; “conditional” means the data is needed to establish an effect. I read every code cell, recorded output, Finding cell, and both documents. I did not rerun the study.

**1. Code correctness bugs**

- **`etl` — Low, conditional: incomplete/stale cache.** S1/C5:L3: `if (out / "daily").exists() and not force:` accepts the cache without checking `pc_pairs`, `dom_pairs`, source freshness, or ETL version. A partial or stale cache could invalidate downstream numbers. No evidence establishes that this happened.

- **`context` — Low, conditional: evaluation roster.** S1/C5:L40: `c.users = sorted(c.daily.user.unique())` defines staff through observed activity. Users absent from the logs disappear from ranking, while scenario denominators still use the answer key. The printed `"staff 1000"` and `"staff 2000"` match expectations, but membership assertions are missing.

- **`metrics` — Medium: arbitrary top-k tie handling; conditional missing-score error.** S3/helper C3:L13: `order = s.sort_values(ascending=False, kind="mergesort").index` breaks ties through the sorted user-ID order. This particularly affects integer-valued percentile scores and queue selections. AP/AUC handle score ties; top-k results describe one arbitrary ordering. L11, `s = s.fillna(s.min() if s.notna().any() else 0)`, also assigns missing users the smallest **observed** score, which may be positive; absent rare-site activity should normally score zero. Potential effects: P@20, hits@70, scenario counts, and missing-user AP/AUC.

- **`robust_max` — Medium, verified: future-dependent baseline and omitted zero days.** S3/helper C3:L27: `med = g.transform("median"); mad = g.transform(lambda x: (x - x.median()).abs().median())`. Callers supply test-period novelty rows, so later test activity changes earlier deviations. Moreover, S4/C14:L30–31 builds an outer union of novelty days, excluding days without either kind of novelty. Three identical novelty days can consequently score zero, even after many ordinary days. This affects naive novelty, ALS novelty, peer/lift scores, and all combinations using them.

- **`rz` — No positional bug found; evaluation limitation.** S3/helper C3:L32: `v = np.log1p(pd.Series(s).reindex(users).fillna(0).clip(lower=0))` aligns IDs correctly. Its median/MAD come from the evaluated population, making the score transductive rather than calibrated against historical normality. This matters especially for S14’s `"robust z >= 6"` threshold.

- **`pct` — Low, conditional.** S3/helper C3:L39: `return s.fillna(s.min()).rank(pct=True)`. An entirely missing signal stays missing; missing activity can receive a positive minimum. No current output proves this occurred. Its average-rank treatment of ties is otherwise valid.

- **`window_z` — No demonstrated index misalignment.** S3/C11:L5’s `.day.nunique().values[:, None]` uses the same default-sorted groups as the numerator. L7’s `.rolling(f"{w}D")` is a **calendar** window, and L8’s counts follow the same group/row order. However, `te_s = c.te...` means early windows omit pre-cutoff history; the denominator counts observed active-day rows, not elapsed days. Thus `"28-day"` initially means a shorter, active-day-adjusted window.

- **`det_baselines` — No demonstrated alignment bug.** S3/C11:L17: `m = te[["user"]].join(mu, on="user")[FEATS].fillna(0).values` aligns each row to its user before conversion. The means and standard deviations use training rows. The missing-calendar-day qualification above also applies to `"R1 daily behavior z"`.

- **`split_new` — No direct leakage found.** S4/C14:L3: `seen = set(zip(trp.user, trp[item]))` uses training pairs only. L4 deliberately counts repeated test accesses as “new relative to training”; it does not implement “first-ever access” after deployment.

- **`train_als` — No demonstrated correctness bug.** S4/C14:L7: `trp.groupby(["user", item]).n.sum()` uses web visit counts; the alternative `.size()` uses computer login-days. L13 initializes absent training users with zero factors. That is a cold-start convention, not a learned prediction; S2’s `"new hires 0"` does not validate cold-start performance.

- **`predict` — No positional bug found.** S4/C14:L20: `pred[known] = np.einsum(...)` applies matching masks to users and items. Unknown items retain zero affinity and therefore receive maximum surprise in S4/L27.

- **`det_novelty` — Medium, verified feature-definition mismatch.** S4/C14:L28: `new_["one"] = 1.0`; L30–32 sums these rows and surprise values without multiplying by web count `n`. These are **distinct new domains per user-day**, not the markdown’s “each ... web visit.” Only `w_rare` explicitly sums visits through L38’s `.groupby("user").n.sum()`. Reported numbers are valid for the implemented feature, but the feature description and any volume interpretation are wrong.

- **`Xmat` — No leakage/alignment bug found.** S5/C17:L2: `pd.Series(c.S[k]).reindex(c.users)` aligns IDs, fills missing activity with zero, then applies an elementwise log transform. Learned standardization is inside the estimator pipeline, not fitted globally.

- **`cv_score` — No direct supervised fold leakage found.** S5/C17:L12 uses `cross_val_predict(... StratifiedKFold(5, shuffle=True, random_state=s) ...)`. However, L14’s `np.mean(ps, axis=0)` produces an averaged out-of-fold ensemble; it is not 25 independent evaluations. Feature/model selection using these same results remains optimistic.

- **`loso` — High, verified evaluation defect.** S7/C23:L8 scores each normal user once per seed: `p[pool[b]] += ... / seeds`. L9 scores each held-out insider in **every fold**: `p[tst] += ... / (5 * seeds)`. Thus insiders average 25 models while normals average five. The means have comparable nominal scale, but different ensemble variance, potentially changing top-100 membership in either direction. All LOSO counts in S7, S10, and S12 require recomputation. Assign held insiders to outer test folds and score each once per repeat, like normals.

- **`loso_unsup` — Correct filtered ranking, misleading “unseen” interpretation.** S7/C23:L15 computes one score on everyone, then L18 removes other scenarios. Nothing is retrained or held out from normalization. The reported `"12/30"` describes a restricted candidate pool, not an independent generalization experiment.

- **`det_more` — Medium, definition issue; low conditional missingness risk.** S6/C20:L15: `tm = roll28.groupby(["team", "day"])[WF].transform("median").values` compares **rolling totals**, although S6 describes `"28-day rate against the team median"`. Different active-day exposure can drive differences. L3’s concatenated team fields also become missing if any component is missing, causing peer statistics to disappear. No evidence establishes missing LDAP fields here.

- **`personal` — Alignment is correct; low conditional cold-start issue.** S8/C26:L6: `mu.reindex(df.user).values` preserves the intended row order. Its final `.fillna(0)` makes a user without baseline history look exactly typical. The present outputs do not establish such users.

- **`det_models` — High, verified cutoff leakage.** S8/C26:L12 groups whole calendar weeks before `personal` decides training membership through L4’s `trm = df[key] < c.cut`. The week beginning **May 31** includes June 1–6 test data; the week beginning **March 29** includes April 1–4. Those days enter training and disappear from weekly testing. Recorded attack starts are later, so this is test-data leakage, not demonstrated attack contamination. It affects weekly models and downstream combinations. L18’s `Xtr[::3]` also makes LOF subsampling dependent on row order.

- **`det_als_tweaks` — Medium, verified uncontrolled comparison.** S9/C29:L14: `d = new.groupby(["user", "day"])[["peer", "lift"]].sum().reset_index()` uses item-specific novelty days. Plain ALS in S4 instead uses the union of computer and website novelty days. Consequently `"a_dom"` versus `"dom_peer"` changes both the access score and the days used for median/MAD normalization. The improvement cannot all be attributed to peer similarity.

- **`det_site_lift` — Medium, verified denominator and aggregation defects.** S9/C29:L23 multiplies the personal active-day rate by a fixed `20`: `...fillna(0).values * 20`, despite a calendar `"28D"` window and shorter initial windows. L26 aggregates only domains visited **on that date**; domains still contributing to a 28-day history vanish on dates without a current visit. This is not a synchronized user-by-site rolling profile. The reported `"AUC 0.55 to 0.62"` does not fairly reject the intended method.

- **`det_ownpct` — High, verified weekly cutoff leakage; medium tie sensitivity.** S10/C32:L3: `tr, te = wk[wk.week < c.cut], wk[wk.week >= c.cut].copy()` repeats the weekly leakage above. L9’s `(P >= 0.99).sum(axis=1)` yields only ten possible scores, 0–9. With roughly 13–22 training weeks, the empirical tail is extremely coarse. The headline `"40"`/`"39"` hits and top-25 spike queues need tie-sensitivity reporting.

- **`fusion_rows` — Medium, interpretation/calibration problem.** S11/C35:L12: `P = X.rank(ascending=False, method="max") / n` creates empirical ranking scores, not validated incident probabilities. L29’s family correction often saturates at `1`; L21 clips that to `1 - 1e-9`, which contributes approximately **−6** to Stouffer. This can heavily penalize specialists with ordinary scores elsewhere. Rankings are computable, but “p-value,” “99th percentile,” and confidence language do not establish false-positive control.

- **`det_owner` — Medium, denominator qualification.** S13/C42:L9: `...groupby("user").f.mean()` averages **user–computer–day pairs**, not days or weeks. Days with more computers get more weight. L12 then divides a count of foreign-access weeks by this fraction: `weeks / (1 + 50 * base.reindex(c.users).fillna(0))`. This is a heuristic roaming discount, not an exposure-adjusted weekly rate. It drives the dramatic change from `"own_days"` catching **2/30** snoopers to `"own_weeks_adj"` catching **30/30**.

- **`queues` — Medium, budget/tie interpretation; union arithmetic is correct.** S14/C45:L7 takes each top 25 independently, and L8’s `picked |= set(sel)` deduplicates without refilling. Thus 100 alert slots become `"87"` or `"88"` unique reviews. ID-based ties remain. The reported `"54"` insiders among `"88"` people is consistent with the recorded output; it is not a ranked top-100 system result.

**2. Leakage and evaluation design**

- **The blanket “no leakage” claim fails.** S2’s `"no attack is ever in training"` is supported for recorded event start dates, but does not cover weekly boundary leakage or S3’s `"typical test day"` normalization. Whole-test normalization is permissible for a clearly labeled retrospective ranking, not evidence of causal, timely detection.

- **Labels influence design.** S12 explicitly says `"developed on r4.2 with its answer key in view"`. S4/C14:L51, `dn[dn.user.isin(c42.lab)]`, also inspects malicious users’ destinations. That display is not a hardcoded detector, but subsequent choices are label-informed. The plan’s `"answer key only to grade"` and Research Findings’ `"protocol avoids all four"` overstate the separation.

- **Even the after-hours choice uses test information.** S1 says `"chosen from the logon-hour histogram below"`; C5:L18 computes the histogram from the entire log. This is modest exploratory look-ahead, separate from malicious-label leakage.

- **User ranking is appropriate for retrospective triage, insufficient for operational detection.** S3 evaluates maxima across `"351"` test days; S12 uses `"428"`. Maxima and cumulative counts have different exposure effects, and ranking gives no detection delay or alerts per week. Specify the review period; add time-to-first-alert and precision at a fixed periodic budget.

- **LOSO needs the scoring repair above.** S7’s `"9/30"` versus `"12/30"` cannot currently establish one method’s unseen-attack superiority. Other scenarios are removed from the evaluation pool through `keep = (sc == 0) | tst`, making this a narrower task than ranking all staff.

- **5×5 CV is adequate for exploratory LR comparisons, not a strong validation claim.** S5’s `"5-fold ... repeated over 5 shuffles"` still contains only 70 distinct positives, about 14 per test fold. Repeats reduce split variability; they do not create additional attacks. Report paired uncertainty and distinguish scenario/template dependence from independent observations.

- **r5.2 learned results are retrained CV, not transferred weights.** S12/C39:L3 calls `cv_score(c52, cols)`. Moreover, S10’s best set is `"+ own-history percentiles + ALS"`, while S12’s winner is `"+ ... ALS peer-of-item"`. The headline `"54"` and `"47"` select different winners. The corresponding plain-ALS set actually falls to `"40"` hits and `"AP 0.537"` on r5.2.

- **Selection inflation cannot be quantified from these artifacts.** S11 alone compares **15 fusion variants**; S8 prints **12 model/aggregation variants**, followed by more feature sets and scenario inspections. Their errors are correlated, so a numerical correction would be invented. Treat r4.2 winners as discovery results; preselected r5.2 Stouffer as validation; S13–14 ownership/queues as discovery again.

**3. Do the conclusions follow from the numbers?**

- **S1 Finding: counts verified; density and timing overclaimed.** `"1,003 computers and 475 websites"` does not establish a dense interaction matrix; report nonzero density. `"about 36 seconds"` is not demonstrated by the retained run, which prints `"loaded in 0s"` from cache.

- **S2 Finding: attack-free dates supported; departure detail inconsistent.** `"left ... insiders 70 of 99"` leaves only 29 nondeparting insiders, contradicting `"the 30 snoopers stay"`.

- **S3 Finding: supported within its retrospective definition.** Outputs show R1/R2 `"P@20 1.0"` and job-hunter counts `"2/30"`/`"5/30"`. “Catch” should specify **top 100 over the whole test period**.

- **S4 Finding: ALS website advantage is descriptive; destination attribution exceeds the table.** `"AUC 0.697"` versus `"0.551"` supports the ranking comparison. The destination table reports `"insiders 30"` and `"normal_staff 0.0"` within `c42.dom_new`; it does not independently prove all 30 were leakers or that no normal user visited that site anywhere in the full logs.

- **S5 Finding: “ALS adds 7” means a net increase, not seven additional retained cases.** `"39"` to `"46"` hits is correct; overlap is not shown, and leakers in the top 100 fall from `"30/30"` to `"29/30"`. Seeds `"45"` and `"46"` demonstrate initialization stability, not sampling robustness.

- **S6 Finding: reported comparisons are accurate.** LR `"45"`→`"49"` and GBT `"60"`→`"60"` are supported. The incremental ALS benefit already depends on the combiner.

- **S7 Finding: “memorizes known attacks” is too strong.** `"9/30"` under scenario exclusion demonstrates deterioration under a changed task, subject to the LOSO defect. It does not identify memorization as the cause.

- **S8 Finding: weekly LOF complementarity is supported, provisionally.** `"14/30"` and `"16/30"` job-hunters support testing a drift specialist. Weekly boundary leakage and order-based subsampling qualify those results.

- **S9 Finding: improvement observed; explanations and rejection overreach.** `"dom_peer ... AUC 0.828"` versus `"a_dom ... 0.697"` is real in the outputs but confounded by different aggregation masks. The Finding’s `"1.3 to 1.5 times"` visit increase has no supporting calculation/output here; the site-lift implementation also has defects.

- **S10 Finding and plan: “best single signal on both releases” needs a metric.** On r4.2, `pw_hi_max` has `"AP 0.670"` versus R2’s `"0.728"`, and `"AUC 0.948"` versus `"0.960"`. It wins the reported hits@70 comparison, `"40"` versus `"38"`, with tie sensitivity. The claimed hidden-job-hunter improvement `"12"`→`"19"` requires repaired LOSO.

- **S11 Finding: descriptive counts correct; confidence overstated.** `"11 ... of whom insiders: 11"` supports the observed corroboration result, not calibrated high confidence or independent families. Research Findings says `"only 10 people qualified"` and should be reconciled with this output.

- **S12 Finding: “fusion did not generalize” is too categorical.** Preselected Stouffer retains an advantage over R2: `"AP 0.478"` versus `"0.428"`, hits `"38"` versus `"36"`. It fails to beat own-history percentile (`"0.479"`, `"39"`) and misses snoopers. The quoted AP fall `"0.73 to 0.48"` compares different best signals; the same percentile signal falls `"0.670"`→`"0.479"`.

- **S13 Finding: “30 of 30” is correct at top 100, but the causal story is unproven.** Raw ownership gets `"2/30"` snoopers; adjusted ownership gets `"30/30"`. Weekly aggregation and roaming discount therefore matter enormously. Compare identically aggregated/normalized naive, ALS, and ownership signals before blaming collaborative filtering’s treatment of personal resources.

- **S14 Finding: “54 among 88” is correct and exploratory.** Its breakdown is `"26/29  1/30  7/10  20/30"`: the deployed queue allocation catches only **one job-hunter**, and only 20 snoopers. `"40 of 87, because..."` overattributes r4.2’s result to the ownership queue without an ablation.

- **Queue superiority is release-dependent and budgets need matching.** S11 Stouffer already finds `"47"` at 70 reviews on r4.2, exceeding S14’s `"40"` at 87 reviews. On r5.2, Stouffer’s S12 top-100 counts sum to **40**, below the queues’ **54 at 88**; reviewing fewer users does not explain away that gain. Nevertheless, compare all methods at the same unique-person budget and report the ownership/design changes alongside it.

**4. Missed opportunities, ranked by expected value**

1. **Repair causal aggregation before adding models.** Replace S8/S10’s `week < c.cut` split with weeks wholly inside training; normalize S3’s `"typical test day"` against training or preceding history, including zero-novelty active days. This addresses several conclusions simultaneously.

2. **Run controlled, equal-budget ablations.** S13’s `"2/30"`→`"30/30"` demands a common aggregation and roaming adjustment for naive novelty, ALS, and ownership. For S14’s `"88"` reviews, report baseline/fusion hits@88, queue-without-each-specialist results, overlap, and tie ranges. Attribute ALS only its marginal unique discoveries.

3. **Make the slow queue serve job-hunters.** S12 weekly LOF gets `"10/30"` job-hunters in the top 100 versus unusual-weeks’ `"4/30"`; S14’s selected drift queue gets `"1"` at 25 slots. Compare LOF at the actual queue budget. Also test cheap train-relative domain-distribution drift followed by USB/file escalation, motivated by S1’s domain table and S2’s scenario description `"browses job and competitor sites, then copies files"`.

4. **Set queue capacity operationally, without labels.** S14’s `"25 review slots each"` is defensible as an explicit policy. Deduplicate and refill to a fixed unique-person capacity; calibrate eligibility on earlier, disjoint historical blocks. Avoid ranking zero-evidence users merely to fill capacity, and distinguish eligibility from available staffing. S14’s failed `"z ... 6"` threshold is not evidence that historical calibration cannot work.

5. **Build the smallest reproducible VM pipeline and honest demonstration.** S48 specifies `"local[3]"` and CSV/Spark intermediates; the notebook still uses `pd.read_parquet` in S1. Reuse ALS factors rather than retraining in S4/S9, and omit discarded site-lift/computer-ALS paths. Show per-scenario counts, temporal evidence, measured VM runtime, and explicitly label S13–14 as post-r5.2 exploration.

**5. Answers to the six reviewer questions**

1. **Protocol:** user ranking is fair for retrospective triage; the current `"no leakage"` statement is not. Repair S8/S10 weekly boundaries, qualify S3 test-period normalization, and fix S7’s unequal LOSO ensembles before trusting unseen-scenario numbers.

2. **Overfitting:** require an untouched third test for selected r4.2 improvements, feature/family choices, the S13 ownership heuristic, and S14 queues. S12’s preselected Stouffer `"AP 0.478"` is the strongest independent check shown, albeit subject to implementation qualifications.

3. **Ownership:** principled enough to present as a hypothesis, with `"designed after seeing r5.2"` prominently disclosed. Freeze the 80% ownership threshold, factor 50, aggregation, and budget before another CERT release. LANL can test transfer to real authentication data, but its labels describe red-team compromises rather than CERT snoopers; separate workstation-like resources and authentication types. This also contradicts S47’s `"real access logs are never released"`. [LANL dataset documentation](https://csr.lanl.gov/data/cyber1/)

4. **Queues:** a reasonable staffing/coverage policy, not yet the demonstrated universal winner. S14’s `"40 of 87"` versus S11’s `"47"` at 70 reviews is the counterexample. Predeclare capacity, deduplication/refill, minimum evidence, and review cadence; do not optimize allocations against scenario labels.

5. **Scenario 2:** prioritize weekly LOF and joint destination-drift/USB escalation; current queues deliver `"1/30"` in S14. If email data is available, test new external recipients and attachment activity using metadata, following Research Findings’ `"web and email novelty"` suggestion. Treat these as new hypotheses requiring validation.

6. **Recommender:** defensible as an experimental destination specialist, not yet essential infrastructure. S5’s `"39"`→`"46"` establishes exploratory incremental value, but S10’s mature combiner gains only `"53"`→`"54"`. S14’s destination queue has `"16"` insiders, without its marginal contribution being shown. Demonstrate improvement over identically aggregated naive/rare-site scores before claiming ALS is necessary.

**Top five changes before tomorrow**

1. Fix weekly cutoff leakage and novelty-day normalization — S8/S10’s `week < c.cut`, S3’s test-period `"median"`.
2. Repair LOSO and report top-k tie sensitivity — S7’s `/ seeds` versus `/ (5 * seeds)`.
3. Compare queues, baselines, and fusion at equal unique-person budgets; ablate ALS and roaming adjustment — S14’s `"54"` at `"88"`.
4. Correct headline claims and expose scenario coverage — especially `"best single"`, `"no leakage"`, and S14’s `"1/30"` job-hunters.
5. Freeze the revised design and run the minimal `"local[3]"` VM pipeline; present ownership/queues as exploratory, not independently validated.