-- Values that cannot be physically right. Negative values are expected for
-- pumped_storage, battery and interconnector_net_export. Solar and wind dip a few MW
-- below zero when plants draw station power (e.g. solar at night, wind in calm periods:
-- -8 MW solar and -2 MW wind seen in Kyushu files), so they get a small tolerance.
select *
from {{ ref('area_supply') }}
where quality_flag = 'ok'
  and (
       (metric in ('demand', 'total_supply') and (value <= 0 or value > 80000))
    or (metric in ('solar', 'wind') and value < -50)
    or (metric like '%_curtailment' and value < 0)
    or (metric = 'nuclear' and value < 0)
  )
