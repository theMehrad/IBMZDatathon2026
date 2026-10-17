"""IBM Z helper: copy the three Spark tables to plain CSV, for machines where pandas cannot read Parquet.

    python tables_to_csv.py 4.2      (or 5.2), after build_tables.py

pyarrow has no IBM Z (s390x) build on PyPI, so pandas has no Parquet reader there. Spark has its own: this reads
data/cache/r{rel}/ and writes data/cache_csv/r{rel}/, which outofrole_minimal.py reads when pyarrow is missing.
"""
import os, sys
from pathlib import Path
from pyspark.sql import SparkSession

REL = sys.argv[1]
BASE = Path(__file__).resolve().parent.parent
spark = (SparkSession.builder.master("local[*]").appName("outofrole-csv")
         .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "4g")).config("spark.ui.showConsoleProgress", "false").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
for name in ("daily", "pc_pairs", "dom_pairs"):
    df = spark.read.parquet(str(BASE / "data" / "cache" / f"r{REL}" / name))
    df.write.mode("overwrite").option("header", True).csv(str(BASE / "data" / "cache_csv" / f"r{REL}" / name))
    print(f"r{REL} {name}: {df.count():,} rows written as CSV")
spark.stop()
