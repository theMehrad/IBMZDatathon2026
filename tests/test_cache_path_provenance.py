"""Inference-only reuse of the reviewed cache-path change; no model or scoring."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
import runner

OLD_SCORER = 'fb122cdf35128976f9e2580824a1e4ebdd807d1812b024898a39c3cac633767c'
NEW_SCORER = '5bf0b02ff118d1837bfc9d9b97e5468ba5787fe7c287c73904a2e9821c703a80'


def fixture(tmp_path, monkeypatch, *, opt_in=True, runner_update=False,
            prepared_change=None, current_change=None):
    current = runner.code_hashes()
    assert current['outofrole_minimal.py'] == NEW_SCORER
    prepared = current.copy()
    prepared['outofrole_minimal.py'] = OLD_SCORER
    if runner_update:
        prepared['runner.py'] = 'older-runner'
        prepared.pop('label_guide.py')
        prepared.pop('evidence_policy.py')
    if prepared_change:
        prepared.update(prepared_change)
    if current_change:
        current.update(current_change)
    monkeypatch.setattr(runner, 'code_hashes', lambda: current)
    bundle = dict(code_sha256=prepared, day='2010-08-02', release='4.2', cases=[])
    packs = tmp_path / 'packs.json'
    packs.write_text(json.dumps(bundle))
    manifest = tmp_path / 'preparation.json'
    manifest.write_text(json.dumps(dict(packs_sha256=runner.file_hash(packs), code_sha256=prepared)))
    args = argparse.Namespace(
        run_dir=tmp_path, stage='infer', allow_runner_update=runner_update,
        allow_cache_path_update=opt_in, model=tmp_path / 'missing.gguf',
        context=2048, threads=2, max_tokens=64, startup_timeout=60, timeout=180,
        structured_output=True, max_cases=1, model_mode='chat',
        label_guide='v2', evidence_policy='v2')
    return args, packs.read_bytes(), manifest.read_bytes()


@pytest.mark.parametrize('runner_update', [False, True])
def test_exact_pair_is_recorded_without_rewriting_evidence(tmp_path, monkeypatch, runner_update):
    args, packs, manifest = fixture(tmp_path, monkeypatch, runner_update=runner_update)
    # Empty synthetic queue exercises real infer/config persistence without loading a model.
    assert runner.infer(args) == 0
    config = json.loads(next((tmp_path / 'attempts').glob('*/config.json')).read_text())
    assert config['cache_path_compatibility'] == {
        'file': 'outofrole_minimal.py', 'prepared_sha256': OLD_SCORER,
        'current_sha256': NEW_SCORER,
        'reason': 'Reviewed cache-root override only; inference reuses saved packs without scoring'}
    assert config['allowed_runner_update'] is runner_update
    assert (tmp_path / 'packs.json').read_bytes() == packs
    assert (tmp_path / 'preparation.json').read_bytes() == manifest


@pytest.mark.parametrize('kwargs', [
    {'opt_in': False},
    {'prepared_change': {'outofrole_minimal.py': 'unknown-old'}},
    {'current_change': {'outofrole_minimal.py': 'unknown-new'}},
    {'prepared_change': {'case_file.py': 'changed-validator'}},
    {'prepared_change': {'table_io.py': 'changed-loader'}},
    {'prepared_change': {'runner.py': 'changed-runner'}},
    {'prepared_change': {'unexpected.py': 'extra-file'}},
    {'runner_update': True, 'prepared_change': {'case_file.py': 'changed-validator'}},
    {'runner_update': True, 'prepared_change': {'table_io.py': 'changed-loader'}},
    {'runner_update': True, 'current_change': {'outofrole_minimal.py': 'unknown-new'}},
    {'runner_update': True, 'prepared_change': {'unexpected.py': 'extra-file'}},
])
def test_unapproved_changes_fail_before_creating_attempt(tmp_path, monkeypatch, kwargs):
    args, packs, manifest = fixture(tmp_path, monkeypatch, **kwargs)
    with pytest.raises(ValueError, match='Code changed since pack export'):
        runner.infer(args)
    assert not (tmp_path / 'attempts').exists()
    assert (tmp_path / 'packs.json').read_bytes() == packs
    assert (tmp_path / 'preparation.json').read_bytes() == manifest


def test_exception_does_not_apply_to_run_stage(tmp_path, monkeypatch):
    args, _, _ = fixture(tmp_path, monkeypatch, runner_update=True)
    args.stage = 'run'
    with pytest.raises(ValueError, match='Code changed since pack export'):
        runner.infer(args)
    assert not (tmp_path / 'attempts').exists()


def test_pack_digest_still_enforced(tmp_path, monkeypatch):
    args, _, _ = fixture(tmp_path, monkeypatch)
    with (tmp_path / 'packs.json').open('a') as stream:
        stream.write(' ')
    with pytest.raises(ValueError, match='Pack digest mismatch'):
        runner.infer(args)


def test_cli_flag_is_only_available_for_infer(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['runner.py', 'prepare', '--release', '4.2',
        '--day', '2010-08-02', '--allow-cache-path-update'])
    with pytest.raises(SystemExit) as exc:
        runner.cli()
    assert exc.value.code == 2
