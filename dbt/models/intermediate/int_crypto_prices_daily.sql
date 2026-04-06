{{ config(materialized="view") }}

select
    date,
    upper(replace(ticker, '-USD', '')) as asset,
    open,
    high,
    low,
    close,
    volume
from {{ ref("stg_yfinance_ohlcv") }}
