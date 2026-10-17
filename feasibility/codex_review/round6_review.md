## 1. Round 5 items

References: **M** = [minimal script](reference/outofrole_minimal.py), **C** = [case_file.py](reference/case_file.py). Numbers below are source lines.

| Item | Fixed? |
|---|---|
| Activity means any daily record | **Yes.** M:27,36,48. |
| Owned sites excluded from recommendations | **Yes.** M:165–167; synthetic regression passes. |
| Basic input assertions | **Yes.** M:28–29. Domain-key uniqueness and answer-key endpoint checks remain absent. |
| Label-independent case retrieval | **Yes.** M:115–126. Labels enter evidence grading separately at M:128–133. |
| Actual first-alert evaluation | **No.** M:139–140 starts searching after the cutoff week, although lists begin at the cutoff. |
| Label-independent strength rule | **Yes.** M:135–137. The pack implementation has a rounding mismatch, below. |
| Canonical access numbers | **Yes.** Verified Numbers:90–94,187–188 match fresh output. |
| Workload definition reconciled | **No.** M:202 still reports normal-ever-listed divided by weeks, rather than first-ever entrants across all staff. |
| Unsupported departure pitch and mixed evidence slot removed | **Yes in the build plan.** Build Plan:14,91. Notebook wording remains stale. |
| Removal suggestions and static coverage | **Yes, implemented.** M:179–187; important qualifications below. |
| Reliable checked explanation and fallback | **No.** C:11–47 has substantive gaps. |

## 2. New code

**The scoring core remains sound. The explanation path needs correction.**

- **Checker fails open.** C:41 checks only dates and percentages; C:42 permits uncited values when the person’s identifier appears. Other claims need no citation. I verified that all these return **no problems**:
  - `U-017 stole 500 files [E1].`
  - `U-017 stole customer records.`
  - A visit to an unrelated domain using E1’s valid date.

  The self-test catches its chosen corruptions, but establishes neither “every number checked” nor factual support. Use constrained IDs/templates with deterministic fact rendering, or withhold free-form model prose.

- **Case-to-pack integration is incomplete.** M:124–126 returns an **unsorted DataFrame**. C:11–15 expects a **ranked list of dictionaries**. Add and test an explicit sort/convert adapter, including empty cases and normal staff.

- **Fallback invents first-ever use.** C:29–30 translates “absent from training” into “for the first time.” Repeated test-period accesses retain that flag. Replace with **“not observed in this person’s training history.”** Also qualify staff usage as **during training**.

- **First-alert timing is wrong at the boundary.** M:86,116,139–140 omit the initial test days. A synthetic trajectory first listed on day zero was reported as first listed on day five. Search from replay day zero and include corresponding case evidence; rerun affected evidence statistics.

- **Strength needs consistent timing and precision.** M:145 evaluates insiders at their graded in-time day; M:146 evaluates normal staff at their first alert. The percentages are not a comparison at the same alert stage. C:14–16 also rounds percentages before applying the threshold: a raw share of `0.0099` becomes “weak.” Apply the rule before rounding. This boundary example is not evidence that current benchmark counts change.

- **Removal suggestions are retrospective proxies.** M:183–187 uses the completed test period and end-of-period activity. Fine as an **end-of-period review**, but it cannot populate earlier replay dates. `own` means previously observed use, not verified held permissions.

- **Static coverage: fine.** M:179–181 correctly evaluates the frozen allow-list. It remains approval coverage, not demonstrated prevention.

## 3. The three goals

- **(a) Simple implementation — yes.** The numerical core is compact; retain it and constrain the explanation output.
- **(b) Impressive and honest — conditionally yes.** The detection result survives, but checker guarantees and equal-workload language currently overclaim.
- **(c) Abstract connection — partial, improved.** Access review strengthens the workflow connection; recommender-driven detection and actual entitlement analysis remain changed or absent. **The rating stays partial.**

## 4. Plain-words document

