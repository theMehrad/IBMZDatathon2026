"""Run core scoring, export one day's cases, then classify in a separate process.

No data or model is loaded on import. See docs/RUNNER.md for operational limits.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def export_review(ns, day, release) -> dict[str, Any]:
    """Export the reference detector's exact membership and deterministic order."""
    import numpy as np
    import pandas as pd
    from case_file import pack_from_case

    requested = pd.Timestamp(day)
    t = (requested - ns['CUT']).days
    if requested != ns['CUT'] + pd.Timedelta(days=t) or not 0 <= t < ns['T']:
        raise ValueError('day must be within the release replay period')
    users = ns['users']
    score = np.zeros(len(users))
    lam = 0.5 ** (1 / ns['HALF_LIFE'])
    for j in range(t + 1):
        score = lam * score + ns['pct_score'][:, j]
    jit = np.random.default_rng(0).random(len(users))
    candidates = np.flatnonzero(score > 0)
    order = candidates[np.lexsort((jit[candidates], score[candidates]))[::-1]][:ns['K']]
    if set(order) != set(np.flatnonzero(ns['on_pct'][:, t])):
        raise RuntimeError('Exported review list disagrees with reference detector')
    cases = []
    for rank, i in enumerate(order, 1):
        # Reference case_items applies the selected-day cutoff, independently of grading.
        pack = pack_from_case(f'U-{i + 1:04d}', ns['case_items'](users[i], t))
        if any(not ns['CUT'].date().isoformat() <= f['date'] <= day for f in pack['facts']):
            raise ValueError('Evidence falls outside the past-only replay window')
        cases.append(dict(rank=rank, running_score=float(score[i]), pack=pack))
    return dict(schema_version=1, release=release, day=day, cases=cases,
                pseudonyms='sorted staff index + 1, release-local; not full anonymization')


def evaluate_reply(case, reply, finish_reason, error=None) -> dict[str, Any]:
    """Do not accept truncated completions, even when their prefix is valid JSON."""
    from case_file import case_file
    reason = error or (None if finish_reason == 'stop' else f'Generation did not finish cleanly: {finish_reason}')
    rendered, problems = case_file(case['pack'], None if reason else reply)
    if reason:
        problems = [reason] + problems
    return dict(rank=case['rank'], running_score=case['running_score'],
                person=case['pack']['person'], raw_reply=reply,
                finish_reason=finish_reason, accepted=not problems,
                problems=problems, rendered=rendered)


def response_schema(pack):
    """Constrain structure/IDs, not whether observations justify a strong label."""
    from case_file import LABELS
    ids = [fact['id'] for fact in pack['facts']]
    if not ids:
        raise ValueError('Cannot constrain an empty evidence pack')
    return dict(type='object', additionalProperties=False, required=['label', 'facts'],
                properties=dict(
                    label=dict(type='string', enum=['weak evidence'] if pack['strength'] == 'weak' else list(LABELS)),
                    facts=dict(type='array', minItems=1, maxItems=len(ids),
                               items=dict(type='string', enum=ids))))


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def code_hashes():
    return {name: file_hash(ROOT / 'code' / name) for name in
            ('outofrole_minimal.py', 'case_file.py', 'table_io.py', 'runner.py')}


def prepare_child(args):
    old = sys.argv
    try:
        sys.argv = [str(ROOT / 'code/outofrole_minimal.py'), args.release]
        ns = runpy.run_path(sys.argv[0])
        bundle = export_review(ns, args.day, args.release)
        bundle['code_sha256'] = code_hashes()
        bundle['table_format'] = os.environ.get('OUTOFROLE_TABLE_FORMAT', 'auto')
        from importlib.metadata import version
        bundle['versions'] = dict(python=sys.version, numpy=version('numpy'), pandas=version('pandas'))
        bundle['created_at'] = datetime.now(timezone.utc).isoformat()
        write_json(args.run_dir / 'packs.json', bundle)
        write_json(args.run_dir / 'preparation.json', dict(
            packs_sha256=file_hash(args.run_dir / 'packs.json'),
            code_sha256=bundle['code_sha256'], created_at=bundle['created_at']))
        print(f'Exported {len(bundle["cases"])} cases for {args.day}', flush=True)
    finally:
        sys.argv = old


