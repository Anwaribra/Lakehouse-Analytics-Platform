{{ config(materialized="table") }}

select
    date as price_date,
    asset,
    open,
    high,
    low,
    close,
    volume
from {{ ref("int_crypto_prices_daily") }}
