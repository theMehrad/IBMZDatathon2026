# OutOfRole: Research Findings (Oct 16)

Five research passes: published work on the CERT dataset, recommender and graph methods for access anomalies, commercial insider-risk products, AI acceleration on LinuxONE, and other datasets plus real-world statistics. Only sources the researchers actually opened are listed. Numbers from our own tests live in `evidence/Verified_Numbers.md` and the notebook (`evidence/Study_Notebook.ipynb`); `9_Archive/Feasibility_Findings_old.md` is superseded.

## 1. What published work on CERT found

| Work | What they did | Lesson for us |
|---|---|---|
| [Le & Zincir-Heywood, TNSM 2021](https://web.cs.dal.ca/~lcd/pubs/TNSM2021.pdf) | Day and week counts as a **percentile of the same user's own history**; autoencoder, Isolation Forest, LOF ensembles | Percentiles beat z-scores and transferred to another release. We tested it: biggest single gain tonight. |
| [Le et al., DISSECT 2019](https://web.cs.dal.ca/~lcd/pubs/lcd_dissect19.pdf), [Le thesis 2021](https://web.cs.dal.ca/~mheywood/Thesis/DucLe2021.pdf) | Session, day and week granularity, supervised with few labels | Scenario 2 (job-hunter) is the hardest for everyone: 12.5 to 74% detection. Week-level helps. |
| [Tuor et al. 2017](https://ar5iv.arxiv.org/html/1710.00811) | Deep and recurrent models on user-day counts, scores split per feature | Per-feature contributions double as analyst explanations. |
| [Garchery & Granitzer 2020](https://arxiv.org/pdf/2007.06985) | Event-level novelty (new web sites, new email recipients) | Scenario 2 is best caught by web and email novelty; simple rules are strong baselines. |
| [Yuan et al. 2018](https://www.iccs-meeting.org/archive/iccs2018/papers/108600047.pdf), [arXiv 2506.23446](https://arxiv.org/html/2506.23446), [arXiv 2602.11019](https://arxiv.org/html/2602.11019v1) | LSTM-CNN, transformer, convolutional autoencoder | Headline numbers often use event-level metrics, row-level splits or subsets of users, so they are not comparable to ranking all 1,000 users. |

**Pitfalls judges may raise:** event-level metrics, look-ahead leakage (departure dates in LDAP, z-scores over the whole timeline), tuning on the 70 labels, and leaky row-level splits. Our protocol addresses all four: user-level ranking, a train window that ends before any insider activity (with the boundary week dropped; the cutoff itself was chosen with the labels), the departure field never used, and a hold-one-scenario-out test. Several design choices were still made with r4.2's answers in view, so r5.2 served as the real test, and the out-of-role view (designed after r5.2) still needs an untouched one.

## 2. The recommender part has strong precedent

| Work | Takeaway |
|---|---|
| [Menon et al. 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC3967851/) | Collaborative filtering to catch snooping in hospital records; latent "fingerprints" beat plain logistic regression. |
| [Chen, Nyemba & Malin, CADS](https://pmc.ncbi.nlm.nih.gov/articles/PMC3905623) | Unsupervised: users far from their access community are suspicious. |
| [Google Facade](https://arxiv.org/abs/2412.06700) | Scores access by lift over popularity; filtering accesses common to many users cut false positives over 20x. |
| [Microsoft, Modell et al.](https://www.microsoft.com/en-us/research/uploads/prod/2022/01/modell_paper.pdf) | Scores an access by distance to the nearest previous user of that resource. |
| [Hu, Koren & Volinsky](http://yifanhu.net/PUB/cf.pdf) | Implicit ALS favors popular items, so correct for popularity. |

**Pitch line:** these works score access by how unexpected it is under a collaborative-filtering model, and our abstract promised the same: recommender-based detection. Our tests showed that own-history baselines detect better (the own-history weekly percentile, after Le & Zincir-Heywood), and used as a detector the recommender gave no gain over popularity, tuned or not. So the recommender moved to access advice: it suggests which access to pre-approve (least privilege). Tuned without labels, it catches 0.211 of normal staff's next new websites in its top 20 on r4.2, against 0.145 for popularity (0.190 vs 0.130 on r5.2). Only 28% (r4.2) and 42% (r5.2) of its extra grants were later used, so it is a suggestion list, and its coverage figures are static, not prevention. See `evidence/Verified_Numbers.md`, sections 1, 3, 5 and 9.

### Least privilege

- [Microsoft Entra access-review recommendations](https://learn.microsoft.com/en-us/entra/id-governance/review-recommendations-access-reviews): reviewers get system recommendations to keep or deny each person's access. A user who has not signed in recently gets a Deny recommendation, and a machine-learning "user-to-group affiliation" score flags members who sit far from the rest of the group in the org chart.
- [SailPoint recommendations](https://www.sailpoint.com/solutions/recommendations): a thumbs-up or thumbs-down on access requests and certifications, based on peer groups, identity attributes and access activity; low-risk access can be approved automatically.

Our advisor applies the same idea to websites: tuned ALS suggests which of each person's likely next sites to pre-approve, and a rule blocks sites new to the whole company (`code/experiments/least_privilege_full.py`, `org_novel_sites.py`).

### Analyst feedback (tested and dropped)

- [Das et al., ICDM 2016, "Incorporating Expert Feedback into Active Anomaly Discovery"](https://web.engr.oregonstate.edu/~afern/papers/icdm16-das.pdf): show the analyst the top-ranked case, take their verdict, and re-weight the detector ensemble before choosing the next case (Active Anomaly Discovery, AAD).
- [Siddiqui et al., KDD 2018, "Feedback-Guided Anomaly Discovery via Online Optimization"](https://doi.org/10.1145/3219819.3220083): the same feedback loop, framed as online optimization of the detector weights.

We tested AAD-style re-weighting of our detector families: 57 vs 55 insiders found in 100 reviews on r4.2, and 42 vs 43 on r5.2; across 40 subsamples the gain was +0.2 ± 0.9 and +0.1 ± 1.0. With job-hunters hidden from training it places 22 of 30 in the top 100, against 19 for frozen fusion and 4 to 7 for trained combiners. No reliable gain, so it is dropped (`evidence/Verified_Numbers.md`, sections 5 and 9).

## 3. How commercial products score risk

- [Microsoft Sentinel UEBA](https://learn.microsoft.com/en-us/azure/sentinel/identify-threats-with-entity-behavior-analytics): peers are the 20 users with the most shared group memberships; explanations are plain flags such as "first time user performed action" or "uncommon among peers".
- [Microsoft Purview Insider Risk](https://learn.microsoft.com/purview/insider-risk-management-policies): an alert is spotlighted only with a high score **and** at least 3 corroborating conditions; users are pseudonymized by default.
- [Splunk risk-based alerting](https://help.splunk.com/en/splunk-enterprise-security-7/risk-based-alerting/7.3/identify-threat/default-risk-incident-rules-in-splunk-enterprise-security): risk accumulates per person; an incident fires on a total threshold or on many distinct tactics.
- [Google SecOps](https://docs.cloud.google.com/chronicle/docs/detection/risk-analytics-overview): strongest finding plus 0.2 times the rest.

We tested the corroboration idea: on r4.2, all 11 people flagged by 2 or more signal families above their 99th percentile were insiders; on r5.2, 14 of the 20 were. That's useful as a **"high confidence" tier** in the dashboard, not as the main ranking.

**Granite explanation rules** ([Audit-LLM](https://arxiv.org/html/2408.08902), [OWASP LLM01](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)):
1. Give Granite a small evidence pack with an ID per fact (signal, value, the person's own normal, team normal, dates) and require it to cite IDs. Check the numbers in code afterwards.
2. Treat log text (URLs, file names, email text) as data, never instructions. No tools; it recommends, the analyst decides.
3. Stable pseudonyms (U-017) that keep role and team; map back to real IDs in code.

## 4. Running it on LinuxONE (IBM's own repos)

| Piece | Where it should run | How |
|---|---|---|
| Autoencoder | **AI chip (Telum)** | Keras with `ibm-zdnn-plugin`, or PyTorch with `torch_nnpa` (`model.nnpa()`), both preinstalled. Score in graph mode (`model.predict`). |
| Combiner | **AI chip** | Train in XGBoost (preinstalled), then load into Snap ML (`pip install snapml`, `import_model(..., 'xgb_json', tree_format='zdnn_tensors')`). |
| Isolation Forest, LOF, ALS, logistic regression | CPU | Say so honestly; there is no accelerated path for them. |
| Spark | CPU | Not in the image: install OpenJDK 17 and PySpark. **No pyarrow for s390x**, so avoid pandas UDFs. Use `local[3]` and set driver memory before Spark starts. |
| Granite | CPU or chip | Reuse the loan-approval demo's model file (must be big-endian). Pre-generate the 10 explanations. |

**Proof for the video:**
- `uname -m` (s390x), `lscpu`, and `grep nnpa /proc/cpuinfo`
- `docker ps` with the 148.100.x.x prompt visible
- accelerator logs (`TF_CPP_VMODULE=remapper=1` or `TORCH_NNPA_DEBUG=1`)
- the same scoring timed with and without the chip

Sources: [jupyter-lab-ml](https://github.com/linuxone-community-cloud/jupyter-lab-ml), [ibm-zdnn-plugin](https://github.com/IBM/ibm-zdnn-plugin), [IBM accelerated PyTorch](https://github.com/IBM/ibmz-accelerated-for-pytorch), [Snap ML on Z](https://github.com/IBM/ibmz-accelerated-for-snapml), [llama.cpp on s390x](https://github.com/ggml-org/llama.cpp/blob/master/docs/build-s390x.md).

## 5. Other datasets

| Dataset | Fit | Note |
|---|---|---|
| **CERT r5.2** | Best quick test | Same format, 2,000 staff, 99 insiders, adds **scenario 4: logging into colleagues' computers**. Downloaded and tested: snoopers are caught by weekly persistence of logins to unusual computers (27 to 30 of 30 in the top 100), not by the recommender as such. |
| **[LANL multi-source](https://csr.lanl.gov/data/cyber1/)** | Best real-world test | Real (not synthetic) authentication logs with red-team labels, one of the few public releases of real access data: 58 days of enterprise logons, 12,425 users, red-team labels; user-to-computer only, no org chart. About 12 GB, request form. |
| [Amazon Employee Access](https://www.openml.org/api/v1/json/data/qualities/4135) | Small side test | Real access requests; labels are manager denials, not misuse. |
| CERT r6.2, TWOS, RUU, Schonlau, DARPA OpTC | Poor | Too few insiders, unavailable, dated, or not insider threat. |

## 6. Real-world numbers for the pitch

- **Desjardins (bank):** one employee leaked data on about 9.7 million people over at least 26 months; there was no behavior analytics, and police found it. [Canadian privacy regulator, PIPEDA #2020-005](https://www.priv.gc.ca/en/opc-actions-and-decisions/investigations/investigations-into-businesses/2020/pipeda-2020-005/)
- **Texas HHSC (government):** employees accessed **61,104** public-assistance accounts "without a clear business reason"; seven fired. [Texas Tribune, Jan 2025](https://www.texastribune.org/2025/01/17/texas-hhsc-food-stamp-fraud-data-breach/)
- **Cost:** malicious insiders were the costliest initial attack vector in IBM's 2025 report, $4.92M per breach; healthcare averaged $7.42M. [Summary](https://www.bakerdonelson.com/ten-key-insights-from-ibms-cost-of-a-data-breach-report-2025)
- **Healthcare:** internal actors in 19% of 1,438 confirmed breaches. [Verizon 2026 DBIR healthcare snapshot](https://www.verizon.com/business/resources/reports/2026-dbir-healthcare-snapshot.pdf)
- Vendor-sponsored, quote with care: $19.5M average annual insider cost per organization, 67 days to contain. [Ponemon / DTEX 2026](https://www.dtex.ai/newsroom/press-releases/insider-risk-costs-rise-as-ai-creates-new-blind-spots/)
