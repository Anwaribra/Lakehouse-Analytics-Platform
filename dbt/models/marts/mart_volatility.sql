{{ config(materialized="table") }}

with base as (
    select
        date,
        asset,
        close,
        ln(close / lag(close) over (partition by asset order by date)) as log_return
    from {{ ref("int_crypto_prices_daily") }}
    where close is not null and close > 0
)

select
    date as price_date,
    asset,
    close,
    log_return,
    stddev_samp(log_return) over (
        partition by asset
        order by date
        rows between 6 preceding and current row
    ) as vol_7d,
    stddev_samp(log_return) over (
        partition by asset
        order by date
        rows between 29 preceding and current row
    ) as vol_30d
from base
