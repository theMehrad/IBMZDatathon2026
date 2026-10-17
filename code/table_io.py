"""Portable reads of the existing Spark tables; no changes to feature values."""
import os
from pathlib import Path
from typing import Any
from collections.abc import Hashable
import pandas as pd


def read_table(work, name):
    mode = os.environ.get('OUTOFROLE_TABLE_FORMAT', 'auto')
    if mode not in ('auto', 'csv', 'parquet'):
        raise ValueError('OUTOFROLE_TABLE_FORMAT must be auto, csv or parquet')
    folder = Path(str(work) + '_csv') / name
    if mode == 'csv' or (mode == 'auto' and folder.exists()):
        parts = sorted(folder.glob('part-*.csv'))
        if not (folder / '_SUCCESS').is_file() or not parts:
            raise ValueError(f'Incomplete CSV export: {folder}')
        print(f'Loading {name} from CSV', flush=True)
        identifiers: dict[Hashable, Any] = {column: 'str' for column in ('user', 'pc', 'domain', 'day')}
        return pd.concat([pd.read_csv(p, dtype=identifiers, keep_default_na=False)
                          for p in parts], ignore_index=True)
    return pd.read_parquet(Path(work) / name)
