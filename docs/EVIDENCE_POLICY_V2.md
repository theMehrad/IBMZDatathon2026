# Evidence policy v2: synthetic evaluation protocol

The opt-in `--label-guide v2` adds compact demonstrations to the inference prompt. The opt-in `--evidence-policy v2` checks the model's returned label/citations against a minimum-evidence rule in code. These are separate switches: a guide can be compared with or without the guard. Defaults stay `--label-guide v1 --evidence-policy none` in the quality CLI; the existing v1 fixture suite is unchanged. In the normal runner, keep its own documented defaults unless intentionally testing v2.

## Evaluation and boundaries

`evidence/quality/evidence-policy-v2.json` has eight hand-authored, prompt-disjoint synthetic cases with different person and fact identifiers than the v2 prompt examples. They were **designed after observing the v1 fixtures** and frozen before native v2 inference. This is not an independent scientific holdout or CERT classification accuracy. Expectations, fixture names and descriptions are stored in `suite.json` for audit but only each `pack` is sent to the worker. Do not tune expectations to model answers. The first three cases are a bounded smoke check, not a passing full suite.

The first three cases are balanced across USB-only (weak evidence), the known leak destination (possible data leak) and an explicit removable-media copy (possible data theft). Thus an always-weak classifier cannot pass the initial three-case check. The remaining cases cover an adversarial `wikileaks.org.evil.invalid` domain with embedded instruction text, benign documentation browsing, new after-hours activity, a mixed leak/copy case, and explicit colleague-computer ownership. A site containing the leak site's name is not the exact known destination. Visiting the exact known destination is concern evidence, **not proof of upload**. USB attachment is not a copy observation. Newness/rarity makes a pack *strong* under the existing ranking rule but does not by itself establish an accusation; all eight packs are strong and weak-label examples are not grammar-forced. Priority leak > theft > snooping > after-hours is a prompt/evaluation convention, **not** a minimum-evidence guard requirement. In the mixed case the copy may be a second, positive citation, but familiar-PC context is forbidden. A weak label may cite the limited observation under review.

**Capability-only synthetic inputs:** explicit copy and colleague ownership are richer fact kinds absent from the current production case producer, which emits computer logon, website visit, USB use and after-hours logon. Passing those examples does not establish coverage on real exported evidence. The synthetic staff shares and events are not measured CERT claims.

The runner's source provenance now includes `evidence_policy.py`. A previously exported pack without that hash requires an explicit `--allow-runner-update` on `runner.py infer`; without the flag, inference fails before loading a model. The override permits only runner/guide/policy source changes, not changes to the scorer, table loader or validator; preparation and current hashes remain in the attempt config.

`contract_accepted` counts raw responses valid under the JSON/ID contract, `system_accepted` counts responses retained after the optional policy guard, and `policy_rejected` counts contract-valid responses the guard rejected into the deterministic fallback. `label_matches`, `citation_matches` and `quality_passed` grade **raw contract-valid model output**, not the fallback and not policy acceptance. Thus a guard rejecting an incorrect accusation improves the system's safety disposition but never retroactively raises model accuracy. A policy-rejected raw reply could theoretically match an inconsistent fixture expectation; report both measurements rather than hiding either. `quality_passed` requires both raw label and citation match, including no repeated IDs, required support, no forbidden neutral context and at most two distinct IDs. Contract failures, truncation and worker errors cannot pass. `config.json` records the suite version, suite guide version, active prompt guide version, policy choice and hashes; `suite.json` snapshots expectations. Partial results retain `partial_quality_check` status. The guard rejects unsupported claims; it does not replace analyst review or prove malicious intent.

## LinuxONE invocation (existing container and model paths)

Use the existing runner checkout and notebook container; do not install packages or download models for this check. Keep run outputs private and untracked under `data/quality_runs/`. Preview the frozen expectations without loading a model:

```bash
cd /home/linux1/shared/ibmzdatathon2026-runner
docker exec -w /home/ibm-user/shared/ibmzdatathon2026-runner \
  notebook python3 code/quality_check.py --label-guide v2 --list --limit 8
```

Start with three cases against the existing 350M model, then use `--limit 8` for the full suite after reviewing failures. A completion token cap can truncate otherwise structured output; do not silently retry unconstrained inference.

```bash
docker exec -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 \
  -w /home/ibm-user/shared/ibmzdatathon2026-runner \
  notebook python3 -u code/quality_check.py \
    --model /home/ibm-user/granite-4.0-h-350m-base-be.f16.gguf \
    --model-mode completion --label-guide v2 --evidence-policy v2 \
    --limit 3 --max-tokens 64 --timeout 60 --startup-timeout 60
```

For the full suite, repeat the same command with `--limit 8`. Compare *the same expectations* with the guard disabled (new output directory each run):

```bash
docker exec -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 \
  -w /home/ibm-user/shared/ibmzdatathon2026-runner \
  notebook python3 -u code/quality_check.py \
    --model /home/ibm-user/granite-4.0-h-350m-base-be.f16.gguf \
    --model-mode completion --label-guide v2 --evidence-policy none \
    --limit 8 --max-tokens 64 --timeout 60 --startup-timeout 60
```

For a 2B comparison on that same suite, verify the existing model path in the container and run its chat mode (embedded chat template required). This is not a claim that the 2B model or runtime is accessible here:

```bash
docker exec -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 \
  -w /home/ibm-user/shared/ibmzdatathon2026-runner \
  notebook python3 -u code/quality_check.py \
    --model /home/ibm-user/shared/models/granite-3.3-2b-instruct-be.Q4_K_M.gguf \
    --model-mode chat --label-guide v2 --evidence-policy v2 \
    --limit 8 --max-tokens 64 --timeout 180 --startup-timeout 180
```

Explicit `--fixtures evidence/quality/evidence-policy-v2.json` permits comparison with `--label-guide v1` or `none` without changing expected answers. Default suite selection is v2 only with guide v2; other guide choices default to v1. The quality CLI exit status is 0 only if every selected raw model result passes both quality gates and every response is system-accepted; 2 if a quality/system check fails; and 1 for fatal configuration/I/O errors. CLI argument errors also use exit 2 before a summary exists. The summary identifies model path, mode, guide and policy to avoid ambiguous pasted results. Runtime/model verification requires actual LinuxONE execution; local test adapters are explicitly simulated and do not establish native Granite quality or latency.
