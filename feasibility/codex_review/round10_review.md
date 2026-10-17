**1. Live list and cases**

- **Causal and correct.** Each flagged week contributes from its first flagged day onward; cumulative scores use no later days. ALS and roaming remain training-only ([minimal:98–122](reference/outofrole_minimal.py#L98)). In-time grading still requires **first malicious day ≤ listed day < last malicious day**.
- **Case coverage: yes for both daily lists.** Their union determines the case population; evidence is truncated at the requested day ([lines 154–165](reference/outofrole_minimal.py#L154)).
- **First-alert metrics correctly remain main-list-only** ([line 178](reference/outofrole_minimal.py#L178)).
- Coverage is **not guaranteed for every retrospective top-100 row**. Include those IDs if that review offers case-file click-through.

**2. Abstract connection: partial, substantially improved.**

- **Recommender detection:** implemented and evaluated causally; its demonstrated strength is retrospective review, with no additional live detections when combined.
- **Files:** identity-level learning remains absent. Filename uniqueness supports limiting scope; it does not establish that file modelling is impossible.
- **Access administrators:** past-use proxies remain substitutes for actual permissions and demonstrated need.
- **LinuxONE/local AI:** implementation proof remains event-day work.

No additional model is justified tonight. Extending case coverage to retrospective review rows is a small useful fix **if those rows need explanations**.

**3. Plain words**

Mostly honest. Three edits remain:

- **Line 60 — “Files could not be modelled … nothing to learn”:** replace with:  
  **“File identities were not modelled. In the CERT file logs, 100% (r4.2) and 94.4% (r5.2) of distinct filename strings were observed for only one user, limiting overlap for collaborative filtering.”**  
  The script correctly counts distinct users per filename; this statistic does not measure how much activity occurs on shared files ([file_uniqueness.py:5–12](reference/file_uniqueness.py#L5)).
- **Line 16 — “as a live list it adds nothing”:** replace with:  
  **“In the r5.2 replay, adding its live list did not increase the number of insiders caught in time.”**  
  Unchanged counts do not exclude earlier warnings for already-caught people.
- **Line 75:** change “Among insiders ever listed” to **“Among insiders ever listed on the main 20-name daily list.”**

**4. Final verdict**

- **Simple:** yes. Keep the unsuccessful live snooping queue as an evaluation control; it need not become another analyst queue.
- **Impressive and honest:** yes, after the wording edits. Lead with the existing daily-list results.
- **Abstract connection:** partial, with a clear functional recommender link and disclosed omissions.

**Remaining local fixes:** the three wording edits above; retrospective case coverage only if its rows offer case-file click-through. No further modelling is needed.

Event-day: verify Granite integration and the complete LinuxONE run. Raw CERT results were not independently rerun here.