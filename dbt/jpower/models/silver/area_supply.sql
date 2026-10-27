-- Latest published value per area, half hour and metric.
-- raw keeps every file version; here the most recent download wins, so a revised
-- or gap-filled value from a later re-pull replaces the earlier one.
select
    source,
    area_code,
    period_start_jst,
    period_start_utc,
    metric,
    value,
    unit,
    quality_flag,
    downloaded_at_utc,
    file_path
from {{ source('raw', 'area_supply') }}
qualify row_number() over (
    partition by source, area_code, period_start_jst, metric
    order by downloaded_at_utc desc, loaded_at_utc desc
) = 1
