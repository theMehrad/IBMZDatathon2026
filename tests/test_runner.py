import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))

import pandas as pd
import pytest


def test_csv_cache_reads_all_parts_and_rejects_partial_export(tmp_path):
    from table_io import read_table
    work = tmp_path / 'r4.2'
    folder = tmp_path / 'r4.2_csv' / 'daily'
    folder.mkdir(parents=True)
    (folder / 'part-001.csv').write_text('user,day,n_usb\nB,2010-06-02,2\n')
    (folder / 'part-000.csv').write_text('user,day,n_usb\nA,2010-06-01,1\n')
    with pytest.raises(ValueError, match='Incomplete CSV'):
        read_table(work, 'daily')
    (folder / '_SUCCESS').touch()
    result = read_table(work, 'daily')
    assert result.user.tolist() == ['A', 'B']
    assert result.n_usb.tolist() == [1, 2]


def test_review_export_preserves_reference_list_and_uses_past_only_evidence():
    import ast
    import numpy as np
    from runner import export_review

    source = (Path(__file__).resolve().parents[1] / 'code/outofrole_minimal.py').read_text()
    nodes = ast.parse(source).body
    # Use the original detector as an oracle, not a second test implementation.
    funcs = [n for n in nodes if isinstance(n, ast.FunctionDef) and n.name in ('daily_lists', 'case_items')]
    users = np.array([f'RAW-{i:03d}' for i in range(25)])
    scores = np.zeros((25, 3))
    scores[:, 0] = 1
    scores[:5, 1] = 4
    scores[24, 2] = 100  # Future spike must not affect day 2's list or scores.
    cut = pd.Timestamp('2010-06-01')
    rows = pd.DataFrame([
        dict(kind='dom', item='example.org', day=cut, new=True, share=0.001, score=2.999),
        dict(kind='dom', item='future.example', day=cut + pd.Timedelta(days=2), new=True, share=0., score=3.),
    ])
    ns = dict(np=np, pd=pd, K=20, HALF_LIFE=7, T=3, CUT=cut, users=users,
              pct_score=scores, CASE={u: rows for u in users})
    exec(compile(ast.Module(body=funcs, type_ignores=[]), '<reference>', 'exec'), ns)
    ns['on_pct'] = ns['daily_lists'](scores, decay=True)
    review = export_review(ns, '2010-06-02', '4.2')
    assert len(review['cases']) == 20
    expected_people = {f'U-{i+1:04d}' for i in np.flatnonzero(ns['on_pct'][:, 1])}
    assert {r['pack']['person'] for r in review['cases']} == expected_people
    assert [r['rank'] for r in review['cases']] == list(range(1, 21))
    assert review['cases'][0]['running_score'] >= review['cases'][-1]['running_score']
    assert all(f['date'] <= '2010-06-02' for r in review['cases'] for f in r['pack']['facts'])
    assert 'RAW-' not in __import__('json').dumps(review)
    with pytest.raises(ValueError, match='replay'):
        export_review(ns, '2010-05-31', '4.2')


@pytest.mark.parametrize('reply,finish,error,accepted', [
    ('{"label":"possible data leak","facts":["E1"]}', 'stop', None, True),
    ('{"label":"possible data leak","facts":["E9"]}', 'stop', None, False),
    ('not json', 'stop', None, False),
    ('{"label":"possible data leak","facts":["E1"]}', 'length', None, False),
    (None, None, 'inference timed out', False),
])
def test_inference_outcomes_preserve_rank_and_render_safe_fallback(reply, finish, error, accepted):
    from runner import evaluate_reply
    case = dict(rank=7, running_score=12.5, pack=dict(person='U-0007', strength='strong', facts=[
        dict(id='E1', what='visited website', item='example.org', date='2010-06-01',
             new_to_person=True, staff_share=0.001),
    ]))
    result = evaluate_reply(case, reply, finish, error)
    assert result['rank'] == 7 and result['person'] == 'U-0007'
    assert result['accepted'] is accepted
    assert 'example.org' in result['rendered'] and '[E1]' in result['rendered']
    if not accepted:
        assert result['rendered'].startswith('U-0007: needs review')
        assert result['problems']


def test_worker_timeout_also_bounds_partial_lines(tmp_path):
    import subprocess
    from runner import JsonWorker
    with (tmp_path / 'worker.log').open('w') as log:
        client = JsonWorker([sys.executable, '-u', '-c',
            'import sys,time; sys.stdout.write("partial"); sys.stdout.flush(); time.sleep(10)'], log)
        try:
            with pytest.raises(TimeoutError):
                client.receive(0.2)
        finally:
            client.close()
        assert client.process.poll() is not None