**No, not every claim is supported as written.** Changes to [OutOfRole_In_Plain_Words.md](OutOfRole_In_Plain_Words.md):

| Lines | Replacement wording |
|---|---|
| **8: deployed Granite/privacy claims** | “The planned LinuxONE build keeps processing and AI inference local and displays pseudonyms.” Describe Granite in future tense until demonstrated. |
| **12: blanket rule-tool failure** | “Valid logins can conceal misuse; analysts need a manageable review list.” |
| **16: feature descriptions** | “The score compares recent USB connections, file copies, after-hours activity and numbers of computers used with training history.” `n_pcs` does not measure new computers. |
| **17,48: checker guarantee** | Until corrected: “The checker tests citation IDs and selected percentages and dates; unsupported prose may still pass.” The self-test rejects an invented **ID**, not every invented fact. |
| **18,35,62: held-access/removal claims** | “At the end of testing, previously observed website use that did not recur becomes a suggestion for access review. Actual permissions are not available.” |
| **22: frozen/sole-source claims** | “The headline method was selected after exploratory testing. Build metrics come from the minimal script; historical controls come from the experiment scripts.” |
| **27,40: same churn/workload and held-back release** | “On r5.2, the selected method lists 80 of 99 insiders versus 40 for the baseline. Both lists hold 20 names daily; turnover differs. On r4.2 they tie.” |
| **30: real malicious action** | “At the graded in-time detection day, the top three include an answer-key-matched activity item, averaging over tied rankings.” |
| **32: strength comparison** | “Strength rule satisfied: insiders at their graded in-time day versus normal staff at their first alert.” |
| **58,64: exact abstract equivalence** | “Changed: behavioral history drives alerts; the website recommender supports access advice. Later recorded logs are replayed for evaluation.” |
| **66: file recommender verdict** | “Computer recommendations showed no useful benefit for the tested task; file recommendation was not built.” |
| **72: first-alert claim** | Currently: “The reported first-alert figures search from the Monday after the cutoff week, among insiders who were listed.” After fixing the search, replace the figures. Say **“no labeled malicious activity to cite”**, rather than “nothing malicious.” |

## 5. Notebook v4

Zero-based cell/source-line citations for [notebook v4](OutOfRole_Feasibility_v4.ipynb):

- **Steps 16 and 19 headline values: fine.**
- **Step 17’s numerical difference: explained, fine.** C53:L5 and C62:L8 identify the full-experiment variant. Label the Step 17 ladder row in C73:L29 accordingly; Verified Numbers’ ladder now uses canonical values.
- **Mixed evidence slot remains “optional for the build”:** C66:L8 and C73:L6. Replace with **“historical post-hoc experiment, excluded from the build.”**
- **Feedback generalization overclaim:** C72:L3 says feedback does not hurt generalization. The held-out S1 result falls from **30/30 to 27/30**. Replace with **“effects vary by withheld scenario.”**
- **Part 3 outputs match the fresh file.** Its first-alert, strength and removal interpretations inherit the issues above.
- **Part 3 can silently hide failures:** C77:L3 and C78:L1 print only subprocess stdout without checking exit status. Add `check=True`.
- **“Every headline number” remains too broad:** C76:L3; the minimal script does not reproduce fusion, chance controls or full workload diagnostics.
- **Verified Numbers also needs cleanup:** L176 still says 178 lines; L197 refers ambiguously to section 4’s old numbers rather than its labeled full-experiment variant.

## 6. Verdict

**Remaining local blockers:**

1. Make explanation validation fail closed; correct fallback wording and test the actual ranked case-to-pack adapter.
2. Correct first-alert boundary handling, rerun affected metrics and update their labels.
3. Present removals as end-of-period historical-use proxies, and correct the documentation above.
4. Make Part 3 fail when either subprocess fails.

**Event-day checks, separately:** Granite on LinuxONE, table-ingestion adaptation, dashboard integration, and measured VM runtime/memory.