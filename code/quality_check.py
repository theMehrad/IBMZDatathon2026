"""Frozen synthetic policy-adherence checks, not CERT classification accuracy."""
import json
from runner import evaluate_reply


def grade_reply(fixture, reply, finish_reason, error=None):
    case = dict(rank=1, running_score=0.0, pack=fixture['pack'])
    result = evaluate_reply(case, reply, finish_reason, error)
    parsed = json.loads(reply) if result['accepted'] else {}
    label = parsed.get('label')
    cited = set(parsed.get('facts', []))
    label_match = result['accepted'] and label == fixture['expected_label']
    citation_match = (result['accepted']
                      and set(fixture['required_fact_ids']).issubset(cited)
                      and not set(fixture['forbidden_fact_ids']).intersection(cited)
                      and len(cited) <= fixture['max_cited_facts'])
    result.update(fixture=fixture['id'], expected_label=fixture['expected_label'],
                  actual_label=label, label_match=bool(label_match),
                  citation_match=bool(citation_match),
                  quality_pass=bool(label_match and citation_match))
    return result


def load_suite(path):
    from case_file import LABELS
    from label_guide import GUIDE_VERSION
    suite = json.loads(path.read_text())
    if suite['guide_version'] != GUIDE_VERSION:
        raise ValueError('Fixture suite and guide versions disagree')
    ids = [case['id'] for case in suite['cases']]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Fixture IDs must be nonempty and unique')
    for fixture in suite['cases']:
        if fixture['expected_label'] not in LABELS:
            raise ValueError('Unknown expected label in fixture')
        pack = fixture['pack']
        facts = pack['facts']
        fact_ids = {fact['id'] for fact in facts}
        if not facts or len(fact_ids) != len(facts):
            raise ValueError('Fixture fact IDs must be nonempty and unique')
        strong = any(f['new_to_person'] and f['staff_share'] < 0.01 for f in facts)
        if pack['strength'] != ('strong' if strong else 'weak'):
            raise ValueError('Fixture strength disagrees with the existing strength rule')
        required, forbidden = set(fixture['required_fact_ids']), set(fixture['forbidden_fact_ids'])
        if not (required | forbidden).issubset(fact_ids) or required & forbidden:
            raise ValueError('Fixture citation expectations are inconsistent')
    return suite


