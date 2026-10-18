# Local OutOfRole dashboard

The overview, daily queue, and employee detail screens follow the OutOfRole Figma dashboard. The application reads existing files only: it never launches Spark, the detector, the runner, or Granite. No web framework, Node installation, or frontend build is needed.

From the repository root on Windows:

```powershell
py code/dashboard.py
```

On Linux/macOS:

```bash
python3 code/dashboard.py
```

Open **http://127.0.0.1:8000**. Stop with Ctrl+C. The server binds only to loopback. Do not expose it publicly: evidence includes pseudonymized computer and website identifiers.

If no runner exports exist, the dashboard opens the **CERT r4.2 activity preview** from the existing `data/r4.2/r4.2/logon.csv`. It reads at most the first 50,000 CSV records and offers dates present in that bounded slice. Totals refer only to that slice. Employees appear alphabetically, with raw logon/logoff evidence; scores, detector ranks, and Granite labels are unavailable. CERT is a synthetic benchmark; this view is distinct from the fictional Northstar UI sample. No Spark, feature processing, scoring or model inference runs. `--raw /path/to/r4.2` points to the CSV folder on another machine when running the dashboard there. This is not remote filesystem access from your laptop.

After updating dashboard code, stop the old server with Ctrl+C, start it again, and refresh the browser. Static text is served as UTF-8 with caching disabled to prevent stale garbled labels.

## Through Jupyter

When Jupyter Server Proxy is installed and enabled, run the dashboard in the same container as Jupyter and open `<jupyter-base-url>/proxy/8000/` (including the trailing slash). Use the container-visible paths for `--run-dir` and `--cache`. The dashboard's API URL is relative so requests stay under the proxy prefix, including nested JupyterHub base paths. Direct access at `http://127.0.0.1:8000/` also works.

Keep Jupyter's existing authentication and HTTPS protections. Installing the extension may require a coordinated Jupyter server restart; do not restart a shared container while teammates have jobs running. This JavaScript-only API-path fix needs a browser refresh, not a container restart or a rerun of scoring, Spark, or Granite.

## Use existing data

By default the server discovers `data/runs/*/packs.json` and selects the last run in directory-name order. The daily-window selector lets you switch runs, including separate runs for the same day. For an existing run elsewhere:

```powershell
py code/dashboard.py --run-dir "C:\path\to\existing-run" --cache "C:\path\to\data\cache"
```

```bash
python3 code/dashboard.py --run-dir /path/to/existing-run --cache /path/to/data/cache
```

Alternatively, `--runs /path/to/runs` changes discovery. `--port 8080` changes the local port. `--attempt /path/to/existing-run/attempts/TIMESTAMP` pins an inference attempt and requires `--run-dir`. Otherwise the last attempt with `results.jsonl` in directory-name order is used. Refresh reloads files, including incremental runner results. A partial final JSON line is ignored with a visible notice.

The queue uses `packs.json` ranks, raw running scores, pseudonyms, and evidence without recalculating or reranking. It reads the selected attempt's `results.jsonl` and revalidates accepted, cleanly finished replies with `case_file.accept`. Unknown citations, invalid labels, truncated replies, failed inference, and skipped cases cannot become accepted assessments. The displayed narrative comes from the deterministic renderer, not model-written prose. “Accepted” means contract validity, not semantic accuracy. Missing results appear as “Not inferred.”

Processed totals come from the selected release's existing `daily` table using `table_io.read_table`, which supports complete Spark CSV directories or Parquet. Install `pandas` only if you need these totals; Parquet also needs `pyarrow` or another pandas-compatible engine. The rest of the dashboard uses Python's standard library. `OUTOFROLE_TABLE_FORMAT=csv` or `parquet` selects a format; default `auto` follows the project loader. `OUTOFROLE_CACHE` or `--cache` supplies the cache root containing `r4.2` / `r4.2_csv` folders. Incomplete exports produce a visible unavailable-metrics message, never an automatic rebuild.

“Employees active” is the distinct processed users on the chosen day. “Processed events” sums `n_logon`, `n_usb`, `n_file`, and `n_http` on that day; these are not the scorer's exact evaluation totals. Missing values display a dash. The runner does not export a priority policy, names/departments, precise event times, or multi-day alert history, so none are fabricated. Priorities remain Unassigned, the volume panel shows only the selected run, and timelines retain source day precision and indicate that these are ranked evidence facts.

## Sample workspace and interactions

