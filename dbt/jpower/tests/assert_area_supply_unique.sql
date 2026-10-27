-- One row per source, area, half hour and metric.
select source, area_code, period_start_jst, metric, count(*) as n
from {{ ref('area_supply') }}
group by 1, 2, 3, 4
having count(*) > 1
