{{ config(materialized="view") }}

with raw as (
    select *
    from read_parquet({{ s3_bronze_glob("yfinance/*.parquet") }}, union_by_name = true)
)

select
    cast(date as date) as date,
    ticker,
    try_cast(open as double) as open,
    try_cast(high as double) as high,
    try_cast(low as double) as low,
    try_cast(close as double) as close,
    try_cast(volume as double) as volume,
    try_cast(ingested_at as timestamp) as ingested_at
from raw
where try_cast(close as double) is not null
