-- Kyushu: total_supply = generation + pumped storage + battery + other - net export.
-- Curtailment is reported alongside and is not part of supply. Holds exactly in the
-- public file (see docs/SOURCES.md); 1 MW tolerance for rounding. Other areas get
-- their own check once their files are verified.
with wide as (
    select
        period_start_jst,
        sum(case when metric = 'total_supply' then value end) as total_supply,
        sum(case when metric = 'interconnector_net_export' then value end) as net_export,
        sum(case when metric in (
            'nuclear', 'thermal_lng', 'thermal_coal', 'thermal_oil', 'thermal_other', 'hydro',
            'geothermal', 'biomass', 'solar', 'wind', 'pumped_storage', 'battery', 'other'
        ) then value end) as supply_parts
    from {{ ref('area_supply') }}
    where area_code = 'KYS' and quality_flag = 'ok'
    group by 1
)
select *, supply_parts - net_export - total_supply as diff
from wide
where abs(supply_parts - net_export - total_supply) > 1
