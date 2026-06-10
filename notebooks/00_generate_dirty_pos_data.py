"""
SmartRetail POS — Data Generator
Generates 7 entity Parquet files with intentional dirty data.
Output: data/landing/entity={name}/load_date={date}/{name}.parquet
"""
import os
import json
import random
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

fake = Faker()
random.seed(42)
Faker.seed(42)

PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
LANDING      = PROJECT_ROOT / "data" / "landing"
CONFIGS      = PROJECT_ROOT / "data" / "configs"

with open(CONFIGS / "generation_config.json") as f:
    cfg = json.load(f)
with open(CONFIGS / "dirty_data_rules.json") as f:
    dirty = json.load(f)

RUN_DATE = datetime.utcnow().strftime("%Y-%m-%d")


def maybe_null(value, rate):
    return None if random.random() < rate else value


def save_entity(df: pd.DataFrame, entity_name: str) -> pd.DataFrame:
    path = LANDING / f"entity={entity_name}" / f"load_date={RUN_DATE}"
    path.mkdir(parents=True, exist_ok=True)
    out  = path / f"{entity_name}.parquet"
    df.to_parquet(out, index=False)
    print(f"  [OK] {entity_name:<25}  {len(df):>7,} rows  →  {out.relative_to(PROJECT_ROOT)}")
    return df


def gen_stores() -> list:
    rows = []
    for i in range(1, cfg["num_stores"] + 1):
        rows.append({
            "store_id":    f"STR{i:04d}",
            "store_name":  fake.company(),
            "region":      random.choice(cfg["regions"]),
            "format":      random.choice(cfg["store_formats"]),
            "city":        fake.city(),
            "country":     fake.country_code(),
            "opened_date": str(fake.date_between(start_date="-10y", end_date="-1y")),
        })
    df = pd.DataFrame(rows)
    dupes = df.sample(frac=dirty["duplicate_rate"], random_state=1)
    df    = pd.concat([df, dupes], ignore_index=True)
    save_entity(df, "stores")
    return [r["store_id"] for r in rows]


def gen_products() -> list:
    rows = []
    for i in range(1, cfg["num_products"] + 1):
        rows.append({
            "product_id":   f"PRD{i:05d}",
            "product_name": fake.bs().title(),
            "category":     random.choice(cfg["product_categories"]),
            "unit_price":   round(random.uniform(1.99, 499.99), 2),
            "cost_price":   round(random.uniform(0.50, 200.00), 2),
            "supplier_id":  f"SUP{random.randint(1, 50):03d}",
            "active":       maybe_null(random.choice([True, False, True, True, True]),
                                       dirty["null_injection_rate"]),
        })
    df = pd.DataFrame(rows)
    save_entity(df, "products")
    return [r["product_id"] for r in rows]


def gen_customers() -> list:
    rows = []
    for i in range(1, cfg["num_customers"] + 1):
        rows.append({
            "customer_id":    f"CUST{i:06d}",
            "first_name":     maybe_null(fake.first_name(), dirty["null_injection_rate"]),
            "last_name":      fake.last_name(),
            "email":          fake.email(),
            "loyalty_tier":   random.choice(["BRONZE", "SILVER", "GOLD", "PLATINUM", None]),
            "registered_date": str(fake.date_between(start_date="-5y", end_date="today")),
        })
    df = pd.DataFrame(rows)
    save_entity(df, "customers")
    return [r["customer_id"] for r in rows]


def gen_transactions(store_ids: list, customer_ids: list) -> list:
    rows = []
    for i in range(cfg["transactions_per_day"]):
        txn_id = f"TXN{RUN_DATE.replace('-','')}{i:06d}"
        if random.random() < dirty["future_date_rate"]:
            sale_dt = str(datetime.utcnow() + timedelta(days=random.randint(1, 30)))
        else:
            sale_dt = str(datetime.utcnow() - timedelta(hours=random.randint(0, 23),
                                                         minutes=random.randint(0, 59)))
        store_id = (f"INVALID_{i}" if random.random() < dirty["invalid_store_id_rate"]
                    else random.choice(store_ids))
        rows.append({
            "transaction_id": txn_id,
            "store_id":       store_id,
            "customer_id":    maybe_null(random.choice(customer_ids), 0.10),
            "sale_datetime":  sale_dt,
            "payment_method": random.choice(["CARD", "CASH", "DIGITAL", "VOUCHER"]),
            "total_amount":   None,
            "currency":       cfg["currency"],
        })
    df = pd.DataFrame(rows)
    save_entity(df, "transaction_headers")
    return [r["transaction_id"] for r in rows]


def gen_lines(txn_ids: list, product_ids: list):
    rows = []
    lid  = 1
    for txn_id in txn_ids:
        n = random.randint(cfg["lines_per_transaction_min"],
                           cfg["lines_per_transaction_max"])
        for _ in range(n):
            qty   = (random.randint(-5, 0) if random.random() < dirty["negative_quantity_rate"]
                     else random.randint(1, 10))
            price = (round(random.uniform(-50, 0), 2) if random.random() < dirty["invalid_amount_rate"]
                     else round(random.uniform(1.99, 499.99), 2))
            disc  = round(random.uniform(0, 0.5), 2)
            rows.append({
                "line_id":        f"LN{lid:08d}",
                "transaction_id": txn_id,
                "product_id":     random.choice(product_ids),
                "quantity":       qty,
                "unit_price":     price,
                "discount_pct":   disc,
                "line_total":     round(qty * price * (1 - disc), 2),
            })
            lid += 1
    df = pd.DataFrame(rows)
    save_entity(df, "transaction_lines")


def gen_inventory(store_ids: list, product_ids: list):
    rows = []
    for store_id in store_ids:
        for product_id in random.sample(product_ids, k=min(50, len(product_ids))):
            rows.append({
                "inventory_id":  f"INV{fake.uuid4()[:8].upper()}",
                "store_id":      store_id,
                "product_id":    product_id,
                "stock_on_hand": maybe_null(random.randint(0, 500),
                                            dirty["null_injection_rate"]),
                "reorder_point": random.randint(10, 50),
                "last_updated":  str(datetime.utcnow()),
            })
    df = pd.DataFrame(rows)
    save_entity(df, "inventory")


def gen_promotions():
    rows = []
    for i in range(1, 51):
        rows.append({
            "promotion_id":   f"PROMO{i:03d}",
            "promotion_name": fake.catch_phrase(),
            "discount_type":  random.choice(["PERCENT", "FIXED", "BOGO"]),
            "discount_value": round(random.uniform(0.05, 0.50), 2),
            "start_date":     str(fake.date_between(start_date="-30d", end_date="today")),
            "end_date":       str(fake.date_between(start_date="today", end_date="+30d")),
            "active":         True,
        })
    df = pd.DataFrame(rows)
    save_entity(df, "promotions")


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  SmartRetail POS Generator")
    print(f"  Run date : {RUN_DATE}")
    print(f"{'='*60}\n")

    store_ids    = gen_stores()
    product_ids  = gen_products()
    customer_ids = gen_customers()
    txn_ids      = gen_transactions(store_ids, customer_ids)
    gen_lines(txn_ids, product_ids)
    gen_inventory(store_ids, product_ids)
    gen_promotions()

    print(f"\n{'='*60}")
    print(f"  Generation complete.")
    print(f"  Next: upload to Databricks DBFS")
    print(f"{'='*60}\n")

