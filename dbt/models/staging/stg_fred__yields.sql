with source as (
    select * from {{ source('fred', 'raw_fred__yields') }}
)

select
    series_id,
    maturity_label,
    cast(obs_date as date)                 as yield_date,
    try_cast(nullif(value, '.') as double) as yield_pct,
    cast(obs_realtime_start as date)       as yield_realtime_start,
    cast(obs_realtime_end as date)         as yield_realtime_end,
    cast(fetched_at_utc as timestamp)      as fetched_at_utc,
    source_name
from source
where nullif(value, '.') is not null