Choose **Northstar / demo-01 (sample)** in the dataset selector for the clearly labeled synthetic design preview. It is separate from runner data and never appears automatically as a substitute for missing results. Sample Granite labels are human-authored, with explicit “no model was run” wording. Only Mara has an authored sample timeline; other sample employees show an honest empty evidence state.

Queue search, priority and review filters, employee navigation, fact links, and JSON queue export work locally. “Begin review” and “Mark reviewed” store review metadata in browser session storage, scoped to source/run/day/person; they do not alter runner outputs or persist as a shared review system. Queue exports include the source/sample designation.

Dataset selection is explicit: selecting **Runner outputs** keeps that source selected and shows an empty state when no prepared exports exist. The r4.2 activity preview is an initial-load fallback only; it does not override an explicit source choice or Refresh. Late responses from an earlier selection are ignored.

Refresh rereads saved files; it does not execute the runner or generate another replay day. The button shows progress, a completion timestamp, and whether data changed. It prevents duplicate pending requests and preserves the selected employee and inference attempt for the same run. On a read failure, the previous results stay visible with an error message. Sample data is static and Refresh explains that rather than making a request.

The daily-window selector lists available saved runs, not pages or all dates in the raw dataset. One saved run means one choice; four inference attempts within that run are selected separately in the inference-attempt selector. With `--run-dir`, the dashboard is pinned to that one run. To browse several prepared days, launch using `--runs /path/to/data/runs` instead of `--run-dir`; Refresh can then discover additional saved runs in that folder without starting analysis.

On Overview, **Inspect employee** opens that employee's detail screen. In the daily queue, **Select** updates the highlighted employee and selection summary; the chosen row reads **Selected**. Use **Inspect employee** in the summary to open details. When saved runner results are loaded, the dashboard states that explicitly and keeps requirements for generating new results in a collapsed optional setup panel. A missing model configuration does not prevent reading saved Granite responses.

## Detector and Granite integration

The dashboard now shows original running scores in the queue and employee detail, the highest running score in the overview, a comparison of the first five ranked scores, and separate Accepted/Fallback/Not inferred counts. Score bars share the current queue maximum, not a 100-point risk scale. Exact score values remain in the JSON export and score tooltips. No priorities or risk percentages are invented.

Use the inference-attempt selector to inspect saved attempts without overwriting older results. Model name, model SHA-256, API mode, and structured-output configuration appear when recorded by the runner. A preparation manifest, when present, must match the packs digest and recorded code provenance. A mismatched result rank or score cannot produce an accepted assessment. No raw model narrative or answer-key identities are sent to the browser.

The readiness panel reports missing processed tables, required readers, runtime and model configuration. To check without running any computation:

```powershell
py code/dashboard_pipeline.py check
```

On the Linux/RHEL machine with complete tables, select an explicit replay day and prepare the original detector output:

```bash
python3 code/dashboard_pipeline.py prepare --release 4.2 --day 2010-08-02 --cache /path/to/data/cache
```

This invokes the unchanged reference runner/scorer and creates a new saved run; it does not build tables or start Spark. The example date is illustrative, not selected from the answer key. A missing/incomplete table stops before scoring starts. The original scorer still requires the answer key for its evaluation report, per the existing contract; Granite never receives it.

Then reuse the printed run path for a one-case Granite diagnostic:

```bash
python3 code/dashboard_pipeline.py infer --run-dir /path/to/existing-run --model /path/to/granite.gguf --max-cases 1
```

The helper enables the existing per-pack JSON grammar and validator. All names and ranks remain; other cases are Not inferred. `--model-mode completion` is available for the supplied 350M base model; chat remains the default for instruction models. The existing runner's provenance checks remain in force. The helper does not bypass source-hash mismatches, install a runtime, download models, or synthesize assessments.

The current Granite worker requires POSIX pipe selectors and is run on Linux/RHEL, not this Windows laptop. Configure `--model /existing/model.gguf` when launching the dashboard, or set `OUTOFROLE_GRANITE_MODEL`, to include that model in readiness checks. Opening or refreshing the dashboard never launches inference. See [runner operational guidance](RUNNER.md) for native runtime configuration and full-batch inference after a successful diagnostic. Recommender/access-advice results are not in the runner export contract, so the dashboard does not fabricate them.

## Verification

```powershell
py -m unittest discover -s tests -p test_dashboard.py
py -m compileall -q code/dashboard.py
```

The tests use temporary synthetic fixtures to verify preserved ranks, validated citations, fail-closed inference handling, partial records, and missing-data behavior. They do not run scoring, Spark, or a real Granite model.