def prepare(args):
    cutoff = {'4.2': date(2010, 6, 1), '5.2': date(2010, 4, 1)}[args.release]
    if date.fromisoformat(args.day) < cutoff:
        raise ValueError(f'Requested day is before the replay cutoff {cutoff}')
    if args.run_dir is None:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        args.run_dir = ROOT / 'data' / 'runs' / f'r{args.release}-{args.day}-{stamp}'
    args.run_dir = args.run_dir.resolve()
    args.run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    print(f'Stage 1/2: core scoring. Log: {args.run_dir / "scoring.log"}', flush=True)
    env = dict(os.environ, OUTOFROLE_TABLE_FORMAT=args.table_format,
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    command = [sys.executable, '-u', __file__, '_prepare', '--release', args.release,
               '--day', args.day, '--run-dir', str(args.run_dir)]
    with (args.run_dir / 'scoring.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env, check=True)
    # Child exit releases scoring arrays before any Granite model is started.
    print((args.run_dir / 'scoring.log').read_text(), flush=True)
    return args.run_dir


def worker(args):
    """JSON-line protocol on stdout; diagnostics go to stderr, never the analyst UI."""
    from contextlib import redirect_stdout
    from importlib.metadata import version, PackageNotFoundError
    def emit(value):
        print(json.dumps(value), flush=True)
    model = None
    try:
        with redirect_stdout(sys.stderr):
            from importlib import import_module
            runtime = import_module('llama_cpp')
            Llama = runtime.Llama
            from case_file import prompt
            model = Llama(model_path=str(args.model), n_ctx=args.context,
                          n_threads=args.threads, n_batch=128, n_gpu_layers=0, verbose=False)
            if args.model_mode == 'chat' and not model.metadata.get('tokenizer.chat_template'):
                raise ValueError('Embedded chat template required; refusing guessed chat format')
        try:
            runtime_version = version('llama-cpp-python')
        except PackageNotFoundError:
            runtime_version = 'unknown'
        emit(dict(kind='ready', model_name=model.metadata.get('general.name'),
                  runtime_version=runtime_version, model_mode=args.model_mode))
        for line in sys.stdin:
            request = json.loads(line)
            try:
                with redirect_stdout(sys.stderr):
                    options = {}
                    if args.structured_output:
                        # Explicit grammar construction: failure must not silently
                        # retry as unconstrained JSON/text.
                        options['grammar'] = runtime.LlamaGrammar.from_json_schema(
                            json.dumps(response_schema(request['pack'])), verbose=False)
                    if args.model_mode == 'completion':
                        result = model.create_completion(
                            prompt=prompt(request['pack']) + '\nJSON response:\n',
                            temperature=0, max_tokens=args.max_tokens, **options)
                    else:
                        result = model.create_chat_completion(
                            messages=[dict(role='user', content=prompt(request['pack']))],
                            temperature=0, max_tokens=args.max_tokens, **options)
                choice = result['choices'][0]
                reply = choice['text'] if args.model_mode == 'completion' else choice['message']['content']
                emit(dict(kind='reply', person=request['pack']['person'],
                          reply=reply, finish_reason=choice['finish_reason']))
            except Exception as exc:
                emit(dict(kind='error', error=f'{type(exc).__name__}: {exc}'))
                return 1
        return 0
    except Exception as exc:
        emit(dict(kind='error', error=f'{type(exc).__name__}: {exc}'))
        return 1
    finally:
        if model is not None:
            with redirect_stdout(sys.stderr):
                model.close()


class JsonWorker:
    """One model process with bounded startup and per-case waits (POSIX)."""
    def __init__(self, command, log):
        import selectors
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=log, text=True, bufsize=1,
                                        env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
        self.selector = selectors.DefaultSelector()
        assert self.process.stdin is not None and self.process.stdout is not None
        self.input = self.process.stdin
        self.output = self.process.stdout
        self.selector.register(self.output, selectors.EVENT_READ)
        self.buffer = b''

    def receive(self, timeout):
        import time
        deadline = time.monotonic() + timeout
        while b'\n' not in self.buffer:
            remaining = max(0, deadline - time.monotonic())
            if not self.selector.select(remaining):
                raise TimeoutError(f'Granite timed out after {timeout:g} seconds')
            chunk = os.read(self.output.fileno(), 65536)
            if not chunk:
                raise RuntimeError('Granite worker exited without a response; see granite.log')
            self.buffer += chunk
            if len(self.buffer) > 1024 * 1024:
                raise RuntimeError('Granite worker response exceeded protocol limit')
        line, self.buffer = self.buffer.split(b'\n', 1)
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError('Invalid Granite worker protocol')
        if value.get('kind') == 'error':
            raise RuntimeError(value.get('error', 'Unknown Granite worker error'))
        return value

    def ask(self, pack, timeout):
        self.input.write(json.dumps(dict(pack=pack)) + '\n')
        self.input.flush()
        value = self.receive(timeout)
        if value.get('kind') != 'reply' or value.get('person') != pack['person']:
            raise RuntimeError('Granite reply did not match the requested person')
        return value

    def close(self):
        self.selector.close()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.input.close()
        self.output.close()


def infer(args):
    import time
    manifest = json.loads((args.run_dir / 'preparation.json').read_text())
    if file_hash(args.run_dir / 'packs.json') != manifest['packs_sha256']:
        raise ValueError('Pack digest mismatch: evidence export changed since preparation')
    bundle = json.loads((args.run_dir / 'packs.json').read_text())
    if bundle['code_sha256'] != manifest['code_sha256']:
        raise ValueError('Preparation provenance disagrees with pack export')
    current_hashes = code_hashes()
    changed = {name for name in set(bundle['code_sha256']) | set(current_hashes)
               if bundle['code_sha256'].get(name) != current_hashes.get(name)}
    if changed and not (args.allow_runner_update and changed == {'runner.py'}):
        raise ValueError('Code changed since pack export; prepare again or explicitly allow a runner-only update')
    cases = bundle['cases']
    if [c['rank'] for c in cases] != list(range(1, len(cases) + 1)):
        raise ValueError('Review ranks are not consecutive')
    people = [c['pack']['person'] for c in cases]
    if len(set(people)) != len(people):
        raise ValueError('Duplicate person in exported list')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    attempt = args.run_dir / 'attempts' / stamp
    attempt.mkdir(parents=True, exist_ok=False, mode=0o700)
    config = dict(model_path=str(args.model), model_sha256=None,
                  context=args.context, threads=args.threads, max_tokens=args.max_tokens,
                  temperature=0, startup_timeout=args.startup_timeout, case_timeout=args.timeout,
                  structured_output=args.structured_output, max_cases=args.max_cases, model_mode=args.model_mode,
                  prepared_code_sha256=bundle['code_sha256'],
                  allowed_runner_update=bool(changed),
                  created_at=datetime.now(timezone.utc).isoformat(), code_sha256=current_hashes)
    # Missing model/runtime and startup failure become explicit fallbacks for every name.
    problem = None
    if not args.model.is_file():
        problem = f'Model file not found: {args.model}'
    else:
        config['model_sha256'] = file_hash(args.model)
    write_json(attempt / 'config.json', config)
    print(f'Stage 2/2: Granite for {len(cases)} cases. Results: {attempt}', flush=True)
    command = [sys.executable, '-u', __file__, '_worker', '--model', str(args.model),
               '--context', str(args.context), '--threads', str(args.threads),
               '--max-tokens', str(args.max_tokens), '--model-mode', args.model_mode]
    if args.structured_output:
        command.append('--structured-output')
    if args.max_cases is not None:
        print(f'Diagnostic limit: infer first {min(args.max_cases, len(cases))} case(s); '
              'retain remaining names as NOT INFERRED.', flush=True)
    client = None
    results = []
    started = time.monotonic()
    try:
        with (attempt / 'granite.log').open('w') as log, (attempt / 'results.jsonl').open('w') as records:
            if not problem and cases:
                try:
                    client = JsonWorker(command, log)
                    ready = client.receive(args.startup_timeout)
                    if ready.get('kind') != 'ready':
                        raise RuntimeError('Granite worker did not become ready')
                    config['runtime'] = ready
                    write_json(attempt / 'config.json', config)
                except Exception as exc:
                    problem = f'{type(exc).__name__}: {exc}'
                    if client:
                        client.close()
                        client = None
            for case in cases:
                begin = time.monotonic()
                reply, finish, reason = None, None, problem
                skipped = args.max_cases is not None and case['rank'] > args.max_cases
                if skipped:
                    reason = 'Not inferred: diagnostic --max-cases limit'
                elif not case['pack']['facts']:
                    reason = 'No replay evidence available for this person on this day'
                elif client:
                    try:
                        answer = client.ask(case['pack'], args.timeout)
                        reply, finish = answer.get('reply'), answer.get('finish_reason')
                    except Exception as exc:
                        problem = reason = f'{type(exc).__name__}: {exc}'
                        client.close()
                        client = None
                result = evaluate_reply(case, reply, finish, reason)
                result['skipped'] = skipped
                if args.structured_output and not skipped and case['pack']['facts']:
                    result['response_schema'] = response_schema(case['pack'])
                result['elapsed_seconds'] = round(time.monotonic() - begin, 3)
                results.append(result)
                records.write(json.dumps(result) + '\n')
                records.flush()
                os.fsync(records.fileno())
                print(f'{case["rank"]}/{len(cases)} {result["person"]}: '
                      f'{"NOT INFERRED" if skipped else "ACCEPTED" if result["accepted"] else "FALLBACK"}', flush=True)
                if args.max_cases is not None and not skipped:
                    print('Diagnostic raw reply:', repr(reply), flush=True)
                    print('Validation problems:', result['problems'], flush=True)
                    print(result['rendered'], flush=True)
    finally:
        if client:
            client.close()
    assert [r['person'] for r in results] == people, 'Review list/order changed'
    accepted = sum(r['accepted'] for r in results)
    skipped = sum(r['skipped'] for r in results)
    fallback = len(cases) - accepted - skipped
    summary = dict(day=bundle['day'], release=bundle['release'], total=len(cases),
                   accepted=accepted, fallback=fallback, skipped=skipped,
                   elapsed_seconds=round(time.monotonic() - started, 3),
                   status='completed_with_fallbacks' if fallback else 'partial_test' if skipped else 'completed',
                   semantic_accuracy='not evaluated; acceptance validates the response contract only')
    write_json(attempt / 'summary.json', summary)
    (attempt / 'case_files.txt').write_text('\n\n'.join(
        ('[NOT INFERRED: diagnostic limit]\n' if r['skipped'] else '') + r['rendered']
        for r in results) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
    print(f'Case files: {attempt / "case_files.txt"}', flush=True)
    return 0 if not summary['fallback'] else 2


def iso_day(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError('Use an exact YYYY-MM-DD date')
    return value


def positive_int(value):
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError('Must be positive')
    return n


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='stage', required=True)
    for name in ('run', 'prepare', 'infer', '_prepare', '_worker'):
        sub = subs.add_parser(name)
        if name in ('run', 'prepare', '_prepare'):
            sub.add_argument('--release', choices=('4.2', '5.2'), required=True)
            sub.add_argument('--day', type=iso_day, required=True)
            sub.add_argument('--table-format', choices=('auto', 'csv', 'parquet'), default='auto')
        if name != '_worker':
            sub.add_argument('--run-dir', type=Path, required=name in ('infer', '_prepare'))
        if name in ('run', 'infer', '_worker'):
            sub.add_argument('--model', type=Path, required=True)
            sub.add_argument('--model-mode', choices=('chat', 'completion'), default='chat',
                             help='Explicit plain completion for base models; chat uses embedded template')
            sub.add_argument('--context', type=positive_int, default=2048)
            sub.add_argument('--threads', type=positive_int, default=2)
            sub.add_argument('--max-tokens', type=positive_int, default=128)
            sub.add_argument('--timeout', type=positive_int, default=300)
            sub.add_argument('--startup-timeout', type=positive_int, default=180)
            sub.add_argument('--structured-output', action='store_true',
                             help='Apply a per-pack JSON grammar; keep the validator unchanged')
            if name != '_worker':
                sub.add_argument('--max-cases', type=positive_int,
                                 help='Diagnostic limit; retain other names as not inferred')
                sub.add_argument('--allow-runner-update', action='store_true',
                                 help='Reuse packs if only runner.py changed; record both revisions')
    args = parser.parse_args()
    os.umask(0o077)
    if hasattr(args, 'model'):
        args.model = args.model.expanduser().resolve()
    if args.stage == '_prepare':
        prepare_child(args)
        return 0
    if args.stage == '_worker':
        return worker(args)
    if args.stage in ('run', 'prepare'):
        prepare(args)
        print(f'Run directory: {args.run_dir}', flush=True)
    if args.stage in ('run', 'infer'):
        return infer(args)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(cli())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
