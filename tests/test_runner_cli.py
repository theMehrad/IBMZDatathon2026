"""CLI integration tests use explicitly synthetic data and a simulated LLM adapter.
They do not establish CERT metrics, Granite compatibility or label accuracy.
"""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd
import pytest

CODE = Path(__file__).resolve().parents[1] / 'code'


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture
def synthetic_repo(tmp_path):
    root = tmp_path / 'repo'
    shutil.copytree(CODE, root / 'code', ignore=shutil.ignore_patterns('__pycache__'))
    daily, pcs, dom = [], [], []
    for d in pd.date_range('2010-01-01', '2010-06-06'):
        for i in range(24):
            user = f'RAW-{i:03d}'
            after = d >= pd.Timestamp('2010-06-01')
            daily.append(dict(user=user, day=str(d.date()), n_logon=1, n_logon_ah=0, n_pcs=1,
                              n_usb=10 if after and i < 2 else 0, n_usb_ah=0,
                              n_file=20 if after and i < 2 else 1, n_file_ah=0,
                              n_http=1, n_http_ah=0))
            pcs.append(dict(user=user, day=str(d.date()), pc=f'PC-{i}'))
            dom.append(dict(user=user, day=str(d.date()), domain=f'site{i % 2}.example', n=1))
            if after:
                dom.append(dict(user=user, day=str(d.date()), domain=f'site{1-i % 2}.example', n=1))
    for name, rows in [('daily', daily), ('pc_pairs', pcs), ('dom_pairs', dom)]:
        folder = root / 'data/cache/r4.2_csv' / name
        write_csv(folder / 'part-000.csv', rows)
        (folder / '_SUCCESS').touch()
    answer = root / 'data/answers/answers'
    write_csv(answer / 'insiders.csv', [
        dict(dataset='4.2', scenario=scenario, user=f'RAW-{i:03d}', start='2010-06-01', end='2010-06-05')
        for i, scenario in [(0, 1), (1, 3)]
    ])
    for i, scenario in [(0, 1), (1, 3)]:
        path = answer / f'r4.2-{scenario}' / f'RAW-{i:03d}.csv'
        path.parent.mkdir(parents=True)
        with path.open('w') as f:
            csv.writer(f).writerow(['http', 'event', '06/01/2010 12:00:00', f'RAW-{i:03d}', f'PC-{i}', 'http://new.example/'])
    return root


