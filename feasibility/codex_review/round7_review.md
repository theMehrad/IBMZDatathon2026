**The four blockers**

1. **Fail-closed case files: no.** The adapter, training-relative wording and raw-share strength are fixed ([lines 15–29](reference/case_file.py#L15)). The optional note and malformed-value handling still fail; details below.
2. **Replay-day-zero evidence and matched-stage strength: yes.** Evidence starts at `CUT`; both groups use their first alert ([lines 86, 139–146](reference/outofrole_minimal.py#L86)). The 0.64/0.66 variants are correctly distinguished ([Verified Numbers:200](Verified_Numbers.md#L200)).
3. **Removal proxy: yes in the documentation.** Its timing and assumed permissions are explicit ([Plain Words:18](OutOfRole_In_Plain_Words.md#L18), [Verified Numbers:189](Verified_Numbers.md#L189)). The console label still needs changing.
4. **Part 3 execution and protocol labels: yes.** Both subprocesses use `check=True`, and the differing experiment windows are explained ([notebook:8845](OutOfRole_Feasibility_v4.ipynb#L8845), [8904](OutOfRole_Feasibility_v4.ipynb#L8904), [8943](OutOfRole_Feasibility_v4.ipynb#L8943)).

**Remaining problems**

- **The note remains unrestricted factual prose.** Targeted checks accepted both `"Alice Smith stole customer records [E1]."` and `"They copied five hundred customer files [E1]."` Names and spelled-out quantities pass the regex and are displayed verbatim ([case_file.py:51–67](reference/case_file.py#L51)). The accepted self-test also says “first visit,” which training-relative novelty cannot establish ([line 79](reference/case_file.py#L79)). **Smallest fix: remove the optional note entirely.**
- **Malformed JSON values can crash instead of falling back.** `facts:[{}]` raises `TypeError` at `set(facts)`; `note:7` raises `TypeError` in `re.findall` ([lines 48–52](reference/case_file.py#L48)). Validate element/value types before using them. Add these cases to the self-test.
- **Do not transfer the evidence metric to Granite’s selections.** The 64%/85% measures C1’s top three with ties averaged ([minimal:98–102](reference/outofrole_minimal.py#L98)); Granite can select and reorder facts independently ([case_file.py:64–66](reference/case_file.py#L64)). Keep the ranked evidence visible and call this the **pre-Granite evidence-ranking result**.
- **Two plain-words corrections remain.**
  - Replace “the release we held back for testing” with **“the r5.2 replay”** ([line 40](OutOfRole_In_Plain_Words.md#L40)). Headline method selection happened after seeing results ([Verified Numbers:36](Verified_Numbers.md#L36)).
  - Replace “46% … and 31% … of insiders” with **“Among insiders ever listed, 46% … and 31% …”** ([line 72](OutOfRole_In_Plain_Words.md#L72)); that is the denominator actually used ([minimal:141–142](reference/outofrole_minimal.py#L141)).
- Change the console’s “revocation suggestions … sites people hold” to **“end-of-period access-review proxy: training person-site pairs not revisited”** ([minimal:211](reference/outofrole_minimal.py#L211)). Regenerate the saved output and Part 3 afterward.

No additional numerical contradiction found in Part 3’s recorded results.

**The three goals**

- **Simple:** yes—two short files and a clear division between detection, evidence and access advice.
- **Impressive and honest:** the replay results are impressive; the guard and wording fixes above are still needed for honesty.
- **Connection to the abstract:** **partial, unchanged**—the audiences and local explanations remain, but recommender-based detection became behavioural detection plus website advice.

**Verdict:** **not ready yet.** Remove free-text notes, validate JSON types, add regression cases, and apply the wording corrections above. These are small local fixes.

**Event-day items:** verify Granite integration, dependencies and runtime on s390x, and the complete LinuxONE dashboard flow.