with source as (
    select * from {{ source('fred', 'raw_fred__cpi') }}
)

select
    series_id,
    measure_label,
    cast(obs_date as date)                 as cpi_date,
    try_cast(nullif(value, '.') as double) as index_level,
    cast(obs_realtime_start as date)       as cpi_realtime_start,
    cast(obs_realtime_end as date)         as cpi_realtime_end,
    cast(fetched_at_utc as timestamp)      as fetched_at_utc,
    source_name
from source
where nullif(value, '.') is not null
