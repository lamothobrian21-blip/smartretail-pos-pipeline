# SmartRetail POS Intelligence Pipeline

An end-to-end data engineering pipeline that processes synthetic retail point-of-sale data through a Bronze → Silver → Gold medallion architecture using Databricks Free Edition and dbt Core.

## Stack
- **Python** — synthetic data generation with Faker
- **Databricks Free Edition** — Bronze ingestion and Silver cleaning (PySpark + Delta Lake)
- **dbt Core** — Gold analytical models with automated data quality tests
- **Delta Lake** — storage format throughout
- **Unity Catalog** — data governance and table management

## Architecture
Python (Faker) → Local Parquet → Databricks Volume
↓
Bronze Layer (raw Delta tables)
↓
Silver Layer (cleaned + validated)
↓
dbt Core → Gold Layer (6 analytical models)

## Gold Models

| Model | Description |
|---|---|
| `gold_sales_daily` | Daily sales by store, product, and payment method |
| `gold_store_performance` | Store-level KPIs — revenue, transactions, basket size |
| `gold_product_performance` | Product revenue, margin, and discount analysis |
| `gold_customer_lifetime_value` | Customer segmentation by spend and purchase frequency |
| `gold_inventory_risk_daily` | Stockout risk classification per store/product |
| `gold_promotion_effectiveness` | Promotion revenue impact and discount cost |

## Data Quality
53 automated dbt tests across all Gold models covering null checks, uniqueness, accepted values, and numerical range validation.

## How to Run
1. Clone the repo
2. Create a virtual environment: `python -m venv venv`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.template` to `.env` and fill in your Databricks credentials
5. Generate data: `python notebooks/00_generate_dirty_pos_data.py`
6. Upload to Databricks Volume and run Bronze/Silver notebooks
7. Run dbt: `cd dbt_smartretail && dbt build`

## Cost
$0/month — built entirely on free tiers
