with pce as (
    select * from {{ ref('stg_fred__pce') }}
    where measure_label = 'core'
),

with_lags as (
    select
        pce_date,
        index_level,
        pce_realtime_start,
        pce_realtime_end,
        lag(index_level, 1)  over (order by pce_date) as index_level_lag1,
        lag(index_level, 12) over (order by pce_date) as index_level_lag12
    from pce
)

select
    pce_date,
    index_level,
    round(100 * (index_level / nullif(index_level_lag1, 0) - 1), 2)  as mom_pct,
    round(100 * (index_level / nullif(index_level_lag12, 0) - 1), 2) as yoy_pct,
    pce_realtime_start,
    pce_realtime_end
from with_lags
