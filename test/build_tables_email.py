"""Nguyen's copy of code/build_tables.py, with email counts added. The team's script is not changed.

    python code/nguyen/build_tables_email.py 4.2      (or 5.2)

Same as build_tables.py, plus it reads data/r{rel}/r{rel}/email.csv and adds four daily columns:
  n_email_out       sent emails with at least one recipient outside the company
  n_email_out_ah    the same, after hours (before 7:00 or from 19:00)
  n_email_out_att   sent outside emails that carry at least one attachment
  n_email_rcpt      total recipients (to + cc + bcc) on all sent emails, which catches mass emails

Writes to data/cache_nguyen/r{rel}/ (not data/cache/), so the team's tables are never overwritten.
Override with OUTOFROLE_CACHE=/some/folder.
"""
import os, sys
from pathlib import Path
from pyspark.sql import SparkSession, functions as F

REL = sys.argv[1]
BASE = Path(os.environ.get("OUTOFROLE_BASE", Path(__file__).resolve().parents[1]))   # repo root
RAW = BASE / "data" / f"r{REL}" / f"r{REL}"
OUT = Path(os.environ.get("OUTOFROLE_CACHE", BASE / "data" / "cache_nguyen")) / f"r{REL}"
OUT.mkdir(parents=True, exist_ok=True)
COMPANY = "@dtaa.com"     # CERT's company domain; the check printed below confirms it

spark = (SparkSession.builder.master("local[*]").appName("outofrole-tables-nguyen")
         .config("spark.driver.memory", "8g").config("spark.sql.shuffle.partitions", "64").config("spark.ui.showConsoleProgress", "false").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

def load(name, cols):
    df = spark.read.csv(str(RAW / f"{name}.csv"), header=True).select(*cols)
    ts = F.to_timestamp("date", "MM/dd/yyyy HH:mm:ss")
    return df.withColumn("ts", ts).withColumn("day", F.to_date("ts")).withColumn("hour", F.hour("ts")).drop("date")

# ---------------------------------------------------------------- unchanged from build_tables.py
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

# ---------------------------------------------------------------- NEW: email
header = open(RAW / "email.csv").readline().strip().split(",")
att_col = "attachments" if "attachments" in header else header[header.index("size") + 1]
cols = ["date", "user", "to", "cc", "bcc", att_col] + (["activity"] if "activity" in header else [])
email = load("email", cols).withColumnRenamed(att_col, "att")
if "activity" in header:                       # r5.2 logs Send and View; keep only emails the person sent
    email = email.filter(F.col("activity") == "Send").drop("activity")
# r4.2 has no Send/View column: every row is an email the person sent.

rcpt = F.expr("filter(split(lower(concat_ws(';', `to`, cc, bcc)), ';'), x -> trim(x) != '')")
email = email.withColumn("rcpt", rcpt)
email = (email.withColumn("n_rcpt", F.size("rcpt"))
              .withColumn("outside", F.expr(f"exists(rcpt, x -> NOT trim(x) LIKE '%{COMPANY}')").cast("int"))
              .withColumn("has_att", F.when(F.col("att").isNull() | (F.trim("att") == "") | (F.trim("att") == "0"), 0).otherwise(1)))
# r4.2 stores an attachment COUNT ("0", "2"); r5.2 stores attachment NAMES separated by ";". Both become has_att 0/1.

d5 = email.groupBy("user", "day").agg(
    F.sum("outside").alias("n_email_out"),
    F.sum(F.col("outside") * ah()).alias("n_email_out_ah"),
    F.sum(F.col("outside") * F.col("has_att")).alias("n_email_out_att"),
    F.sum("n_rcpt").alias("n_email_rcpt"))

# sanity check: most recipients should be on the company domain; if this share is near 0, COMPANY is wrong
chk = email.select(F.explode("rcpt").alias("r")).agg(F.mean(F.trim("r").like(f"%{COMPANY}").cast("int")).alias("share")).first()
print(f"r{REL}: share of email recipients on {COMPANY}: {chk['share']:.1%}  (attachment column used: '{att_col}')")

# ---------------------------------------------------------------- write (d5 joined in; pc_pairs and dom_pairs unchanged)
(d1.join(d2, ["user", "day"], "full").join(d3, ["user", "day"], "full").join(d4, ["user", "day"], "full")
   .join(d5, ["user", "day"], "full")
   .fillna(0).write.mode("overwrite").parquet(str(OUT / "daily")))
logon.select("user", "day", "pc").distinct().write.mode("overwrite").parquet(str(OUT / "pc_pairs"))
(http.filter(F.col("domain") != "").groupBy("user", "day", "domain").agg(F.count("*").alias("n"))
     .write.mode("overwrite").parquet(str(OUT / "dom_pairs")))
print(f"r{REL}: tables written to {OUT}")
spark.stop()
