"""Step 0: turn the raw CERT logs into the three tables everything else reads (PySpark).

    python build_tables.py 4.2      (or 5.2)

Reads data/r{rel}/r{rel}/{logon,device,file,http}.csv and writes, under data/cache/r{rel}/:
  daily      one row per person per day: logons, after-hours logons, computers used, USB connects,
             after-hours USB, files to removable media, after-hours files, web visits, after-hours web
  pc_pairs   (person, day, computer) for every logon
  dom_pairs  (person, day, website domain, visits)
Same code as Step 1 of evidence/Study_Notebook.ipynb. On LinuxONE: install Java 17 and PySpark first;
there is no pyarrow for s390x, so this script avoids pandas UDFs; then run tables_to_csv.py for pandas.
On a small VM set SPARK_DRIVER_MEMORY=4g (default 8g).
"""
import os, sys
from pathlib import Path
from pyspark.sql import SparkSession, functions as F

REL = sys.argv[1]
BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / f"r{REL}" / f"r{REL}"
OUT = Path(os.environ.get("OUTOFROLE_CACHE", BASE / "data" / "cache")) / f"r{REL}"   # override the output folder if needed
OUT.mkdir(parents=True, exist_ok=True)

spark = (SparkSession.builder.master("local[*]").appName("outofrole-tables")
         .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "8g")).config("spark.sql.shuffle.partitions", "64").config("spark.ui.showConsoleProgress", "false").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

def load(name, cols):
    df = spark.read.csv(str(RAW / f"{name}.csv"), header=True).select(*cols)
    ts = F.to_timestamp("date", "MM/dd/yyyy HH:mm:ss")
    return df.withColumn("ts", ts).withColumn("day", F.to_date("ts")).withColumn("hour", F.hour("ts")).drop("date")

logon = load("logon", ["date", "user", "pc", "activity"]).filter(F.col("activity") == "Logon")
device = load("device", ["date", "user", "pc", "activity"]).filter(F.col("activity") == "Connect")
if "to_removable_media" in open(RAW / "file.csv").readline():                    # r5.2 marks USB copies; r4.2 does not
    files = load("file", ["date", "user", "pc", "to_removable_media"]).filter(F.col("to_removable_media") == "True").drop("to_removable_media")
else:
    files = load("file", ["date", "user", "pc"])
http = (load("http", ["date", "user", "pc", "url"])
        .withColumn("domain", F.lower(F.regexp_extract("url", r"^https?://(?:www\.)?([^/:]+)", 1))).drop("url"))

ah = lambda: ((F.col("hour") < 7) | (F.col("hour") >= 19)).cast("int")           # after hours: before 7:00 or from 19:00
d1 = logon.groupBy("user", "day").agg(F.count("*").alias("n_logon"), F.sum(ah()).alias("n_logon_ah"), F.countDistinct("pc").alias("n_pcs"))
d2 = device.groupBy("user", "day").agg(F.count("*").alias("n_usb"), F.sum(ah()).alias("n_usb_ah"))
d3 = files.groupBy("user", "day").agg(F.count("*").alias("n_file"), F.sum(ah()).alias("n_file_ah"))
d4 = http.groupBy("user", "day").agg(F.count("*").alias("n_http"), F.sum(ah()).alias("n_http_ah"))
(d1.join(d2, ["user", "day"], "full").join(d3, ["user", "day"], "full").join(d4, ["user", "day"], "full")
   .fillna(0).write.mode("overwrite").parquet(str(OUT / "daily")))
logon.select("user", "day", "pc").distinct().write.mode("overwrite").parquet(str(OUT / "pc_pairs"))
(http.filter(F.col("domain") != "").groupBy("user", "day", "domain").agg(F.count("*").alias("n"))
     .write.mode("overwrite").parquet(str(OUT / "dom_pairs")))
print(f"r{REL}: tables written to {OUT}")
spark.stop()
