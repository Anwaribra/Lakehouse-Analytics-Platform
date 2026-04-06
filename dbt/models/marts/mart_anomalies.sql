{{ config(materialized="table") }}

select
    price_date,
    asset,
    close,
    log_return,
    vol_7d,
    vol_30d,
    case
        when vol_30d is null or log_return is null then false
        else abs(log_return) > 2 * vol_30d
    end as is_spike_2sigma_30d
from {{ ref("mart_volatility") }}
