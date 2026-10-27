-- Every half hour between the first and last period is present for each metric.
select
    source, area_code, metric,
    min(period_start_jst) as first_period,
    max(period_start_jst) as last_period,
    count(distinct period_start_jst) as periods_found,
    {{ dbt.datediff('min(period_start_jst)', 'max(period_start_jst)', 'minute') }} / 30 + 1
        as periods_expected
from {{ ref('area_supply') }}
group by 1, 2, 3
having count(distinct period_start_jst)
    <> {{ dbt.datediff('min(period_start_jst)', 'max(period_start_jst)', 'minute') }} / 30 + 1
