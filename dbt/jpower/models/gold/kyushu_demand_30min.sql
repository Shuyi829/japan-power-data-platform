-- Kyushu area demand per half hour: a simple, analysis-ready series.
-- period_start_jst is canonical; period_end_jst is included for consumers that use
-- period-ending labels. `date` and `time` describe period_start (JST).
select
    period_start_jst,
    {{ dbt.dateadd('minute', 30, 'period_start_jst') }} as period_end_jst,
    cast(period_start_jst as date) as date,
    {{ format_hhmm('period_start_jst') }} as time,
    value as demand_mw,
    quality_flag
from {{ ref('area_supply') }}
where area_code = 'KYS'
  and metric = 'demand'
order by period_start_jst
