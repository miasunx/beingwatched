with nfp as (
    select * from {{ ref('stg_fred__nfp') }}
),

with_prior as (
    select
        cur.nfp_date,
        cur.payrolls_level,
        cur.nfp_realtime_start,
        cur.nfp_realtime_end,
        prior.payrolls_level as payrolls_level_prior
    from nfp as cur
    left join nfp as prior
        on prior.nfp_date = cur.nfp_date - interval '1 month'
)

select
    nfp_date,
    payrolls_level,
    payrolls_level - payrolls_level_prior as change_thousands,
    nfp_realtime_start,
    nfp_realtime_end
from with_prior
