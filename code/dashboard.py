"""Read-only local dashboard. Never imports the scorer, Spark, or model runtime."""
import argparse
import csv
from collections import defaultdict
from datetime import datetime
import json
import hashlib
import math
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from case_file import accept, case_file, sentence
from dashboard_pipeline import readiness

ROOT = Path(__file__).resolve().parents[1]


def load_activity_preview(raw, day=None, limit=50000):
    """Bounded raw-data preview, explicitly separate from the detector's queue."""
    path = raw / 'logon.csv'
    if not path.is_file():
        return None, []
    by_day = defaultdict(list)
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for index, row in enumerate(csv.DictReader(stream)):
            if index >= limit:
                break
            stamp = datetime.strptime(row['date'], '%m/%d/%Y %H:%M:%S')
            by_day[stamp.date().isoformat()].append(row)
    dates = sorted(by_day)
    if not dates:
        return None, []
    day = day or dates[-1]
    if day not in by_day:
        raise ValueError('Date is outside the bounded r4.2 activity preview')
    users = defaultdict(list)
    for row in by_day[day]:
        users[row['user']].append(row)
    cases = []
    for index, (person, events) in enumerate(sorted(users.items()), 1):
        facts = [dict(id='L' + str(i + 1), date=day, time=row['date'].split(' ')[1],
                      what=row['activity'], title=row['activity'], icon='LogIn', source=row['id'],
                      text=f"{row['date']}: {row['activity']} on {row['pc']}.")
                 for i, row in enumerate(sorted(events, key=lambda r: r['date']))]
        cases.append(dict(person=person, rank=index, score=None, strength='Not scored',
                          signal=f'{len(events)} observed logon/logoff records', employee='CERT r4.2 benchmark identity',
                          facts=facts, label='Not inferred', cited=[], status='Not inferred', rendered='', problems=[]))
    note = (f'Preview of the first {limit:,} logon.csv records only. Counts cover the selected day within that preview, '
            'not the full dataset. Employees are listed alphabetically; this is not a ranked alert queue.')
    return dict(id='CERT r4.2 / activity preview', release='4.2', day=day, cases=cases,
                mode='activity', attempt=None, warnings=[note, 'No processed detector queue or Granite outputs are available for this view.'],
                metrics=dict(employees=len(users), events=len(by_day[day]), note=note)), dates


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_workspace(run, attempt=None):
    bundle = read_json(run / 'packs.json')
    results, warnings = {}, []
    manifest_path = run / 'preparation.json'
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        if hashlib.sha256((run / 'packs.json').read_bytes()).hexdigest() != manifest.get('packs_sha256'):
            raise ValueError('Prepared pack digest mismatch; scores and assessments were not loaded')
        if bundle.get('code_sha256') != manifest.get('code_sha256'):
            raise ValueError('Preparation provenance disagrees with the exported pack')
    else:
        warnings.append('No preparation manifest found; exported scoring provenance cannot be verified.')
    attempts = sorted((run / 'attempts').glob('*/results.jsonl'))
    result_path = attempt / 'results.jsonl' if attempt else (attempts[-1] if attempts else None)
    if result_path and result_path.exists():
        for line in result_path.read_text(encoding='utf-8').splitlines():
            try:
                result = json.loads(line)
                results[result['person']] = result
            except (ValueError, KeyError):
                warnings.append('An incomplete result record was ignored; refresh after inference completes.')
    cases = []
    for entry in bundle['cases']:
        pack = entry['pack']
        result = results.get(pack['person'])
        matches = not result or (result.get('rank', entry['rank']) == entry['rank'] and
                                 result.get('running_score', entry['running_score']) == entry['running_score'])
        usable = result and result.get('accepted') is True and not result.get('skipped') and result.get('finish_reason') == 'stop'
        usable = usable and matches
        reply = result.get('raw_reply') if usable else None
        label, cited, problems = accept(reply, pack) if reply else (None, [], ['No validated model reply'])
        rendered, _ = case_file(pack, reply)
        status = ('Accepted' if not problems else 'Fallback') if result else 'Not inferred'
        if result and result.get('skipped'):
            status = 'Not inferred'
        facts = [dict(f, text=sentence(f)) for f in pack['facts']]
        score = float(entry['running_score'])
        cases.append(dict(person=pack['person'], rank=entry['rank'], score=score if math.isfinite(score) else None,
                          strength=pack['strength'], facts=facts, label=label or ('weak evidence' if pack['strength'] == 'weak' else 'needs review'),
                          cited=cited if not problems else [], status=status, rendered=rendered,
                          elapsed_seconds=result.get('elapsed_seconds') if result else None,
                          problems=(result.get('problems', []) if result else []) + (problems if usable else []) +
                          ([] if matches else ['Result rank or score does not match the prepared queue'])))
    config_path = result_path.parent / 'config.json' if result_path else None
    config = read_json(config_path) if config_path and config_path.exists() else {}
    progress = {status: sum(c['status'] == status for c in cases)
                for status in ('Accepted', 'Fallback', 'Not inferred')}
    return dict(id=run.name, release=bundle['release'], day=bundle['day'], cases=cases,
                attempt=result_path.parent.name if result_path else None, warnings=warnings,
                attempts=[p.parent.name for p in attempts], progress=progress,
                model=dict(name=config.get('runtime', {}).get('model_name'),
                           sha256=config.get('model_sha256'), mode=config.get('model_mode'),
                           structured_output=config.get('structured_output')),
                created_at=bundle.get('created_at'),
                scoring_contract='Original detector order; running score decays with a 7-day half-life. Not a probability or a score out of 100.')


