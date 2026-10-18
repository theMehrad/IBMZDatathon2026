import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
from test_runner_cli import synthetic_repo


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
    repeated = grade_reply(fixture, '{"label":"possible data leak","facts":["E1","E1","E1"]}', 'stop')
    assert repeated['accepted'] and not repeated['quality_pass']
    assert not repeated['citation_match']


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


def test_grading_keeps_raw_quality_when_policy_guard_rejects():
    from quality_check import grade_reply
    fixture = dict(id='guard', expected_label='possible data theft',
                   required_fact_ids=['Q7'], forbidden_fact_ids=[], max_cited_facts=2,
                   pack=dict(person='EVAL-A', strength='strong', facts=[
                       dict(id='Q7', what='used a USB device', item='USB', date='2010-08-02',
                            new_to_person=True, staff_share=0.001)]))
    result = grade_reply(fixture, '{"label":"possible data theft","facts":["Q7"]}',
                         'stop', evidence_policy='v2')
    assert result['contract_accepted'] is True
    assert result['policy_accepted'] is False
    assert result['accepted'] is False
    assert result['label_match'] is True
    assert result['citation_match'] is True
    assert result['quality_pass'] is True  # Raw model choice, not a fallback "improvement".
    assert result['actual_label'] == 'possible data theft'


def test_v2_suite_is_prompt_disjoint_and_strength_consistent():
    from quality_check import load_suite
    root = Path(__file__).resolve().parents[1]
    suite = load_suite(root / 'evidence/quality/evidence-policy-v2.json')
    assert len(suite['cases']) == 8
    assert suite['guide_version'] == 'outofrole-label-guide-v2'
    assert {case['expected_label'] for case in suite['cases']} == {
        'weak evidence', 'possible data leak', 'possible data theft',
        'possible snooping', 'unusual after-hours activity'}
    assert all(case['pack']['person'].startswith('EVAL-') for case in suite['cases'])
    assert all(fact['id'].startswith('Q') for case in suite['cases'] for fact in case['pack']['facts'])
    assert all(case['pack']['strength'] == 'strong' for case in suite['cases'])
    assert [case['expected_label'] for case in suite['cases'][:3]] == [
        'weak evidence', 'possible data leak', 'possible data theft']


def test_v2_frozen_expected_answers_are_policy_accepted_and_mixed_secondary_allowed():
    from quality_check import grade_reply, load_suite
    root = Path(__file__).resolve().parents[1]
    suite = load_suite(root / 'evidence/quality/evidence-policy-v2.json')
    for fixture in suite['cases']:
        reply = json.dumps({'label': fixture['expected_label'], 'facts': fixture['required_fact_ids']})
        grade = grade_reply(fixture, reply, 'stop', evidence_policy='v2')
        assert grade['quality_pass'] and grade['accepted'], (fixture['id'], grade)
    mixed = suite['cases'][6]
    grade = grade_reply(mixed, json.dumps({'label': 'possible data leak',
                                           'facts': ['Q18', 'Q19']}), 'stop', evidence_policy='v2')
    assert grade['quality_pass'] and grade['accepted']


def test_quality_snapshot_hashes_guard_source_for_provenance():
    from runner import ROOT, code_hashes, file_hash
    hashes = code_hashes()
    assert hashes['evidence_policy.py'] == file_hash(ROOT / 'code/evidence_policy.py')


