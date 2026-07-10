with source as (
    select * from {{ source('fred', 'raw_fred__yields') }}
)

select
    series_id,
    maturity_label,
    cast(obs_date as date)              as yield_date,
    try_cast(nullif(value, '.') as double) as yield_pct,
    cast(_loaded_at as timestamp)       as loaded_at,
    _source                              as source_system
from source
where nullif(value, '.') is not null
