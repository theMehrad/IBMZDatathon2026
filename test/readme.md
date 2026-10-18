# test/ — Nguyen's additions to OutOfRole

Copies of the team's pipeline with two extra inputs for the daily list. The team's scripts in `code/` are unchanged.

## Run the best setting

```bash
conda activate outofrole
python test/build_tables_email.py 5.2        # once per release: raw CSVs -> tables in data/cache_nguyen/
bash test/run.sh 5.2                    # final setting + export (use 4.2 for the development release)
```

`run_best.sh` runs:

```bash
python test/outofrole_email.py 5.2 --feats=n_new_site,n_boss_pc --w=5 --export
```

## What changed

| Input | Counts per person per day | Points when unusual |
|---|---|---|
| `n_new_site` | Visits to websites nobody in the company visited during training | 5 |
| `n_boss_pc` | Logons to one's own supervisor's main computer (from LDAP) | 5 |
| original 9 activities | logons, USB, files, web, after-hours versions, computers used | 1 |

## Results

| | r4.2 before | r4.2 after | r5.2 before | r5.2 after |
|---|---|---|---|---|
| Insiders caught in time | 59/70 | **63/70** | 80/99 | **83/99** |
| Sysadmins | 4/10 | **8/10** | 2/10 | **6/10** |
| Normal staff ever listed | 230 | **219** | 291 | **279** |

Settings were chosen on r4.2 and run once, unchanged, on r5.2. Email inputs were tested on r4.2 and dropped (more false alarms, no extra catches).

## Files

| File | Purpose |
|---|---|
| `build_tables_email.py` | Spark: raw logs -> daily, computer and website tables |
| `outofrole_email.py` | All models + grading report. Options: `--no-email`, `--feats=`, `--w=`, `--export`, `--why-s3` |
| `compare_features.py` | Compares settings side by side, e.g. `python test/compare_features.py 4.2 n_new_site,n_boss_pc@5` |
| `run_best.sh` | Runs the final setting |

## Output

- Report printed to the screen (insiders caught, by attack type, normal staff listed, ...)
- With `--export`: `data/exports_nguyen/r{release}_cases.jsonl`, one record per person per day on the list (why flagged + top 5 evidence facts), label-free, for the Granite step. **Never commit it**: it is derived from CERT data.

## Requirements

Data in `data/r4.2/r4.2/`, `data/r5.2/r5.2/` and `data/answers/answers/`. Python with `pyspark pandas numpy pyarrow`, and Java 17:

```bash
conda create -n outofrole -c conda-forge python=3.11 pyspark pyarrow pandas numpy openjdk=17 -y
```