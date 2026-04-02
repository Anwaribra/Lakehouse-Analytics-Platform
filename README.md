# Lakehouse Analytics Platform

A production-style, end-to-end data engineering project that ingests real-time market data, processes it through a multi-layer lakehouse architecture, and serves insights via an interactive dashboard.

## Pipeline Architecture
![Pipeline Architecture](/dashboard/pipeline-architecture.png)


## Project Structure

```
lakehouse-analytics/
│
├── ingestion/
│   └── fetch_market_data.py          # API ingestion scripts
│
├── dbt/
│   ├── models/
│   │   ├── staging/                  # Raw → cleaned
│   │   ├── intermediate/             # Joins & enrichment
│   │   └── marts/                    # Final business tables
│   │
│   └── dbt_project.yml
│
├── orchestration/
│   └── dags/
│       └── market_pipeline.py        # Airflow DAG
│
├── dashboard/
│   └── screenshots/                 
│
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Tech Stack


| Layer          | Tool                  |
| -------------- | --------------------- |
| Ingestion      | Python, Requests      |
| Orchestration  | Apache Airflow        |
| Storage        | MinIO (S3-compatible) |
| Transformation | dbt + DuckDB          |
| Dashboard      | Metabase              |
| Infrastructure | Docker Compose        |
