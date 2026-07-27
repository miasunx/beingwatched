with cpi as (
    select * from {{ ref('stg_fred__cpi') }}
),

with_lags as (
    select
        cpi_date,
        measure_label,
        index_level,
        cpi_realtime_start,
        cpi_realtime_end,
        lag(index_level, 1)  over (partition by measure_label order by cpi_date) as index_level_lag1,
        lag(index_level, 12) over (partition by measure_label order by cpi_date) as index_level_lag12
    from cpi
)

select
    cpi_date,
    measure_label,
    index_level,
    round(100 * (index_level / nullif(index_level_lag1, 0) - 1), 2)  as mom_pct,
    round(100 * (index_level / nullif(index_level_lag12, 0) - 1), 2) as yoy_pct,
    cpi_realtime_start,
    cpi_realtime_end
from with_lags
