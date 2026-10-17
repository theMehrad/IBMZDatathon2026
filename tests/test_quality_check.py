import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))


def test_versioned_guide_keeps_baseline_and_does_not_include_expected_answers():
    from case_file import prompt
    from label_guide import prompt_for, GUIDE_VERSION
    pack = dict(person='TEST', strength='strong', facts=[])
    assert prompt_for(pack, 'none') == prompt(pack)
    guided = prompt_for(pack, 'v1')
    assert GUIDE_VERSION in guided
    assert 'USB use alone' in guided
    assert '1 or 2' in guided
    assert guided.endswith(prompt(pack))


def test_quality_grading_separates_valid_json_from_label_and_citation_quality():
    from quality_check import grade_reply
    fixture = dict(id='test', expected_label='possible data leak', required_fact_ids=['E1'],
                   forbidden_fact_ids=['E2'], max_cited_facts=2,
                   pack=dict(person='TEST', strength='strong', facts=[
                       dict(id='E1', what='visited website', item='wikileaks.org', date='2010-08-02', new_to_person=True, staff_share=0.),
                       dict(id='E2', what='logged on to computer', item='PC-A', date='2010-08-02', new_to_person=False, staff_share=0.1),
                   ]))
    good = grade_reply(fixture, '{"label":"possible data leak","facts":["E1"]}', 'stop')
    assert good['accepted'] and good['quality_pass']
    wrong = grade_reply(fixture, '{"label":"possible data theft","facts":["E1"]}', 'stop')
    assert wrong['accepted'] and not wrong['quality_pass']
    assert not wrong['label_match']
    all_facts = grade_reply(fixture, '{"label":"possible data leak","facts":["E1","E2"]}', 'stop')
    assert all_facts['accepted'] and not all_facts['quality_pass']
    assert not all_facts['citation_match']
    malformed = grade_reply(fixture, 'not JSON', 'stop')
    assert not malformed['accepted'] and not malformed['quality_pass']
    truncated = grade_reply(fixture, '{"label":"possible data leak","facts":["E1"]}', 'length')
    assert not truncated['accepted'] and not truncated['quality_pass']


def test_frozen_suite_uses_neutral_ids_and_nonforced_weak_expectations():
    from quality_check import load_suite
    root = Path(__file__).resolve().parents[1]
    suite = load_suite(root / 'evidence/quality/label-guide-v1.json')
    assert len(suite['cases']) == 6
    assert all(c['pack']['strength'] == 'strong' for c in suite['cases'])
    assert {c['expected_label'] for c in suite['cases']} == {
        'possible data leak', 'possible data theft', 'unusual after-hours activity', 'weak evidence'}
    assert [c['pack']['person'] for c in suite['cases']] == [f'SYNTH-{i:03d}' for i in range(1, 7)]


def test_quality_cli_measures_quality_not_just_simulated_contract_acceptance(tmp_path):
    import os
    import shutil
    import subprocess
    root = tmp_path / 'repo'
    original = Path(__file__).resolve().parents[1]
    shutil.copytree(original / 'code', root / 'code', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(original / 'evidence/quality', root / 'evidence/quality')
    adapter = tmp_path / 'adapter'
    adapter.mkdir()
    # Intentionally wrong for two cases: never presented as actual model output.
    (adapter / 'llama_cpp.py').write_text('''
import json
class LlamaGrammar:
    @classmethod
    def from_json_schema(cls, text, verbose=False):
        schema = json.loads(text)
        assert len(schema['properties']['label']['enum']) == 5
        return schema
class Llama:
    metadata = {'general.name': 'SIMULATED QUALITY ADAPTER'}
    def __init__(self, **kwargs): pass
    def create_completion(self, **kwargs):
        text = kwargs['prompt']
        assert 'outofrole-label-guide-v1' in text
        assert 'expected_label' not in text and 'leak-with-neutral-distractor' not in text
        assert 'grammar' in kwargs
        return {'choices': [{'text': '{"label":"possible data leak","facts":["E1"]}', 'finish_reason': 'stop'}]}
    def close(self): pass
''')
    model = tmp_path / 'SIMULATED_MODEL_NOT_GGUF'
    model.write_text('Test-only placeholder')
    out = root / 'data/quality_runs/test'
    cli = [sys.executable, str(root / 'code/quality_check.py'), '--model', str(model),
           '--limit', '3', '--output', str(out)]
    result = subprocess.run(cli, text=True, capture_output=True, timeout=30,
                            env=dict(os.environ, PYTHONPATH=str(adapter)))
    assert result.returncode == 2, result.stdout + result.stderr
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['contract_accepted'] == 3
    assert (summary['quality_passed'], summary['quality_failed']) == (1, 2)
    assert summary['citation_matches'] == 3
    assert summary['status'] == 'partial_quality_check' and not summary['complete_suite']
    assert summary['selected'] == 3 and summary['suite_total'] == 6
    config = json.loads((out / 'config.json').read_text())
    assert config['guide_version'] == 'outofrole-label-guide-v1'
    assert config['suite_sha256'] and config['model_sha256']
    assert (out / 'suite.json').is_file()
    before = (out / 'summary.json').read_bytes()
    again = subprocess.run(cli, text=True, capture_output=True, timeout=10)
    assert again.returncode == 1
    assert (out / 'summary.json').read_bytes() == before
