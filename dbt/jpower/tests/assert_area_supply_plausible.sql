-- Values that cannot be physically right. Negative values are expected for
-- pumped_storage, battery and interconnector_net_export, and solar dips a few MW
-- below zero at night, so those get looser bounds.
select *
from {{ ref('area_supply') }}
where quality_flag = 'ok'
  and (
       (metric in ('demand', 'total_supply') and (value <= 0 or value > 80000))
    or (metric = 'solar' and value < -50)
    or (metric in ('solar_curtailment', 'wind_curtailment', 'wind', 'nuclear') and value < 0)
  )
