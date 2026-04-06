# Lakehouse Analytics Platform

End-to-end crypto market data pipeline: ingest **CoinGecko** + **yfinance** (optional **Kaggle CSV** backup) into **MinIO** as Bronze Parquet, orchestrate with **Apache Airflow**, transform with **dbt + DuckDB** (Silver → Gold), and explore in **Metabase**.

## Architecture

![Pipeline Architecture](dashboard/pipeline-architecture.png)

## Tech stack

| Layer          | Tool                                      |
| -------------- | ----------------------------------------- |
| Ingestion      | Python, Requests, yfinance, boto3, Parquet  |
| Orchestration  | Apache Airflow (Docker, LocalExecutor)    |
| Storage        | MinIO (S3-compatible)                     |
| Transformation | dbt + DuckDB                              |
| Dashboard      | Metabase                                  |
| Infrastructure | Docker Compose                            |

## Project layout

```
lakehouse-analytics/
├── ingestion/
│   ├── fetch_market_data.py      # Bronze → MinIO (Parquet)
│   └── data/                     # Optional backup.csv (Kaggle-style)
├── dbt/
│   ├── models/
│   │   ├── staging/              # Silver: typed, cleaned
│   │   ├── intermediate/       # Joins / daily grain
│   │   └── marts/                # Gold: marts
│   ├── macros/
│   ├── seeds/
│   └── dbt_project.yml
├── orchestration/
│   └── dags/
│       └── market_pipeline.py    # Daily: ingest → dbt run
├── dashboard/
│   └── screenshots/
├── docker/
│   ├── airflow/                  # Airflow image + pip deps
│   └── dbt/                      # Standalone dbt image (optional)
├── scripts/
│   └── dbt                       # Wrapper: local dbt without ~/.dbt
├── docker-compose.yml
├── requirements.txt
└── README.md
```


## Pipeline flow

1. **Bronze** — `fetch_market_data.py` writes Parquet under `s3://<bucket>/bronze/coingecko/`, `bronze/yfinance/`, and optionally `bronze/kaggle_backup/`.
2. **Airflow** — DAG `market_pipeline` runs ingestion then `dbt run` daily.
3. **Silver** — dbt staging models read Bronze via `read_parquet('s3://…')` (httpfs + MinIO settings in `profiles.yml`).
4. **Gold** — marts: `mart_daily_prices`, `mart_volatility`, `mart_anomalies` (materialized tables in the DuckDB file).

## Lakehouse layers

- **Bronze:** Raw API-shaped data, Parquet in MinIO (timestamped files).
- **Silver:** Staging views — typed columns, nulls filtered where needed.
- **Gold:** `mart_daily_prices` (OHLCV by asset/day), `mart_volatility` (7d/30d rolling vol of log returns), `mart_anomalies` (2σ spike flag vs 30d vol).
