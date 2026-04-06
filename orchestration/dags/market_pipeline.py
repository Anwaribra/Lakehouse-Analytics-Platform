from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="market_pipeline",
    default_args={
        "owner": "lakehouse",
        "depends_on_past": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    description="CoinGecko + yfinance → MinIO (Bronze), dbt → DuckDB (Silver/Gold)",
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["lakehouse", "crypto", "dbt", "minio"],
) as dag:
    ingest_bronze = BashOperator(
        task_id="ingest_bronze",
        bash_command="python /opt/airflow/ingestion/fetch_market_data.py",
    )

    
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            "cd /opt/dbt && "
            "dbt run --profiles-dir /opt/dbt --project-dir /opt/dbt "
            "--log-path /opt/airflow/logs/dbt"
        ),
    )

    ingest_bronze >> dbt_run
