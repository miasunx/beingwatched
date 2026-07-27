with nfp as (
    select * from {{ ref('stg_fred__nfp') }}
),

with_lag as (
    select
        nfp_date,
        payrolls_level,
        nfp_realtime_start,
        nfp_realtime_end,
        lag(payrolls_level, 1) over (order by nfp_date) as payrolls_level_lag1
    from nfp
)

select
    nfp_date,
    payrolls_level,
    payrolls_level - payrolls_level_lag1 as change_thousands,
    nfp_realtime_start,
    nfp_realtime_end
from with_lag