def processed_metrics(cache, release, day):
    work = cache / ('r' + release)
    if not (work / 'daily').exists() and not Path(str(work) + '_csv').exists():
        return dict(employees=None, events=None, note='Processed daily table is not available.')
    try:
        from table_io import read_table
        daily = read_table(work, 'daily')
        rows = daily[daily.day.astype(str).str[:10] == day]
        columns = ['n_logon', 'n_usb', 'n_file', 'n_http']
        return dict(employees=int(rows.user.nunique()), events=int(rows[columns].sum().sum()),
                    note='Selected-day active employees and processed logon, USB, file and HTTP counts; not detector evaluation totals.')
    except (ImportError, OSError, ValueError, KeyError) as exc:
        return dict(employees=None, events=None, note='Processed totals unavailable: ' + str(exc))


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def guess_type(self, path):
        mime = super().guess_type(path)
        if mime in ('text/html', 'text/css', 'text/javascript', 'application/javascript'):
            return mime + '; charset=utf-8'
        return mime

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path != '/api/workspace':
            if url.path == '/':
                self.path = '/index.html'
            return super().do_GET()
        try:
            runs = [self.server.run_dir] if self.server.run_dir else sorted(self.server.runs.glob('*/packs.json'))
            runs = [p.parent if p.name == 'packs.json' else p for p in runs]
            choices = [dict(id=p.name, day=read_json(p / 'packs.json')['day']) for p in runs]
            requested = parse_qs(url.query).get('run', [None])[0]
            params = parse_qs(url.query)
            source = params.get('source', ['auto'])[0]
            if source not in ('auto', 'runner', 'activity'):
                raise ValueError('Unknown data source')
            dates = []
            pipeline = readiness(self.server.cache, model=getattr(self.server, 'model', None))
            if source == 'activity' or (source == 'auto' and (requested == 'activity' or (not runs and requested is None))):
                data, dates = load_activity_preview(self.server.raw, params.get('day', [None])[0])
                payload = json.dumps(dict(runs=choices, workspace=data, activity_dates=dates, pipeline=pipeline), allow_nan=False).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            selected = next((p for p in runs if p.name == requested), None) if requested else (runs[-1] if runs else None)
            if requested and selected is None:
                raise ValueError('Unknown run')
            attempt = self.server.attempt
            attempt_id = params.get('attempt', [None])[0]
            if attempt_id and selected:
                attempt = next((p.parent for p in (selected / 'attempts').glob('*/results.jsonl') if p.parent.name == attempt_id), None)
                if attempt is None:
                    raise ValueError('Unknown inference attempt')
            data = load_workspace(selected, attempt) if selected else None
            if data:
                data['metrics'] = processed_metrics(self.server.cache, data['release'], data['day'])
            pipeline = readiness(self.server.cache, data['release'] if data else '4.2', getattr(self.server, 'model', None))
            payload = json.dumps(dict(runs=choices, workspace=data, activity_dates=dates, pipeline=pipeline), allow_nan=False).encode()
            self.send_response(200)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            payload = json.dumps(dict(error='Cannot read dashboard inputs: ' + str(exc))).encode()
            self.send_response(400)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--runs', type=Path, default=ROOT / 'data/runs')
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--raw', type=Path, default=ROOT / 'data/r4.2/r4.2', help='Existing r4.2 raw CSV directory for the bounded activity preview')
    parser.add_argument('--attempt', type=Path, help='Explicit attempt directory; requires --run-dir')
    parser.add_argument('--model', type=Path, default=Path(os.environ['OUTOFROLE_GRANITE_MODEL']) if os.environ.get('OUTOFROLE_GRANITE_MODEL') else None,
                        help='Existing Granite GGUF path for readiness checks only; never starts inference')
    parser.add_argument('--cache', type=Path, default=Path(os.environ.get('OUTOFROLE_CACHE', ROOT / 'data/cache')))
    args = parser.parse_args()
    if args.attempt and not args.run_dir:
        parser.error('--attempt requires --run-dir')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(ROOT / 'web/dashboard')))
    server.runs, server.run_dir, server.attempt, server.cache = args.runs, args.run_dir, args.attempt, args.cache
    server.raw = args.raw
    server.model = args.model
    print(f'OutOfRole: http://127.0.0.1:{args.port} (read-only; no scoring or inference)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
