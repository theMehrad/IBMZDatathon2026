"""Native CLI transport with explicitly simulated inference, never Granite output."""
import hashlib
import json
from test_runner_cli import command, synthetic_repo


def test_v2_guard_preserves_old_prepared_packs_and_every_review_entry(synthetic_repo):
    root = synthetic_repo
    run = root / 'data/runs/policy-v2'
    prepared = command(root, 'prepare', '--release', '4.2', '--day', '2010-06-02', '--run-dir', str(run))
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    bundle = json.loads((run / 'packs.json').read_text())
    assert bundle['cases'][0]['pack']['strength'] == 'strong'
    # Model an earlier preparation revision without the new inference adapter.
    bundle['code_sha256'].pop('evidence_policy.py')
    bundle['code_sha256']['runner.py'] = '0' * 64
    (run / 'packs.json').write_text(json.dumps(bundle))
    manifest = json.loads((run / 'preparation.json').read_text())
    manifest['code_sha256'] = bundle['code_sha256']
    manifest['packs_sha256'] = hashlib.sha256((run / 'packs.json').read_bytes()).hexdigest()
    (run / 'preparation.json').write_text(json.dumps(manifest))
    before = (run / 'packs.json').read_bytes()
    adapter = root / 'policy_test_adapter'
    adapter.mkdir()
    (adapter / 'llama_cpp.py').write_text('''
import json
class LlamaGrammar:
    @classmethod
    def from_json_schema(cls, text, verbose=False):
        schema = json.loads(text)
        assert len(schema['properties']['label']['enum']) == 5
        return schema
class Llama:
    metadata = {'general.name': 'SIMULATED WRONG CLASSIFICATION'}
    def __init__(self, **kwargs): pass
    def create_completion(self, **kwargs):
        assert 'outofrole-label-guide-v2' in kwargs['prompt']
        assert '"file_copy_observed":false' in kwargs['prompt']
        assert 'grammar' in kwargs
        return {'choices': [{'text': '{"label":"possible data theft","facts":["E1"]}', 'finish_reason':'stop'}]}
    def close(self): pass
''')
    model = root / 'SIMULATED_MODEL_NOT_GGUF'
    model.write_text('Not real weights')
    for policy in ('none', 'v2'):
        output = command(root, 'infer', '--run-dir', str(run), '--model', str(model),
                         '--label-guide', 'v2', '--evidence-policy', policy,
                         '--model-mode', 'completion', '--structured-output', '--max-cases', '1',
                         '--allow-runner-update', env={'PYTHONPATH': str(adapter)})
        assert output.returncode == (0 if policy == 'none' else 2), output.stdout + output.stderr
    attempts = sorted((run / 'attempts').iterdir())
    assert len(attempts) == 2
    for attempt, policy in zip(attempts, ('none', 'v2')):
        rows = [json.loads(line) for line in (attempt / 'results.jsonl').read_text().splitlines()]
        assert [r['person'] for r in rows] == [c['pack']['person'] for c in bundle['cases']]
        assert [r['rank'] for r in rows] == [c['rank'] for c in bundle['cases']]
        assert rows[0]['contract_accepted']
        assert rows[0]['accepted'] is (policy == 'none')
        assert sum(r['skipped'] for r in rows) == 19
        summary = json.loads((attempt / 'summary.json').read_text())
        assert summary['contract_accepted'] == 1
        assert summary['policy_rejected'] == (0 if policy == 'none' else 1)
        assert summary['total'] == 20
        config = json.loads((attempt / 'config.json').read_text())
        assert config['evidence_policy'] == policy
        assert config['allowed_runner_update']
        if policy == 'v2':
            assert rows[0]['rendered'].startswith(rows[0]['person'] + ': needs review')
            assert 'possible data theft' not in rows[0]['rendered']
    assert (run / 'packs.json').read_bytes() == before
