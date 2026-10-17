"""Structured-mode transport tests; adapter is simulated, never a real model."""
import hashlib
import json
import pytest
from test_runner_cli import command, synthetic_repo


@pytest.mark.parametrize('grammar_available', [True, False])
def test_constrained_single_case_reuses_old_packs_and_retains_skipped_names(synthetic_repo, grammar_available):
    root = synthetic_repo
    run = root / 'data/runs/constrained'
    prepared = command(root, 'prepare', '--release', '4.2', '--day', '2010-06-02', '--run-dir', str(run))
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    # Simulate an old runner revision with unchanged scorer/validator/loader.
    bundle = json.loads((run / 'packs.json').read_text())
    manifest = json.loads((run / 'preparation.json').read_text())
    bundle['code_sha256']['runner.py'] = '0' * 64
    manifest['code_sha256'] = bundle['code_sha256']
    (run / 'packs.json').write_text(json.dumps(bundle))
    manifest['packs_sha256'] = hashlib.sha256((run / 'packs.json').read_bytes()).hexdigest()
    (run / 'preparation.json').write_text(json.dumps(manifest))
    model = root / 'SIMULATED_MODEL_NOT_GGUF'
    model.write_text('test-only placeholder')
    rejected = command(root, 'infer', '--run-dir', str(run), '--model', str(model))
    assert rejected.returncode == 1 and 'Code changed' in rejected.stderr
    adapter = root / 'grammar_adapter'
    adapter.mkdir()
    (adapter / 'llama_cpp.py').write_text('''
import json
class LlamaGrammar:
    @classmethod
    def from_json_schema(cls, text, verbose=False):
        schema = json.loads(text)
        assert schema['additionalProperties'] is False
        assert schema['properties']['facts']['items']['enum'][0] == 'E1'
        return schema
class Llama:
    metadata = {'tokenizer.chat_template': 'test-only', 'general.name': 'SIMULATED GRAMMAR ADAPTER'}
    def __init__(self, **kwargs): pass
    def create_chat_completion(self, **kwargs):
        assert 'grammar' in kwargs, 'Constrained mode must actually pass its grammar'
        return {'choices': [{'message': {'content': '{"label":"weak evidence","facts":["E1"]}'}, 'finish_reason': 'stop'}]}
    def close(self): pass
''')
    if not grammar_available:
        path = adapter / 'llama_cpp.py'
        path.write_text(path.read_text() + '\ndel LlamaGrammar\n')
    result = command(root, 'infer', '--run-dir', str(run), '--model', str(model),
                     '--structured-output', '--max-cases', '1', '--allow-runner-update',
                     env={'PYTHONPATH': str(adapter)})
    assert result.returncode == (0 if grammar_available else 2), result.stdout + result.stderr
    attempt, = (run / 'attempts').iterdir()
    summary = json.loads((attempt / 'summary.json').read_text())
    assert (summary['total'], summary['skipped']) == (20, 19)
    expected = (1, 0) if grammar_available else (0, 1)
    assert (summary['accepted'], summary['fallback']) == expected
    if grammar_available:
        assert summary['status'] == 'partial_test'
    records = [json.loads(line) for line in (attempt / 'results.jsonl').read_text().splitlines()]
    assert [r['person'] for r in records] == [c['pack']['person'] for c in bundle['cases']]
    assert all(r['skipped'] for r in records[1:])
    assert records[0]['response_schema']['properties']['facts']['items']['enum'][0] == 'E1'
    config = json.loads((attempt / 'config.json').read_text())
    assert config['allowed_runner_update'] and config['structured_output']
    assert config['prepared_code_sha256']['runner.py'] == '0' * 64
    # The override must NOT permit a changed validator or scorer.
    source = root / 'code/case_file.py'
    source.write_text(source.read_text() + '\n# changed\n')
    invalid = command(root, 'infer', '--run-dir', str(run), '--model', str(model), '--allow-runner-update')
    assert invalid.returncode == 1 and 'Code changed' in invalid.stderr
