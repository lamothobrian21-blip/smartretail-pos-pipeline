"""
SmartRetail — Silver Cleaning
Reads smartretail.bronze.* → writes smartretail.silver.*
Rejected records → smartretail.audit.rejected_records

Cleaning rules:
  stores             : deduplicate on store_id, non-null region
  products           : non-null product_id, unit_price > 0
  customers          : deduplicate on customer_id, non-null last_name
  transaction_headers: non-null txn_id, valid store_id, no future dates
  transaction_lines  : quantity > 0, unit_price > 0, non-null line_id
  inventory          : non-null stock_on_hand >= 0, valid FK
  promotions         : end_date >= start_date, discount > 0
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, current_timestamp, lit, to_date, to_timestamp, row_number
)
from pyspark.sql.window import Window
import datetime

spark = SparkSession.builder.getOrCreate()

RUN_DATE = datetime.date.today().strftime("%Y-%m-%d")

print(f"\n{'='*60}")
print(f"  Silver Cleaning — {RUN_DATE}")
print(f"{'='*60}\n")

# Reference sets for FK validation
valid_stores = [
    r.store_id for r in
    spark.sql("SELECT DISTINCT store_id FROM smartretail.bronze.stores").collect()
]
valid_products = [
    r.product_id for r in
    spark.sql("SELECT DISTINCT product_id FROM smartretail.bronze.products").collect()
]


def write_silver_and_audit(df_clean, df_reject, entity: str):
    df_clean = (df_clean
                .withColumn("_silver_cleaned_at", current_timestamp())
                .withColumn("_run_date",          lit(RUN_DATE)))
    df_reject = (df_reject
                 .withColumn("entity",       lit(entity))
                 .withColumn("_run_date",    lit(RUN_DATE))
                 .withColumn("_rejected_at", current_timestamp()))

    (df_clean.write.format("delta").mode("append")
     .option("mergeSchema", "true")
     .saveAsTable(f"smartretail.silver.{entity}"))

    (df_reject.write.format("delta").mode("append")
     .option("mergeSchema", "true")
     .saveAsTable("smartretail.audit.rejected_records"))

    c   = df_clean.count()
    r   = df_reject.count()
    pct = round(r / max(c + r, 1) * 100, 1)
    print(f"  {entity:<25}  clean: {c:>7,}  rejected: {r:>5,}  ({pct}%)")
    return c, r


# 1. Stores
raw     = spark.sql(f"SELECT * FROM smartretail.bronze.stores WHERE _load_date='{RUN_DATE}'")
w       = Window.partitionBy("store_id").orderBy("_bronze_ingested_at")
deduped = raw.withColumn("_rn", row_number().over(w)).filter(col("_rn") == 1).drop("_rn")
clean   = deduped.filter(col("store_id").isNotNull() & col("region").isNotNull())
reject  = (raw.filter(col("store_id").isNull() | col("region").isNull())
           .withColumn("rejection_reason", lit("null_store_id_or_region")))
write_silver_and_audit(clean, reject, "stores")

# 2. Products
raw    = spark.sql(f"SELECT * FROM smartretail.bronze.products WHERE _load_date='{RUN_DATE}'")
clean  = raw.filter(col("product_id").isNotNull() & (col("unit_price") > 0) & (col("cost_price") > 0))
reject = (raw.filter(col("product_id").isNull() | (col("unit_price") <= 0) | (col("cost_price") <= 0))
          .withColumn("rejection_reason", lit("null_product_id_or_invalid_price")))
write_silver_and_audit(clean, reject, "products")

# 3. Customers
raw     = spark.sql(f"SELECT * FROM smartretail.bronze.customers WHERE _load_date='{RUN_DATE}'")
w       = Window.partitionBy("customer_id").orderBy("_bronze_ingested_at")
deduped = raw.withColumn("_rn", row_number().over(w)).filter(col("_rn") == 1).drop("_rn")
clean   = deduped.filter(col("customer_id").isNotNull() & col("last_name").isNotNull())
reject  = (raw.filter(col("customer_id").isNull() | col("last_name").isNull())
           .withColumn("rejection_reason", lit("null_customer_id_or_last_name")))
write_silver_and_audit(clean, reject, "customers")

# 4. Transaction Headers
raw = spark.sql(f"SELECT * FROM smartretail.bronze.transaction_headers WHERE _load_date='{RUN_DATE}'")
clean = (raw
         .filter(col("transaction_id").isNotNull())
         .filter(col("store_id").isin(valid_stores))
         .filter(to_timestamp(col("sale_datetime")) <= current_timestamp()))
r_null   = raw.filter(col("transaction_id").isNull()).withColumn("rejection_reason", lit("null_transaction_id"))
r_store  = raw.filter(~col("store_id").isin(valid_stores)).withColumn("rejection_reason", lit("invalid_store_id"))
r_future = raw.filter(to_timestamp(col("sale_datetime")) > current_timestamp()).withColumn("rejection_reason", lit("future_sale_datetime"))
reject   = r_null.unionByName(r_store, allowMissingColumns=True).unionByName(r_future, allowMissingColumns=True)
write_silver_and_audit(clean, reject, "transaction_headers")

# 5. Transaction Lines
raw    = spark.sql(f"SELECT * FROM smartretail.bronze.transaction_lines WHERE _load_date='{RUN_DATE}'")
clean  = raw.filter(col("line_id").isNotNull() & col("transaction_id").isNotNull() & (col("quantity") > 0) & (col("unit_price") > 0))
reject = (raw.filter(col("line_id").isNull() | col("transaction_id").isNull() | (col("quantity") <= 0) | (col("unit_price") <= 0))
          .withColumn("rejection_reason", lit("null_key_or_negative_qty_or_price")))
write_silver_and_audit(clean, reject, "transaction_lines")

# 6. Inventory
raw    = spark.sql(f"SELECT * FROM smartretail.bronze.inventory WHERE _load_date='{RUN_DATE}'")
clean  = (raw
          .filter(col("inventory_id").isNotNull())
          .filter(col("store_id").isin(valid_stores))
          .filter(col("product_id").isin(valid_products))
          .filter(col("stock_on_hand").isNotNull() & (col("stock_on_hand") >= 0)))
reject = (raw.filter(
              col("inventory_id").isNull() |
              ~col("store_id").isin(valid_stores) |
              ~col("product_id").isin(valid_products) |
              col("stock_on_hand").isNull() |
              (col("stock_on_hand") < 0))
          .withColumn("rejection_reason", lit("null_key_or_invalid_fk_or_negative_stock")))
write_silver_and_audit(clean, reject, "inventory")

# 7. Promotions
raw    = spark.sql(f"SELECT * FROM smartretail.bronze.promotions WHERE _load_date='{RUN_DATE}'")
clean  = (raw
          .filter(col("promotion_id").isNotNull())
          .filter(col("discount_value") > 0)
          .filter(to_date(col("end_date")) >= to_date(col("start_date"))))
reject = (raw.filter(
              col("promotion_id").isNull() |
              (col("discount_value") <= 0) |
              (to_date(col("end_date")) < to_date(col("start_date"))))
          .withColumn("rejection_reason", lit("null_id_or_invalid_dates_or_discount")))
write_silver_and_audit(clean, reject, "promotions")

print(f"\n{'='*60}")
print(f"  Silver complete. Rejected records in smartretail.audit.rejected_records")
print(f"  Next: run dbt build from your local machine")
print(f"{'='*60}\n")