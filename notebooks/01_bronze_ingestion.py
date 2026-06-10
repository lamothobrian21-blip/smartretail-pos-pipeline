from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit
import datetime

spark = SparkSession.builder.getOrCreate()

RUN_DATE    = datetime.date.today().strftime("%Y-%m-%d")
LANDING_DIR = "/Volumes/smartretail/bronze/landing"

ENTITIES = [
    "stores", "products", "customers",
    "transaction_headers", "transaction_lines",
    "inventory", "promotions"
]

print(f"\n{'='*60}")
print(f"  Bronze Ingestion — {RUN_DATE}")
print(f"{'='*60}\n")

results = []

for entity in ENTITIES:
    parquet_path = f"{LANDING_DIR}/{entity}.parquet"
    print(f"  Reading: {parquet_path}")

    try:
        df_raw = spark.read.format("parquet").load(parquet_path)
        raw_count = df_raw.count()

        df_bronze = (df_raw
                     .withColumn("_load_date",          lit(RUN_DATE))
                     .withColumn("_source_system",      lit("synthetic_pos"))
                     .withColumn("_bronze_ingested_at", current_timestamp()))

        (df_bronze.write
         .format("delta")
         .mode("append")
         .option("mergeSchema", "true")
         .saveAsTable(f"smartretail.bronze.{entity}"))

        written = spark.sql(
            f"SELECT COUNT(*) AS n FROM smartretail.bronze.{entity} "
            f"WHERE _load_date = '{RUN_DATE}'"
        ).collect()[0].n

        print(f"    Raw: {raw_count:,}  |  Written to bronze: {written:,}")
        results.append({"entity": entity, "status": "SUCCESS", "rows": written})

    except Exception as e:
        print(f"    ERROR: {e}")
        results.append({"entity": entity, "status": "FAILED", "error": str(e)})

print(f"\n{'='*60}")
print(f"  Bronze Summary — {RUN_DATE}")
for r in results:
    if r["status"] == "SUCCESS":
        print(f"  [OK]   smartretail.bronze.{r['entity']:<22}  {r['rows']:>8,} rows")
    else:
        print(f"  [FAIL] {r['entity']}  →  {r.get('error')}")
print(f"{'='*60}\n")

failed = [r for r in results if r["status"] == "FAILED"]
if failed:
    raise Exception(f"Bronze failed for: {[r['entity'] for r in failed]}")