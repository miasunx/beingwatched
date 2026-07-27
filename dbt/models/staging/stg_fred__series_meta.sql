with yields as (
    select * from {{ source('fred', 'raw_fred__yields_series_meta') }}
),

cpi as (
    select * from {{ source('fred', 'raw_fred__cpi_series_meta') }}
),

pce as (
    select * from {{ source('fred', 'raw_fred__pce_series_meta') }}
),

nfp as (
    select * from {{ source('fred', 'raw_fred__nfp_series_meta') }}
),

unioned as (
    select * from yields
    union all
    select * from cpi
    union all
    select * from pce
    union all
    select * from nfp
)

select
    series_id,
    title,
    cast(series_observation_start as date) as series_observation_start,
    cast(series_observation_end as date)   as series_observation_end,
    frequency,
    frequency_short,
    units,
    units_short,
    seasonal_adjustment,
    seasonal_adjustment_short,
    cast(last_updated as timestamp)        as last_updated,
    popularity,
    notes,
    cast(fetched_at_utc as timestamp)      as fetched_at_utc,
    source_name
from unioned
