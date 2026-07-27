with yields as (
    select * from {{ ref('stg_fred__yields') }}
)

select
    yield_date,
    maturity_label,
    yield_pct,
    yield_realtime_start,
    yield_realtime_end
from yields
