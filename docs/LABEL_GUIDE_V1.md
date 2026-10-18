# Label guide v1 and quality-check protocol

## Purpose

Measure whether the supplied Granite 350M Base model follows a defined triage policy, selects relevant citations and remains responsive. This is a **synthetic development check**, not a CERT accuracy result, a held-out evaluation, or evidence that visits/USB use establish wrongdoing.

The change is opt-in. The detector, ALS settings, evidence scores, label allowlist and validator are unchanged. The existing five labels remain; the source overview's sixth sabotage label is still separate unfinished work.

## Versioned guide

The executable prompt text lives in `code/label_guide.py`, version `outofrole-label-guide-v1`. `prompt_for(pack, 'none')` returns the exact pre-guide prompt. `prompt_for(pack, 'v1')` prepends the policy and leaves the observations/JSON contract intact.

| Label | Supporting observation / boundary |
| --- | --- |
| possible data leak | Known leak-destination visit or explicitly observed external disclosure. A visit is not proof of an upload. |
| possible data theft | An explicit collection/copy-to-removable-media observation. USB connection or job-site browsing alone is not enough; do not invent copying. |
| possible snooping | Explicit colleague-computer ownership or unauthorized-search context. A single unfamiliar PC is not enough, and the model must not invent its owner. |
| unusual after-hours activity | New after-hours activity is the main concern, without a more specific supported pattern. |
| weak evidence | No specific pattern is supported. Strong novelty/rarity does not imply malicious behavior. |

When multiple patterns are supported, the declared demonstration priority is **leak > theft > snooping > after-hours**. Weak packs retain their existing forced weak-label rule. This is a project triage convention, not an external security standard.

Ask for **one or two directly supporting fact IDs**, not every fact. Neutral, familiar-computer context should not be cited as suspicious support. For weak evidence, cite the limited observations under review. This selection instruction is tested independently; the grammar continues to permit every known ID and does not encode the expected citation answers.

## Frozen fixtures

`evidence/quality/label-guide-v1.json` contains six hand-authored examples. Expectations were written before native model execution. Person identifiers are neutral; fixture names, descriptions and expected labels are **not sent to Granite**.

| Order | Example | Expected label |
| --- | --- | --- |
| 1 | Leak destination plus neutral distraction | possible data leak |
| 2 | New USB use without an observed copy | weak evidence |
| 3 | Explicit copy observation, no leak destination | possible data theft |
| 4 | After-hours activity as the main concern | unusual after-hours activity |
| 5 | Novel documentation site without suspicious behavior | weak evidence |
| 6 | Leak destination plus explicit copy | possible data leak |

All packs satisfy the existing **strong** novelty/rarity rule. Consequently, weak labels in examples 2 and 5 are real choices among all allowed labels, not grammar-forced answers.

In mixed example 6, the leak-site observation E1 is mandatory; E2 (explicit copying) is permitted as secondary, competing-pattern context. Each cited fact need not independently establish the chosen pattern. Copying alone does not establish external disclosure. The neutral computer observation E3 is forbidden. Repeated IDs fail the citation gate even if the existing validator accepts/deduplicates them.

**Evidence limitations:** examples 3 and 6 deliberately contain synthetic, explicit file-copy observations. Current `case_items()` produces computer, website, USB-use and after-hours facts; this change does not add a production file-copy fact type. Passing those fixtures would show response to richer supplied evidence, not establish that the current exporter supplies it. The after-hours fixture uses a made-up organization where that action is rare, not CERT's measured staff share. There is no positive snooping fixture or sabotage fixture in this first suite, so it does not validate every attack class.

## Three separate gates

1. **Contract:** existing validator accepts JSON/known label/known fact IDs, and generation finishes normally. Malformed, truncated, unavailable-runtime and timeout outcomes fail.
2. **Label:** the chosen label equals the frozen policy expectation.
3. **Citations:** required evidence IDs are included, listed neutral distractors are excluded, and no more than two distinct facts are cited.

