All four fixes are correctly implemented for the current calls. Your quoted outputs are correct. **C = zero-based v3 cell; verification is from code and recorded outputs, without rerunning data.**

**(a) Fix verification**

- **Fusion storage:** S11/C35:L31–32 guards assignment with `"if store:"`; S13/C42:L52 calls `fusion_rows(c, FAM_OWN, store=False)`. Ownership-augmented fusion therefore preserves the frozen score used in Step 14.
- **Common ownership discount:** S13/C42:L40–42 passes `base_away` to all three calls: `weekly(te.foreign, base_away)`, `weekly(te.new, base_away)`, and the recommender-filtered equivalent. The denominator and weekly aggregation now match.
- **MPR:** S15/C48:L19 uses `rankdata(-A[i, cand], method="average")`; L22 passes the unclipped `U[...] @ V.T`. This correctly removes both arbitrary tie ordering and clipping-induced ranking ties.
- **Queue capacity:** S14/C45:L25 adds `assert K <= len(c.users)`, preventing the previously identified oversized-budget loop.

One conditional issue remains: joint primary/secondary queue ties still inherit input order through C45:L7’s `sort_values(["a", "b"], ...)`. Their effect on these outputs is unverified.

**(b) Numbers**

S14/C45 confirms all your equal-budget readings:

| Insiders among 100 reviews | r4.2 | r5.2 |
|---|---:|---:|
| Four queues | “42” | “53” |
| R2 | “44” | “39” |
| Own-history percentile | “43” | “44.6” |
| Frozen Stouffer | “55” | “43” |
| Reference trained LR | “63” | “55” |

- **Common-discount snoopers:** S13/C42 confirms ownership/naive/recommender all `"27/30"`, with P@20 `"0.85"`, `"0.70"`, `"0.75"`. Ownership improves early precision here, not top-100 snooper coverage.
- **Website MPR:** S15/C48 confirms ALS/popularity `"35.9"/"35.5"` and `"35.8"/"38.3"`, unchanged **at displayed precision**.
- These ownership controls do not replace the queues’ original `own_weeks_adj`—S14/C45:L1 still names that signal.

**(c) Claims for judges**

Safe, qualified as **exploratory retrospective results on synthetic CERT data**:

- **Personal percentiles perform consistently near the top:** P@20 `"1.00"`/`"1.000"` and expected hits@70 `"39.4"`/`"40.3"`—S10/C32, S12/C38.
- **Frozen fusion beats R2 on both releases:** top-100 discoveries `"55 versus 44"` and `"43 versus 39"`—S14/C45.
- **Persistence and roaming adjustment matter more than the computer scoring distinction:** common-discount snooper coverage is `"27/30"` for all three—S13/C42.
- **Recommender features show conditional supervised value:** naive→both yields `"51→52"` and `"45→49"` hits@70—S15/C50. This does not establish independent generalization.
- **Job-hunters remain difficult:** four queues find `"4/30"` and `"2/30"`—S14/C45.

Drop:

- **“Four queues are best”**: frozen fusion wins r4.2 `"55 versus 42"`; removing destination improves r5.2 `"59 versus 53"`—S14/C45, S15/C50.
- **“Ownership fundamentally outperforms ALS”** or **“ALS adds seven”**: common-discount coverage ties at `"27/30"`; revised incremental gains differ—S13/C42, S15/C50.
- **“Percentiles are best on both releases,” “fusion did not generalize,”** and operational or independently validated claims: r4.2 R2 AP `"0.728"` exceeds percentile `"0.666"`; retrospective normalization explicitly uses the `"whole test period"`—S3/C11, S10/C32, C3:L40.

**(d) Recommended 24-hour build**

Build a **retrospective triage dashboard using frozen Stouffer as the default ranking**, with R2 and percentile comparison views, feature contributions, and timelines. Its advantage over R2 held on both releases—`"55/44"` and `"43/39"`—S14/C45. Keep ALS within this tested configuration without presenting its individual necessity as proven.

Show ownership/persistence as an **experimental investigation view**, without reserved queue slots. Independent ownership generalization, alternative allocations, live detection, Granite explanation reliability, and 3-vCPU runtime remain **untested**; S13 explicitly discloses post-r5.2 design, and platform C53 recommends `"local[3]"` without supplying that benchmark.