def main():
    import argparse
    from datetime import datetime, timezone
    import os
    from pathlib import Path
    import subprocess
    import sys
    import time
    from runner import ROOT, JsonWorker, code_hashes, file_hash, positive_int, write_json
    from label_guide import GUIDE_VERSION

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path)
    parser.add_argument('--model-mode', choices=('completion', 'chat'), default='completion')
    parser.add_argument('--label-guide', choices=('none', 'v1'), default='v1')
    parser.add_argument('--fixtures', type=Path, default=ROOT / 'evidence/quality/label-guide-v1.json')
    parser.add_argument('--limit', type=positive_int, default=3, help='Initial bounded check; suite has six cases')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--list', action='store_true', help='Inspect frozen expectations without loading a model')
    parser.add_argument('--timeout', type=positive_int, default=60)
    parser.add_argument('--startup-timeout', type=positive_int, default=60)
    parser.add_argument('--max-tokens', type=positive_int, default=64)
    parser.add_argument('--context', type=positive_int, default=2048)
    parser.add_argument('--threads', type=positive_int, default=2)
    args = parser.parse_args()
    suite = load_suite(args.fixtures)
    selected = suite['cases'][:args.limit]
    print('SYNTHETIC DEVELOPMENT QUALITY CHECK — not CERT accuracy', flush=True)
    print(f'{len(selected)} selected / {len(suite["cases"])} suite cases; guide={args.label_guide}', flush=True)
    if args.list:
        for fixture in selected:
            print(f'{fixture["id"]}: expected {fixture["expected_label"]}')
        return 0
    if args.model is None:
        parser.error('--model is required unless --list is used')
    os.umask(0o077)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = args.output or ROOT / 'data/quality_runs' / stamp
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    model = args.model.expanduser().resolve()
    config = dict(suite_version=suite['version'], suite_sha256=file_hash(args.fixtures),
                  label_guide=args.label_guide, guide_version=GUIDE_VERSION if args.label_guide == 'v1' else 'none',
                  code_sha256=code_hashes(), quality_check_sha256=file_hash(__file__),
                  model=str(model), model_sha256=file_hash(model) if model.is_file() else None,
                  model_mode=args.model_mode, max_tokens=args.max_tokens, context=args.context,
                  threads=args.threads, temperature=0, timeout=args.timeout,
                  startup_timeout=args.startup_timeout, structured_output=True,
                  selected_ids=[f['id'] for f in selected], suite_total=len(suite['cases']))
    write_json(output / 'config.json', config)
    # Save frozen expectations outside the worker inputs; only pack is sent to inference.
    write_json(output / 'suite.json', suite)
    command = [sys.executable, '-u', str(ROOT / 'code/runner.py'), '_worker',
               '--model', str(model), '--model-mode', args.model_mode,
               '--label-guide', args.label_guide, '--structured-output',
               '--context', str(args.context), '--threads', str(args.threads),
               '--max-tokens', str(args.max_tokens)]
    client = None
    problem = None if model.is_file() else f'Model file not found: {model}'
    results = []
    started = time.monotonic()
    print(f'Output: {output}', flush=True)
    try:
        with (output / 'granite.log').open('w') as log, (output / 'results.jsonl').open('w') as records:
            if not problem:
                try:
                    client = JsonWorker(command, log)
                    ready = client.receive(args.startup_timeout)
                    if ready.get('kind') != 'ready':
                        raise RuntimeError('Worker did not become ready')
                    config['runtime'] = ready
                    write_json(output / 'config.json', config)
                except Exception as exc:
                    problem = f'{type(exc).__name__}: {exc}'
                    if client:
                        client.close()
                        client = None
            for index, fixture in enumerate(selected, 1):
                begin = time.monotonic()
                reply, finish = None, None
                if client:
                    try:
                        answer = client.ask(fixture['pack'], args.timeout)
                        reply, finish = answer.get('reply'), answer.get('finish_reason')
                    except Exception as exc:
                        problem = f'{type(exc).__name__}: {exc}'
                        client.close()
                        client = None
                result = grade_reply(fixture, reply, finish, problem)
                result['elapsed_seconds'] = round(time.monotonic() - begin, 3)
                results.append(result)
                records.write(json.dumps(result) + '\n')
                records.flush()
                os.fsync(records.fileno())
                print(f'\n{index}/{len(selected)} {fixture["id"]}', flush=True)
                print(f'Expected: {result["expected_label"]} | Actual: {result["actual_label"]}', flush=True)
                print(f'Contract accepted: {result["accepted"]} | Citation check: {result["citation_match"]} '
                      f'| Quality: {"PASS" if result["quality_pass"] else "FAIL"}', flush=True)
                print('Raw reply:', repr(reply), flush=True)
                if result['problems']:
                    print('Problems:', result['problems'], flush=True)
    finally:
        if client:
            client.close()
    passed = sum(r['quality_pass'] for r in results)
    complete = len(selected) == len(suite['cases'])
    summary = dict(suite=suite['version'], selected=len(selected), suite_total=len(suite['cases']),
                   contract_accepted=sum(r['accepted'] for r in results),
                   label_matches=sum(r['label_match'] for r in results),
                   citation_matches=sum(r['citation_match'] for r in results),
                   quality_passed=passed, quality_failed=len(selected)-passed, complete_suite=complete,
                   status='completed' if complete else 'partial_quality_check',
                   elapsed_seconds=round(time.monotonic()-started, 3),
                   disclaimer='Synthetic policy adherence only; not CERT accuracy or broad security validation')
    write_json(output / 'summary.json', summary)
    print('\n' + json.dumps(summary, indent=2), flush=True)
    return 0 if passed == len(selected) else 2


if __name__ == '__main__':
    import sys
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
