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

## Quick start

1. **Environment**

   ```bash
   cp .env.example .env
   ```

   Set `AIRFLOW_FERNET_KEY` (required for Airflow to encrypt connections). Generate:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. **Start stack**

   ```bash
   docker compose build
   docker compose up -d
   ```

   The first build installs ingestion + dbt dependencies into the custom Airflow image.

3. **URLs**

   | Service   | URL                          | Default credentials   |
   | --------- | ---------------------------- | --------------------- |
   | Airflow   | http://localhost:8080        | From `.env` (`admin` / `admin` if unchanged) |
   | MinIO API | http://localhost:9000        | `minioadmin` / `minioadmin` |
   | MinIO UI  | http://localhost:9001        | same                  |
   | Metabase  | http://localhost:3000        | finish setup wizard   |

4. **First pipeline run**

   Bronze must exist before dbt can read Parquet globs. Either trigger the DAG in Airflow (`market_pipeline`) or run manually:

   ```bash
   docker compose exec airflow-scheduler python /opt/airflow/ingestion/fetch_market_data.py
   docker compose exec airflow-scheduler bash -lc 'cd /opt/dbt && dbt run --profiles-dir /opt/dbt --project-dir /opt/dbt'
   ```

   Ad-hoc dbt (standalone service):

   ```bash
   docker compose run --rm dbt run
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

## Metabase + DuckDB

The stack mounts the same DuckDB warehouse file into Metabase at **`/data/warehouse.duckdb`** (read-only). In Metabase **Admin → Databases → Add database**, choose **DuckDB** if your Metabase edition exposes it, and set the database file path to `/data/warehouse.duckdb`.

If DuckDB is not listed, use the [Metabase community drivers](https://www.metabase.com/docs/latest/administration-guide/01-managing-databases.html) or query Gold tables via another client (DuckDB CLI, Python, etc.) against the same path on a machine that has the file.

## Configuration

- **CoinGecko / yfinance:** `COINGECKO_COIN_IDS`, `YFINANCE_TICKERS` in `.env` (comma-separated).
- **Kaggle backup CSV:** place `ingestion/data/backup.csv` or set `KAGGLE_CSV_PATH`.

## Local Python (without Airflow)

**Python version:** **dbt-core does not support Python 3.14** (you will see a `mashumaro` / `JSONObjectSchema` import error). Use **3.11–3.13**; **3.12** matches the Docker images (see `.python-version`).

```bash
python3.12 -m venv .venv && source .venv/bin/activate   # or: pyenv install 3.12 && pyenv local 3.12
pip install -r requirements.txt
```

Load `.env`, then ingestion (MinIO on `localhost:9000`):

```bash
set -a && source .env && set +a
export MINIO_ENDPOINT_URL="${MINIO_ENDPOINT_URL:-http://127.0.0.1:9000}"
python ingestion/fetch_market_data.py
```

dbt against local MinIO uses the **`host`** profile (`s3` → `127.0.0.1:9000`). By default, dbt looks for **`~/.dbt`**; this repo keeps **`dbt/profiles.yml`** in the project, so either:

- **From repo root (recommended):** `./scripts/dbt run --target host` (sets `DBT_PROFILES_DIR` and `--project-dir` for you), or
- **Explicit:** `export DBT_PROFILES_DIR="$PWD/dbt"` then `dbt run --project-dir dbt --target host`, or
- **`cd dbt`:** `dbt run --target host --profiles-dir . --project-dir .`

Optional: `export DUCKDB_PATH="$PWD/dbt/target/warehouse.duckdb"` (from repo root) so the DuckDB file stays under `dbt/target/`.

## Next steps (ideas)

- Add data quality tests (`dbt test`) and source freshness.
- Partition Bronze by date for cheaper incremental models.
- Export Gold to Parquet in MinIO for BI tools that prefer S3.
