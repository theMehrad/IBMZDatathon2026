## 1. Minimal script audit

**Faithful enough to become the numerical reference after small fixes. It is an evaluator, not yet the application.** Raw-data reproduction was unavailable; synthetic checks passed for ALS, tie-aware hit@3 and causal R2/list calculations.

Line references below refer to [outofrole_minimal.py](reference/outofrole_minimal.py).

| Finding | Assessment |
|---|---|
| **L29–59: detector timing** | Fine. Training references precede the excluded week; rolling windows include only days through the scored day. Preserve the `0.01*p.sum()` term when porting. These are end-of-day alerts. |
| **L141–148: recommender** | Fine. Catalog and preferences come from training only. ALS equations match the validated implementation. No answer-derived catalog remains. |
| **L24–25, 66–79, 150–158: labels** | Labels select evaluation populations and calculate outcomes; they do not fit scores or recommendations. The label-informed cutoff and post-hoc method selection remain disclosed design choices. |
| **L67–75, 108–109: detection/evidence definition** | Correctly implements \(F\le D<L\), with evidence through \(D\). But \(D\) is the first listing **after labeled onset**, potentially later than the analyst’s first alert. The 66%/85% evaluates that graded day. Do not describe it universally as first-alert evidence. |
| **L33, 45, 55: reference differences** | “Active” means a login occurred; the full replay uses any daily activity. Tie seed also differs from the full replay. Matching aggregate counts does not establish identical lists. Choose one contract and compare person/day selections. |
| **L89–118: evidence meaning** | Faithful to the existing aggregate-item definition. A maliciously matched day/resource item is not an exact malicious event or proof of intent. `hit_at` handles ties correctly. |
| **L145–147: actual edge-case bug** | With fewer than 20 unseen sites, `top20` includes owned sites from the `-inf` tail. Mask the returned result with `~own`. This also protects the extra-grant denominator. No effect on the supplied dataset results is established. |
| **L151–158: requests** | These remain fixed-roster, distinct-pair request equivalents. Minimal r5.2 gives **3.15→2.55**, versus **3.07→2.48** in Verified Numbers. The training cutoff differs from the full least-privilege experiment. Adopt one canonical result and update every table. |
| **L173: workload** | **4.6/4.8** means distinct normal staff ever listed divided by elapsed weeks. It does not reproduce **4.8/5.3** first-ever entrants across all staff with startup weeks excluded. Rename or recompute. |
| **L160–179: catalog block** | Fine as a frozen “absent from training” rule. Owner filtering and distinct person-day cost are fixed. Update the pitch’s dynamic “nobody has ever visited” wording. |

Add cheap assertions for unique table keys, sufficient training history, insider presence, nonnegative attack offsets, and agreement between answer timestamps and listed start/end dates. The all-period roster at L25 is harmless here given the recorded absence of new hires; assert that assumption.

“Every headline number” remains too broad: the script omits chance controls, fresh-alert counts, scenario delays, weekly distinct workload and malicious-access approval coverage.

## 2. Simplicity

The smallest system preserving the selected numerical results is:

- The three Spark tables, preserving all nine detector features.
- Personal weekly comparison, seven-day decay and daily list.
- One label-independent `case_items(user, day)` function returning ranked C1 evidence with provenance.
- The existing website ALS model, history-plus-recommendation suggestions and frozen catalog block.
- A small interface and one checked Granite explanation.

**Cut:** fusion from the application, specialist queues, ownership models, feedback learning, richer recommenders, optional mixed ALS evidence, and the historical ladder from the pitch. Keep benchmark comparators offline.

The optional ALS evidence slot changes the evaluated evidence rule and adds another post-hoc choice. Website access advice already gives the recommender a clear job.

Drop the unsupported “most insider tools find the culprit after they’ve left” comparison. Also remove the stale “fusion as default” wording and update the build plan to name the minimal script.

## 3. Impressive and honest

