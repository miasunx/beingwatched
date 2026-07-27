with source as (
    select * from {{ source('fred', 'raw_fred__nfp') }}
)

select
    series_id,
    cast(obs_date as date)                 as nfp_date,
    try_cast(nullif(value, '.') as double) as payrolls_level,
    cast(obs_realtime_start as date)       as nfp_realtime_start,
    cast(obs_realtime_end as date)         as nfp_realtime_end,
    cast(fetched_at_utc as timestamp)      as fetched_at_utc,
    source_name
from source
where nullif(value, '.') is not null
