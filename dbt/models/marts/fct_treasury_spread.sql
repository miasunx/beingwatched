with pivoted as (
    select * from {{ ref('int_treasury_yields_pivoted') }}
)

select
    yield_date,
    yield_2y_pct,
    yield_10y_pct,
    round((yield_10y_pct - yield_2y_pct) * 100, 2) as spread_bps,
    (yield_10y_pct - yield_2y_pct) < 0    as inversion_flag
from pivoted