> **In a daily replay of synthetic CERT r5.2 logs, our selected method listed 80 of 99 insiders during their labeled attacks and before their last malicious day, versus 40 for the 28-day personal baseline.**

Two supporting numbers:

- At that graded detection day, C1’s top three evidence items contained a maliciously labeled item for **85%** of insiders caught in time.
- The recommender recalled **19%** of future new person/site pairs, versus **13%** for popularity at the same recommendation budget.

Lead with detection: it answers the security problem most directly. State nearby that selection occurred after inspecting results, r4.2 ties its baseline, and list turnover differs. Keep the late-S1-label caveat visible. These are replay findings, not independent deployment validation.

## 4. Connection to the abstract

“Implemented” below means supported by the supplied code; Granite and LinuxONE delivery still require demonstration.

| Abstract promise | Delivered component or gap |
|---|---|
| **Problem: misuse of valid access without greater exposure** | Addressed through synthetic insider activity. Patient/customer-record monitoring and explicit role authorization are untested. |
| **Learns normal files and machines** | **Changed:** personal activity counts plus website recommendations. No file-resource recommender; machine recommendations were dropped. |
| **Flags access it would never recommend** | **Changed:** behavioral deviations generate the list. Recommendation scores advise access. |
| **AI on the same server explains why** | Causal evidence selection exists. Granite generation and checking are planned, not implemented in this script. |
| **Audience 1: analysts receive short, explained lists** | Daily list implemented; explanation delivery pending. No demonstrated comparison with thousands of commercial rule alerts. |
| **Audience 2: privacy/compliance officers receive an audit record** | Aggregate evidence supports investigation. Exact event provenance, saved case records and checked explanations remain delivery work. |
| **Audience 3: administrators identify held permissions never needed** | **Missing/changed:** no entitlement inventory or revocation analysis. The delivered advisor proposes website pre-approvals. |
| **Audience 4: patients/account holders benefit without outside AI** | Local processing is the intended architecture. Actual patient records and a complete local inference flow have not been demonstrated. |
| **Audience 5: IBM Z organizations run beside their data** | LinuxONE deployment is pending. A VM demonstration establishes deployment feasibility, not integration with core records. |
| **Data: CERT activity logs and LDAP** | CERT used; the final core uses logon, USB, file and web aggregates. Email, LDAP and file identities are absent from the minimal model. |
| **Answer-key evaluation** | Delivered. Labels grade coverage, evidence and access simulations. |
| **Method: Spark matrices, early ALS training, later replay** | Partly delivered: Spark tables, training-only website ALS and temporal replay. PC/file matrices and ALS-driven detection changed. |

**Overall: partial.** The security workflow, recommender and local-AI architecture remain connected. The central detection mechanism and permission-removal promise changed. Explicitly explaining that pivot is sufficient; adding decorative models would weaken the build.

## 5. One-paragraph plain explanation

OutOfRole compares each employee’s recent activity with their own earlier habits and gives analysts a short daily review list. For each listed person, it gathers supporting records available by that day. An AI running on the same server turns those records into an explanation, which software checks against the evidence. A separate model suggests websites the employee may use next, helping reviewers handle routine access requests. Sites absent from the company’s training history are held back. Tests use synthetic workplace records, so the results show promise rather than proven protection in a real organization.

## 6. Remaining blockers

- **One consistent numerical reference:** reconcile request counts, workload definitions, active-day rules and tie seeds; fix the recommendation mask.
- **A label-independent case path:** generate evidence for every actual daily alert, including normal staff and pre-onset listings. `FLAG` currently selects graded true positives.
- **Checked explanation delivery:** implement provenance IDs, citation/value/date checks and an evidence-only fallback. Do not adopt the insider-median strength threshold while claiming label-free calibration.
- **LinuxONE smoke test:** verify table ingestion, complete replay, recommendations and a local Granite case. The Parquet reads need adaptation to the stated environment. Measure the target runtime; the reported local runtime excludes rebuilding the Spark tables.

**Ready to port after those small reference fixes; not yet ready to call the complete build validated.**