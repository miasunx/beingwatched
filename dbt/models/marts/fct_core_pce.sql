with pce as (
    select * from {{ ref('stg_fred__pce') }}
    where measure_label = 'core'
),

with_priors as (
    select
        cur.pce_date,
        cur.index_level,
        cur.pce_realtime_start,
        cur.pce_realtime_end,
        mom_prior.index_level as index_level_mom_prior,
        yoy_prior.index_level as index_level_yoy_prior
    from pce as cur
    left join pce as mom_prior
        on mom_prior.pce_date = cur.pce_date - interval '1 month'
    left join pce as yoy_prior
        on yoy_prior.pce_date = cur.pce_date - interval '12 months'
)

select
    pce_date,
    index_level,
    round(100 * (index_level / nullif(index_level_mom_prior, 0) - 1), 2) as mom_pct,
    round(100 * (index_level / nullif(index_level_yoy_prior, 0) - 1), 2) as yoy_pct,
    'mom_yoy_v2' as formula_version,
    pce_realtime_start,
    pce_realtime_end
from with_priors
