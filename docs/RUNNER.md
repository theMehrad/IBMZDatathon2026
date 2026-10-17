# OutOfRole runner: one day, core analysis + checked Granite cases

## Scope / implementation contract

The runner executes the existing full scoring/evaluation script for one release, exports the selected day's original daily review list in its deterministic score/tie-break order, waits for the scoring child to exit, then starts one Granite model worker and labels the exported packs in order. A person is never removed by Granite. The answer key is still required by the existing grading script but is not included in packs or used by the runner to select people or dates.

This is **batch integration**, not a dashboard, monthly retraining, a final-judge reranker or a semantic-accuracy evaluation. It intentionally leaves ALS parameters, labels, prompt and validator unchanged. The current contract has five labels and the previously observed theft/leak ambiguity remains. `ACCEPTED` means response-contract validity, not a correct or justified security classification. Facts are pseudonymized, not fully anonymized: computer and website identifiers remain in evidence.

## Getting this branch onto LinuxONE safely

The original server checkout contains a local CSV compatibility edit and an untracked notebook. Do not reset or stash them blindly. The safest first run uses a **new Git worktree** with the same dataset; it does not copy the data or modify the original checkout.

In the IBM server SSH terminal (tmux is fine):

```bash
cd /home/linux1/shared/ibmzdatathon2026
git fetch origin feat/linuxone-granite-runner
git worktree add --detach /home/linux1/shared/ibmzdatathon2026-runner origin/feat/linuxone-granite-runner
```

If the new path already exists, stop and inspect it rather than overwriting it. Run the following once to link this new checkout to the existing data **using its container-visible path**:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('/home/linux1/shared/ibmzdatathon2026-runner/data')
if p.exists() or p.is_symlink():
    raise SystemExit('STOP: data path already exists; inspect before proceeding')
p.symlink_to('/home/ibm-user/shared/outofrole/data', target_is_directory=True)
print('Data link created; dataset was not copied.')
PY
```

That absolute link is intended for use inside the container; host-side Python may see a dangling link. Do not change the shared mount. Keep data and generated outputs out of Git; the existing `data/` ignore rule covers normal data directories but not necessarily the symlink itself. Never use `git add .` on the server.

## Run on LinuxONE

Check `free -h` first. Do not run heavy notebooks/scoring alongside Granite. This runner releases its scoring process before loading the model; it does not stop other users' jobs.

```bash
docker exec \
  -e OPENBLAS_NUM_THREADS=1 \
  -e OMP_NUM_THREADS=1 \
  -w /home/ibm-user/shared/ibmzdatathon2026-runner \
  notebook python3 -u code/runner.py run \
    --release 4.2 \
    --day 2010-08-02 \
    --model /home/ibm-user/shared/models/granite-3.3-2b-instruct-be.Q4_K_M.gguf

echo "Runner exit status: $?"
```

The example date is a fixed integration-demo date, not selected by checking the answer key and not evidence of model accuracy. Choose another explicit replay date if needed. No dataset/model download or installation is performed. The day must be within the release's replay period. Stage 1 runs the existing full release report, but evidence for classification stops at the selected day. A day may have fewer than 20 names if fewer have positive running scores.

`auto` table mode prefers complete Spark CSV exports in `data/cache/r4.2_csv/{daily,pc_pairs,dom_pairs}`, otherwise Parquet. A present but incomplete CSV export is an error, not a silent fallback. `--table-format csv` or `--table-format parquet` can force one reader. No change to model/scoring parameters is made.

## Outputs and interpreting success

The command prints an exact run directory under `data/runs/`. Each run is new; an explicit existing `--run-dir` is never overwritten.

```text
<run>/
  scoring.log               Original scorer's report and errors
  packs.json                Original ranks, scores, pseudonymized packs, code hashes
  preparation.json          Digest of the prepared packs and source-code hashes
  attempts/<timestamp>/
    config.json             Model SHA-256, path, runtime identity, generation settings
    granite.log             Runtime diagnostics, separate from analyst case text
    results.jsonl           Incremental raw replies, finish reasons, validation, timing
    case_files.txt          Deterministic analyst-facing case files
    summary.json            Accepted/fallback counts; no claimed semantic accuracy
