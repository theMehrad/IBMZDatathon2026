"""Preflight and explicitly invoke the existing scoring/Granite runner. Never runs Spark."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('daily', 'pc_pairs', 'dom_pairs')


def readiness(cache, release='4.2', model=None, root=ROOT):
    modules = {name: importlib.util.find_spec(name) is not None
               for name in ('numpy', 'pandas', 'pyarrow', 'fastparquet', 'llama_cpp')}
    mode = os.environ.get('OUTOFROLE_TABLE_FORMAT', 'auto')
    tables = []
    for name in TABLES:
        csv = cache / f'r{release}_csv' / name
        parquet = cache / f'r{release}' / name
        use_csv = mode == 'csv' or (mode == 'auto' and csv.exists())
        complete = ((csv / '_SUCCESS').is_file() and any(csv.glob('part-*.csv'))) if use_csv else any(parquet.rglob('*.parquet'))
        reader = True if use_csv else modules['pyarrow'] or modules['fastparquet']
        tables.append(dict(name=name, path=str(csv if use_csv else parquet),
                           format='csv' if use_csv else 'parquet', complete=bool(complete), readable=bool(complete and reader)))
    scoring = [f"{t['name']}: missing/incomplete {t['format']} export" if not t['complete']
               else f"{t['name']}: missing Parquet reader" for t in tables if not t['readable']]
    for module in ('numpy', 'pandas'):
        if not modules[module]:
            scoring.append(f'Missing scoring dependency: {module}')
    if not (root / 'data/answers/answers/insiders.csv').is_file():
        scoring.append('Missing answer-key CSV required by the existing evaluation script (never sent to Granite)')
    if mode not in ('auto', 'csv', 'parquet'):
        scoring.append('Invalid OUTOFROLE_TABLE_FORMAT')
    granite = []
    if os.name != 'posix':
        granite.append('The existing Granite worker uses POSIX pipe selectors; run inference on Linux/RHEL')
    if not modules['llama_cpp']:
        granite.append('llama-cpp-python runtime is not installed')
    if model is None or not model.is_file():
        granite.append('No existing GGUF model configured; use --model or OUTOFROLE_GRANITE_MODEL')
    return dict(release=release, tables=tables, scoring_ready=not scoring,
                granite_ready=not granite, scoring_blockers=scoring, granite_blockers=granite,
                model_configured=bool(model and model.is_file()), modules=modules)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    stages = parser.add_subparsers(dest='stage', required=True)
    for stage in ('check', 'prepare', 'infer'):
        sub = stages.add_parser(stage)
        sub.add_argument('--release', choices=('4.2', '5.2'), default='4.2')
        sub.add_argument('--cache', type=Path, default=Path(os.environ.get('OUTOFROLE_CACHE', ROOT / 'data/cache')))
        sub.add_argument('--model', type=Path, default=Path(os.environ['OUTOFROLE_GRANITE_MODEL']) if os.environ.get('OUTOFROLE_GRANITE_MODEL') else None)
        if stage == 'prepare':
            sub.add_argument('--day', required=True, help='Explicit replay date; never selected using the answer key')
            sub.add_argument('--run-dir', type=Path)
        if stage == 'infer':
            sub.add_argument('--run-dir', type=Path, required=True)
            sub.add_argument('--model-mode', choices=('chat', 'completion'), default='chat')
            sub.add_argument('--max-cases', type=int, default=1, help='Diagnostic limit; preserves all remaining queue entries')
    args = parser.parse_args(argv)
    status = readiness(args.cache, args.release, args.model)
    if args.stage == 'check':
        print(json.dumps(status, indent=2))
        return 0
    blockers = status['scoring_blockers' if args.stage == 'prepare' else 'granite_blockers'][:]
    if args.stage == 'infer':
        if args.max_cases <= 0:
            blockers.append('--max-cases must be positive')
        for name in ('packs.json', 'preparation.json'):
            if not (args.run_dir / name).is_file():
                blockers.append(f'Missing prepared {name}')
    if blockers:
        print('\n'.join(blockers), file=sys.stderr)
        return 2
    command = [sys.executable, str(ROOT / 'code/runner.py'), args.stage]
    if args.stage == 'prepare':
        command += ['--release', args.release, '--day', args.day,
                    '--table-format', os.environ.get('OUTOFROLE_TABLE_FORMAT', 'auto')]
        if args.run_dir:
            command += ['--run-dir', str(args.run_dir)]
    else:
        command += ['--run-dir', str(args.run_dir), '--model', str(args.model),
                    '--model-mode', args.model_mode, '--structured-output', '--max-cases', str(args.max_cases)]
    return subprocess.call(command, env=dict(os.environ, OUTOFROLE_CACHE=str(args.cache)))


if __name__ == '__main__':
    sys.exit(main())
