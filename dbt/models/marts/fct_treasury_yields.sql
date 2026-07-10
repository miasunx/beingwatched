with yields as (
    select * from {{ ref('stg_fred__yields') }}
)

select
    yield_date,
    maturity_label,
    yield_pct
from yields
