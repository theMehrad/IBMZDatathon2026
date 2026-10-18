"""Dashboard adapter tests use synthetic packs, never Spark or a model."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
from dashboard import Handler, load_workspace, processed_metrics, load_activity_preview
from dashboard_pipeline import readiness, main as pipeline_main


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name)
        self.pack = dict(person='U-0001', strength='strong', facts=[dict(
            id='E1', what='visited website', item='<script>example</script>',
            date='2010-08-02', new_to_person=True, staff_share=0.001)])
        self.bundle = dict(release='4.2', day='2010-08-02', cases=[
            dict(rank=1, running_score=7.25, pack=self.pack)])
        (self.run / 'packs.json').write_text(json.dumps(self.bundle))
        self.attempt = self.run / 'attempts' / '001'
        self.attempt.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def result(self, **changes):
        value = dict(person='U-0001', accepted=True, skipped=False, finish_reason='stop',
                     raw_reply=json.dumps(dict(label='possible data leak', facts=['E1'])), problems=[])
        value.update(changes)
        (self.attempt / 'results.jsonl').write_text(json.dumps(value) + '\n')

    def test_preserves_rank_score_and_validated_citations(self):
        self.result()
        case = load_workspace(self.run)['cases'][0]
        self.assertEqual((case['rank'], case['score']), (1, 7.25))
        self.assertEqual(case['cited'], ['E1'])
        self.assertEqual(case['status'], 'Accepted')
        self.assertNotIn('priority', case)

    def test_unknown_citation_fails_closed_despite_accepted_flag(self):
        self.result(raw_reply='{"label":"possible data leak","facts":["E9"]}')
        case = load_workspace(self.run)['cases'][0]
        self.assertEqual(case['status'], 'Fallback')
        self.assertEqual(case['label'], 'needs review')
        self.assertEqual(case['cited'], [])

    def test_truncated_and_skipped_results_are_not_accepted(self):
        for changes, expected in [({'finish_reason':'length'}, 'Fallback'),
                                  ({'skipped':True}, 'Not inferred')]:
            self.result(**changes)
            case = load_workspace(self.run)['cases'][0]
            self.assertEqual(case['status'], expected)
            self.assertEqual(case['cited'], [])

    def test_missing_results_and_partial_line(self):
        self.assertEqual(load_workspace(self.run)['cases'][0]['status'], 'Not inferred')
        self.result()
        with (self.attempt / 'results.jsonl').open('a') as f:
            f.write('{')
        loaded = load_workspace(self.run)
        self.assertEqual(loaded['cases'][0]['status'], 'Accepted')
        self.assertTrue(loaded['warnings'])

    def test_missing_tables_are_unknown_not_sample_totals(self):
        metrics = processed_metrics(self.run / 'missing', '4.2', '2010-08-02')
        self.assertIsNone(metrics['employees'])
        self.assertIsNone(metrics['events'])

    def test_inference_progress_and_model_provenance(self):
        self.result()
        (self.attempt / 'config.json').write_text(json.dumps(dict(
            model_sha256='abc', model_mode='chat', structured_output=True,
            runtime=dict(model_name='Synthetic adapter, not a real model'))))
        value = load_workspace(self.run)
        self.assertEqual(value['attempts'], ['001'])
        self.assertEqual(value['progress']['Accepted'], 1)
        self.assertEqual(value['model']['sha256'], 'abc')
        self.assertEqual(value['cases'][0]['score'], 7.25)

    def test_mismatched_results_keep_detector_score_and_fail_closed(self):
        self.result(rank=9, running_score=99)
        case = load_workspace(self.run)['cases'][0]
        self.assertEqual((case['rank'], case['score']), (1, 7.25))
        self.assertEqual(case['status'], 'Fallback')
        self.assertEqual(case['cited'], [])

    def test_modified_prepared_packs_are_rejected(self):
        (self.run / 'preparation.json').write_text(json.dumps(dict(packs_sha256='wrong')))
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            load_workspace(self.run)

    def test_missing_prerequisites_never_launch_the_runner(self):
        with patch('dashboard_pipeline.subprocess.call') as launch:
            result = pipeline_main(['prepare', '--cache', str(self.run / 'empty'), '--day', '2010-08-02'])
        self.assertEqual(result, 2)
        launch.assert_not_called()

    def test_readiness_rejects_partial_csv_exports(self):
        for name in ('daily', 'pc_pairs', 'dom_pairs'):
            folder = self.run / 'r4.2_csv' / name
            folder.mkdir(parents=True)
            (folder / 'part-000.csv').write_text('user,day\n001,2010-08-02\n')
        with patch.dict('os.environ', OUTOFROLE_TABLE_FORMAT='csv'):
            status = readiness(self.run)
        self.assertFalse(status['scoring_ready'])
        self.assertTrue(all(not t['complete'] for t in status['tables']))

    def test_granite_command_reuses_packs_and_keeps_structured_diagnostic(self):
        (self.run / 'preparation.json').write_text('{}')
        with patch('dashboard_pipeline.readiness', return_value={'granite_blockers': []}), \
                patch('dashboard_pipeline.subprocess.call', return_value=0) as launch:
            result = pipeline_main(['infer', '--run-dir', str(self.run), '--model', str(self.run / 'test.gguf'),
                                    '--model-mode', 'completion', '--max-cases', '1'])
        self.assertEqual(result, 0)
        command = launch.call_args.args[0]
        self.assertIn('infer', command)
        self.assertNotIn('prepare', command)
        self.assertIn('--structured-output', command)
        self.assertEqual(command[command.index('--max-cases') + 1], '1')
        self.assertEqual(command[command.index('--model-mode') + 1], 'completion')

    def test_raw_preview_is_bounded_and_never_claims_inference(self):
        (self.run / 'logon.csv').write_text(
            'id,date,user,pc,activity\n'
            'r1,01/02/2010 08:00:00,001,PC-1,Logon\n'
            'r2,01/02/2010 09:00:00,001,PC-1,Logoff\n'
            'r3,01/03/2010 08:00:00,002,PC-2,Logon\n')
        preview, days = load_activity_preview(self.run, limit=2)
        self.assertEqual(days, ['2010-01-02'])
        self.assertEqual(preview['metrics']['events'], 2)
        self.assertEqual(preview['mode'], 'activity')
        self.assertEqual(preview['cases'][0]['person'], '001')
        self.assertIsNone(preview['cases'][0]['score'])
        self.assertEqual(preview['cases'][0]['status'], 'Not inferred')

    def test_dashboard_assets_are_utf8_without_mojibake(self):
        root = Path(__file__).resolve().parents[1] / 'web/dashboard'
        for name in ('app.js', 'index.html', 'style.css'):
            text = (root / name).read_text(encoding='utf-8')
            for fragment in ('\u00c2', '\u00c3', '\u00e2\u20ac', '\ufffd'):
                self.assertNotIn(fragment, text, name)

    def test_explicit_runner_source_does_not_fall_back_to_raw(self):
        (self.run / 'logon.csv').write_text(
            'id,date,user,pc,activity\n'
            'r1,01/02/2010 08:00:00,001,PC-1,Logon\n')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.run_dir = server.attempt = None
        server.runs = self.run / 'no-runs'
        server.cache = self.run / 'no-cache'
        server.raw = self.run
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}/api/workspace'
        try:
            with urlopen(base) as response:
                self.assertEqual(json.load(response)['workspace']['mode'], 'activity')
            with urlopen(base + '?source=runner') as response:
                data = json.load(response)
                self.assertIsNone(data['workspace'])
                self.assertEqual(data['runs'], [])
            with urlopen(base + '?source=activity') as response:
                self.assertEqual(json.load(response)['workspace']['mode'], 'activity')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