def test_old_preparation_needs_explicit_override_for_new_guard_hash(synthetic_repo):
    import hashlib
    from test_runner_cli import command
    root = synthetic_repo
    run = root / 'data/runs/old-preparation'
    prepared = command(root, 'prepare', '--release', '4.2', '--day', '2010-06-02', '--run-dir', str(run))
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    bundle = json.loads((run / 'packs.json').read_text())
    manifest = json.loads((run / 'preparation.json').read_text())
    bundle['code_sha256'].pop('evidence_policy.py')  # A real earlier export lacks this source file.
    manifest['code_sha256'] = bundle['code_sha256']
    (run / 'packs.json').write_text(json.dumps(bundle))
    manifest['packs_sha256'] = hashlib.sha256((run / 'packs.json').read_bytes()).hexdigest()
    (run / 'preparation.json').write_text(json.dumps(manifest))
    args = ('infer', '--run-dir', str(run), '--model', str(root / 'missing.gguf'),
            '--evidence-policy', 'v2', '--max-cases', '1')
    rejected = command(root, *args)
    assert rejected.returncode == 1 and 'Code changed' in rejected.stderr
    allowed = command(root, *args, '--allow-runner-update')
    assert allowed.returncode == 2, allowed.stdout + allowed.stderr  # Missing model; provenance check passed.
    attempt, = (run / 'attempts').iterdir()
    config = json.loads((attempt / 'config.json').read_text())
    assert config['allowed_runner_update'] and config['evidence_policy'] == 'v2'
    assert 'evidence_policy.py' not in config['prepared_code_sha256']
    assert config['code_sha256']['evidence_policy.py']


def test_v2_cli_tracks_guard_separately_from_raw_quality(tmp_path):
    import os
    import shutil
    import subprocess
    original = Path(__file__).resolve().parents[1]
    root = tmp_path / 'repo'
    shutil.copytree(original / 'code', root / 'code', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(original / 'evidence/quality', root / 'evidence/quality')
    adapter = tmp_path / 'adapter'
    adapter.mkdir()
    (adapter / 'llama_cpp.py').write_text('''
import json
class LlamaGrammar:
    @classmethod
    def from_json_schema(cls, text, verbose=False): return json.loads(text)
class Llama:
    metadata = {'general.name': 'SIMULATED V2 ADAPTER'}
    def __init__(self, **kwargs): pass
    def create_completion(self, **kwargs):
        text = kwargs['prompt']
        assert 'DEMO-01' in text and 'usb_connected' in text
        assert 'expected_label' not in text and 'usb-only-guard' not in text
        assert 'grammar' in kwargs
        return {'choices': [{'text': '{"label":"possible data theft","facts":["Q7"]}', 'finish_reason': 'stop'}]}
    def close(self): pass
''')
    model = tmp_path / 'SIMULATED_MODEL_NOT_GGUF'
    model.write_text('Test-only placeholder')
    out = root / 'data/quality_runs/v2'
    cli = [sys.executable, str(root / 'code/quality_check.py'), '--model', str(model),
           '--label-guide', 'v2', '--evidence-policy', 'v2', '--limit', '1', '--output', str(out)]
    result = subprocess.run(cli, text=True, capture_output=True, timeout=30,
                            env=dict(os.environ, PYTHONPATH=str(adapter)))
    assert result.returncode == 2, result.stdout + result.stderr
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['contract_accepted'] == 1
    assert summary['system_accepted'] == 0
    assert summary['policy_rejected'] == 1
    assert (summary['label_matches'], summary['citation_matches'], summary['quality_passed']) == (0, 1, 0)
    config = json.loads((out / 'config.json').read_text())
    assert config['suite_version'] == 'outofrole-quality-v2'
    assert config['suite_guide_version'] == 'outofrole-label-guide-v2'
    assert config['guide_version'] == 'outofrole-label-guide-v2'
    assert config['evidence_policy'] == 'v2'
    without_guard = root / 'data/quality_runs/v2-no-guard'
    unguarded = subprocess.run(cli[:cli.index('--evidence-policy')] +
                               ['--evidence-policy', 'none', '--limit', '1', '--output', str(without_guard)],
                               text=True, capture_output=True, timeout=30,
                               env=dict(os.environ, PYTHONPATH=str(adapter)))
    assert unguarded.returncode == 2, unguarded.stdout + unguarded.stderr
    comparison = json.loads((without_guard / 'summary.json').read_text())
    assert (comparison['contract_accepted'], comparison['system_accepted'],
            comparison['policy_rejected'], comparison['quality_passed']) == (1, 1, 0, 0)
    baseline = subprocess.run([sys.executable, str(root / 'code/quality_check.py'),
                               '--label-guide', 'v1', '--fixtures', str(root / 'evidence/quality/evidence-policy-v2.json'),
                               '--list', '--limit', '1'], text=True, capture_output=True, timeout=10)
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