A selected case passes only if all gates pass. A valid theft label on the leak fixture fails the label gate. Citing every fact on a fixture with a neutral distractor fails the citation gate. A fallback is correct safety behavior but a failed quality case.

For the first bounded native test, the pass mark is **all three selected cases pass all gates**. The full suite pass mark is **all six pass**. Partial results must stay labelled partial. Failures are findings; do not relabel expected answers after seeing output. Revise the guide/fixtures under a new version if the policy is deliberately changed, preserve old artifacts and retest. These are development checks, not independent unseen-test claims.

## LinuxONE commands

Fetch and fast-forward the existing separate runner worktree; preserve the data symlink and original checkout's changes. No new downloads, data rebuilds or package installs are required for the known container.

```bash
cd /home/linux1/shared/ibmzdatathon2026-runner
git status --short
# Continue only if there are no modified tracked files; ?? data is expected.
git fetch origin && git merge --ff-only origin/feat/linuxone-granite-runner
```

Preview all frozen expectations without loading a model:

```bash
docker exec -w /home/ibm-user/shared/ibmzdatathon2026-runner \
  notebook python3 code/quality_check.py --list --limit 6
```

Start with **three** synthetic cases, loading the 350M model only once:

```bash
docker exec \
  -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 \
  -w /home/ibm-user/shared/ibmzdatathon2026-runner \
  notebook python3 -u code/quality_check.py \
    --model /home/ibm-user/granite-4.0-h-350m-base-be.f16.gguf \
    --model-mode completion --label-guide v1 \
    --limit 3 --max-tokens 64 --timeout 60 --startup-timeout 60
```

The guide adds prompt tokens, so the earlier 10.7-second average is **not a guaranteed new latency**. If a case times out, the worker is terminated and remaining selected cases get recorded failures; it does not keep reloading or silently switch to unconstrained generation. Inspect the reasons before changing limits. An output cap can still truncate a grammar-constrained response.

If the initial native result is acceptable, repeat with `--limit 6` for the full suite. To compare against the original prompt on the same expectations, use `--label-guide none`; this is recorded as the baseline, not secretly mixed with guided results.

## Outputs / interpretation

By default, each invocation creates a new restricted folder under the ignored `data/quality_runs/` directory with config, exact suite snapshot, source/model/fixture hashes, runtime log, incremental `results.jsonl` and `summary.json`. Explicit `--output PATH` overrides that location: choose a private, untracked directory and do not commit its contents. Expected answers stay outside model inputs. Existing output directories are never overwritten.

Summary fields separate `contract_accepted`, `label_matches`, `citation_matches`, `quality_passed` and `quality_failed`. `selected` and `suite_total` prevent a passing subset from being presented as a full-suite result; `complete_suite` and `partial_quality_check` make that distinction explicit. Exit 0 means every selected case passed; exit 2 means at least one selected quality failure; exit 1 is a configuration or other fatal error. CLI argument errors also use exit 2 before an output summary exists.

The command saves raw model responses for diagnosis, but those are not substituted for the deterministic analyst renderer. A security analyst still makes decisions. Do not report these fixtures as measured insider detection or general real-world security performance.

## Using the guide on actual saved packs

The runner accepts `--label-guide v1`; its default remains `none` for baseline reproducibility. Keep `--structured-output` and `--model-mode completion` for 350M. The explicit `--allow-runner-update` override now permits only runner and label-guide changes; preparation's scorer, table-loader and validator hashes must still match. Both preparation and current code hashes are retained. No scorer change, answer-key retuning or evidence re-export is needed for a prompt-only comparison.

## Verification status

Automated tests check grading behavior, fixture consistency, neutral identifiers, non-forced weak choices, actual CLI execution with explicitly simulated model adapters, baseline prompt preservation and original runner regressions. These tests are **not native Granite inference**. Native 350M quality-suite execution must be performed on LinuxONE and its actual output reviewed before claiming improvement.