def command(root, *args, env=None):
    return subprocess.run([sys.executable, str(root / 'code/runner.py'), *args],
                          capture_output=True, text=True, timeout=60,
                          env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', **(env or {})))


def test_prepare_executes_reference_scorer_and_missing_model_preserves_every_case(synthetic_repo):
    root = synthetic_repo
    run = root / 'data/runs/test'
    result = command(root, 'prepare', '--release', '4.2', '--day', '2010-06-02', '--run-dir', str(run))
    assert result.returncode == 0, result.stdout + result.stderr
    packs = json.loads((run / 'packs.json').read_text())
    assert len(packs['cases']) == 20
    assert 'RAW-' not in (run / 'packs.json').read_text()
    assert 'early warning' in (run / 'scoring.log').read_text()
    result = command(root, 'infer', '--run-dir', str(run), '--model', str(root / 'missing.gguf'))
    assert result.returncode == 2, result.stdout + result.stderr
    attempt, = (run / 'attempts').iterdir()
    records = [json.loads(line) for line in (attempt / 'results.jsonl').read_text().splitlines()]
    assert [r['person'] for r in records] == [c['pack']['person'] for c in packs['cases']]
    assert all(not r['accepted'] for r in records)
    assert all('Model file not found' in r['problems'][0] for r in records)
    assert json.loads((attempt / 'summary.json').read_text())['fallback'] == 20
    assert (attempt / 'case_files.txt').read_text().count('U-') == 20
    # Existing artifacts are never overwritten by another prepare.
    before = (run / 'packs.json').read_bytes()
    again = command(root, 'prepare', '--release', '4.2', '--day', '2010-06-02', '--run-dir', str(run))
    assert again.returncode == 1
    assert (run / 'packs.json').read_bytes() == before
    edited = json.loads((run / 'packs.json').read_text())
    edited['cases'][0]['pack']['facts'][0]['item'] = 'edited.example'
    (run / 'packs.json').write_text(json.dumps(edited))
    modified = command(root, 'infer', '--run-dir', str(run), '--model', str(root / 'missing.gguf'))
    assert modified.returncode == 1
    assert 'Pack digest mismatch' in modified.stderr


def test_date_before_cutoff_fails_before_creating_run_directory(synthetic_repo):
    root = synthetic_repo
    run = root / 'data/runs/invalid-date'
    result = command(root, 'prepare', '--release', '4.2', '--day', '2010-05-31', '--run-dir', str(run))
    assert result.returncode == 1
    assert 'before the replay cutoff' in result.stderr
    assert not run.exists()


def test_whole_run_uses_simulated_adapter_and_saves_all_outputs(synthetic_repo):
    root = synthetic_repo
    adapter = root / 'test_adapter'
    adapter.mkdir()
    # Explicit deterministic test double, NOT a real Granite inference result.
    (adapter / 'llama_cpp.py').write_text('''
class Llama:
    metadata = {'tokenizer.chat_template': 'test-only', 'general.name': 'SIMULATED ADAPTER'}
    def __init__(self, **kwargs): pass
    def create_chat_completion(self, **kwargs):
        return {'choices': [{'message': {'content': '{"label":"weak evidence","facts":["E1"]}'}, 'finish_reason': 'stop'}]}
    def close(self): pass
''')
    model = root / 'SIMULATED_MODEL_NOT_GGUF'
    model.write_text('test-only placeholder, never real model weights')
    run = root / 'data/runs/full'
    result = command(root, 'run', '--release', '4.2', '--day', '2010-06-02',
                     '--model', str(model), '--run-dir', str(run), env={'PYTHONPATH': str(adapter)})
    assert result.returncode == 0, result.stdout + result.stderr
    attempt, = (run / 'attempts').iterdir()
    summary = json.loads((attempt / 'summary.json').read_text())
    assert (summary['total'], summary['accepted'], summary['fallback']) == (20, 20, 0)
    config = json.loads((attempt / 'config.json').read_text())
    assert config['runtime']['model_name'] == 'SIMULATED ADAPTER'
    assert config['model_sha256']
    assert (attempt / 'case_files.txt').read_text().count('U-') == 20
    # Pack provenance mismatch is rejected before another inference attempt.
    (root / 'code/case_file.py').write_text((root / 'code/case_file.py').read_text() + '\n# changed\n')
    changed = command(root, 'infer', '--run-dir', str(run), '--model', str(model))
    assert changed.returncode == 1
    assert 'Code changed' in changed.stderr


@pytest.mark.parametrize('failure', ['startup', 'timeout', 'malformed', 'truncated'])
def test_worker_failures_keep_all_names_with_explicit_fallbacks(synthetic_repo, failure):
    root = synthetic_repo
    adapter = root / 'failure_adapter'
    adapter.mkdir()
    (adapter / 'llama_cpp.py').write_text('''
import os, time
class Llama:
    metadata = {'tokenizer.chat_template': 'test-only'}
    def __init__(self, **kwargs):
        if os.environ['TEST_LLM_FAILURE'] == 'startup': raise RuntimeError('SIMULATED STARTUP FAILURE')
    def create_chat_completion(self, **kwargs):
        mode = os.environ['TEST_LLM_FAILURE']
        if mode == 'timeout': time.sleep(10)
        reply = 'not JSON' if mode == 'malformed' else '{"label":"weak evidence","facts":["E1"]}'
        return {'choices': [{'message': {'content': reply}, 'finish_reason': 'length' if mode == 'truncated' else 'stop'}]}
    def close(self): pass
''')
    model = root / 'SIMULATED_MODEL_NOT_GGUF'
    model.write_text('test-only placeholder')
    run = root / 'data/runs/failure'
    result = command(root, 'run', '--release', '4.2', '--day', '2010-06-02',
                     '--model', str(model), '--run-dir', str(run), '--timeout', '1',
                     env={'PYTHONPATH': str(adapter), 'TEST_LLM_FAILURE': failure})
    assert result.returncode == 2, result.stdout + result.stderr
    packs = json.loads((run / 'packs.json').read_text())
    attempt, = (run / 'attempts').iterdir()
    records = [json.loads(line) for line in (attempt / 'results.jsonl').read_text().splitlines()]
    assert [r['person'] for r in records] == [c['pack']['person'] for c in packs['cases']]
    assert len(records) == 20 and all(not r['accepted'] for r in records)
    assert all(r['problems'] for r in records)
    assert json.loads((attempt / 'summary.json').read_text())['fallback'] == 20