```

Outputs use restrictive new-file permissions and stay under git-ignored data by default. The preparation digest detects accidental edits to packs; it is not a signature or protection against someone who can rewrite both packs and manifest. CSV readers preserve user/computer/domain identifier text across parts, including leading zeros and strings such as NA. Dates before the known replay cutoff fail before scoring; the actual upper bound is checked after the reference scorer loads the data. Do not commit or redistribute outputs. Raw model text is retained for debugging but is never used as the rendered analyst narrative.

- Exit **0**: all attempted cases were accepted (or there were no cases). With a diagnostic limit, inspect `skipped` and `partial_test`: it is not a completed full batch or a classification-accuracy score.
- Exit **2**: the run completed with explicit safe fallbacks. Inspect `summary.json`, the per-case problems and `granite.log`.
- Exit **1**: preparation/configuration or another fatal error. Inspect `scoring.log` if stage 1 failed; do not infer that Granite ran.
- CLI argument errors also use argparse's exit 2, but occur before a summary exists.

Missing model/runtime, missing chat template, worker error, or timeout preserves every selected name with a fallback. If the model worker fails or times out, it is terminated and remaining names receive explicit fallbacks rather than silently disappearing or spawning repeated model loads. Invalid JSON or unknown facts affect that case; later cases continue. Token-limit completions are never accepted, even if the emitted prefix happens to be valid JSON. Empty packs fall back without being sent to the model. JSON grammar constraints are opt-in through `--structured-output`.

Default model limits: context 2048, threads 2, batch 128, GPU layers 0, temperature 0, output 128 tokens. Startup timeout is 180 seconds; per-case timeout is 300 seconds. `--context`, `--threads`, `--max-tokens`, `--startup-timeout` and `--timeout` are explicit overrides. A long prompt can exceed the small context; it then falls back, not silently truncates evidence. Measure before increasing limits on the 8 GB VM.

## Re-run Granite without repeating scoring

Use the printed run directory:

```bash
python3 code/runner.py infer --run-dir /absolute/container/path/to/run --model /absolute/container/path/to/model.gguf
```

Run this inside the same notebook container/environment. Each `infer` creates a separate attempt, preserving old outputs. Source hashes must match the preparation snapshot by default. `--allow-runner-update` explicitly permits **only runner.py** to differ and records the prepared and current hashes; scorer, table loader and validator changes still require fresh preparation. A model-only retry or generation-limit change does not require scoring again.

To export packs without starting Granite, use `prepare --release 4.2 --day 2010-08-02`. The CLI requires a model path only for `run` and `infer`.

## Constrain JSON and test only one case

Add `--structured-output` to `run` or `infer`. For each nonempty pack the worker compiles a `LlamaGrammar` from a JSON schema: exactly `label` and `facts`, an allowed-label enum, and a nonempty list of the pack's fact-ID enum. Weak packs permit only `weak evidence`, matching the existing validator. Grammar support is required in this mode; construction/API failures fall back explicitly rather than silently retrying unconstrained. The current runtime must still be exercised to establish native grammar compatibility. The prompt and validator remain unchanged. Structure/known IDs are not evidence that a label is justified; constrained mode changes generation and should be compared with the unconstrained baseline.

`--max-cases 1` sends only the first review entry to inference. Remaining names stay in the output with `skipped: true` and `NOT INFERRED` progress status; they are not counted as inference failures or accepted classifications. The summary reports the full list total, attempted accepted/fallback counts and skipped count. A partial successful diagnostic run has status `partial_test`. Records contain the exact response schema, and diagnostic output prints the attempted raw reply and rendered case.

For existing packs prepared by the earlier runner revision, use the explicit runner-only provenance override; do not edit or rewrite their hashes:

```bash
python3 code/runner.py infer \
  --run-dir /absolute/container/path/to/existing/run \
  --model /absolute/container/path/to/model.gguf \
  --structured-output --max-cases 1 --allow-runner-update \
  --max-tokens 64 --timeout 180
```

Run inside the notebook container, after safely fetching the updated branch into the clean runner worktree. This reuses the existing scoring/evidence and writes a new attempt; it does not repeat the expensive scorer or overwrite the unconstrained results. Constraints do not make CPU inference fast. Output limits can still truncate; timeout still falls back. Do not expand to all 20 until one native constrained case completes and its label/citations have been inspected.

## Verification performed during development

Public seams approved by Daniel: CLI workflow, exact list preservation, past-only evidence export and safe fallbacks. Automated tests execute the real reference scorer on **small synthetic CSV/answer fixtures** and separately exercise an explicitly simulated LLM adapter. They also check incomplete CSVs, unknown IDs, malformed JSON, truncated completions, missing model, startup failure, timeout, output preservation and code-provenance mismatch. The existing case-file self-test remains unchanged.

The integration tests do **not** execute a real Granite model or use CERT records. They are not substitutes for the first real LinuxONE run. A local successful simulated run must never be reported as actual Granite/CERT success.

```bash
python3 -m pytest -q tests
python3 code/case_file.py
python3 -m compileall -q code/runner.py code/table_io.py code/outofrole_minimal.py
```

Development packages: numpy, pandas, pytest; pyarrow is optional for Parquet-path checks. Actual inference additionally needs the existing `llama-cpp-python` runtime and compatible model weights. No new dependency installation is needed for the known notebook image.

## Next checkpoint

Run the published branch on actual r4.2 data and the installed instruction model, retain the exact revision and output paths, and manually inspect labels/citations. Then clarify the label rubric and evaluate quality separately. Do not claim the whole documented product is finished merely because this batch runner completes.
