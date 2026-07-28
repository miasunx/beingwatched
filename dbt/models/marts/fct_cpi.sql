with cpi as (
    select * from {{ ref('stg_fred__cpi') }}
),

with_priors as (
    select
        cur.cpi_date,
        cur.measure_label,
        cur.index_level,
        cur.cpi_realtime_start,
        cur.cpi_realtime_end,
        mom_prior.index_level as index_level_mom_prior,
        yoy_prior.index_level as index_level_yoy_prior
    from cpi as cur
    left join cpi as mom_prior
        on mom_prior.measure_label = cur.measure_label
       and mom_prior.cpi_date = cur.cpi_date - interval '1 month'
    left join cpi as yoy_prior
        on yoy_prior.measure_label = cur.measure_label
       and yoy_prior.cpi_date = cur.cpi_date - interval '12 months'
)

select
    cpi_date,
    measure_label,
    index_level,
    round(100 * (index_level / nullif(index_level_mom_prior, 0) - 1), 2) as mom_pct,
    round(100 * (index_level / nullif(index_level_yoy_prior, 0) - 1), 2) as yoy_pct,
    'mom_yoy_v2' as formula_version,
    cpi_realtime_start,
    cpi_realtime_end
from with_priors
