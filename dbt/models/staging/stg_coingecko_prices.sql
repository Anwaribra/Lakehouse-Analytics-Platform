{{ config(materialized="view") }}

with raw as (
    select *
    from read_parquet({{ s3_bronze_glob("coingecko/*.parquet") }}, union_by_name = true)
)

select
    coin_id,
    try_cast(price_usd as double) as price_usd,
    try_cast(usd_24h_vol as double) as usd_24h_vol,
    try_cast(usd_24h_change as double) as usd_24h_change,
    try_cast(last_updated_at as bigint) as last_updated_epoch_s,
    cast(ingested_at as timestamp) as ingested_at,
    coalesce(source, 'coingecko_simple') as source
from raw
