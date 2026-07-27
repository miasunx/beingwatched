with source as (
    select * from {{ source('fred', 'raw_fred__series_meta') }}
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
from source
