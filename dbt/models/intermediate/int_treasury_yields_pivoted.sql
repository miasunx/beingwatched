with yield_2y as (
    select yield_date, yield_pct as yield_2y_pct
    from {{ ref('stg_fred__yields') }}
    where maturity_label = '2Y'
),

yield_10y as (
    select yield_date, yield_pct as yield_10y_pct
    from {{ ref('stg_fred__yields') }}
    where maturity_label = '10Y'
)

select
    yield_2y.yield_date,
    yield_2y.yield_2y_pct,
    yield_10y.yield_10y_pct
from yield_2y
inner join yield_10y on yield_2y.yield_date = yield_10y.yield_date
