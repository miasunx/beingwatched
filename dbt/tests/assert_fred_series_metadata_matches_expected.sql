-- Spec §7 "Macro unit checks": validate FRED series units, frequency, and
-- seasonal adjustment against known-good values before promoting a series.
-- Fails if a series is missing from stg_fred__series_meta, or if FRED
-- publishes it with different units/seasonal-adjustment/frequency than
-- what the ingestion and transformation SQL currently assume.

with expected as (
    select * from (
        values
            ('DGS2',     'Percent',              'Not Seasonally Adjusted', 'Daily'),
            ('DGS10',    'Percent',              'Not Seasonally Adjusted', 'Daily'),
            ('CPIAUCSL', 'Index 1982-1984=100',  'Seasonally Adjusted',     'Monthly'),
            ('CPILFESL', 'Index 1982-1984=100',  'Seasonally Adjusted',     'Monthly'),
            ('PCEPI',    'Index 2017=100',       'Seasonally Adjusted',     'Monthly'),
            ('PCEPILFE', 'Index 2017=100',       'Seasonally Adjusted',     'Monthly'),
            ('PAYEMS',   'Thousands of Persons', 'Seasonally Adjusted',     'Monthly')
    ) as t(series_id, expected_units, expected_seasonal_adjustment, expected_frequency)
),

actual as (
    select * from {{ ref('stg_fred__series_meta') }}
)

select
    expected.series_id,
    actual.units,
    expected.expected_units,
    actual.seasonal_adjustment,
    expected.expected_seasonal_adjustment,
    actual.frequency,
    expected.expected_frequency
from expected
left join actual on expected.series_id = actual.series_id
where actual.series_id is null
   or actual.units is distinct from expected.expected_units
   or actual.seasonal_adjustment is distinct from expected.expected_seasonal_adjustment
   or actual.frequency is distinct from expected.expected_frequency
