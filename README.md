# Japan Power Data Platform

Half-hourly data platform for the Japanese wholesale power market, built only from
**public** sources (JEPX, the 9 regional TSOs, OCCTO, HJKS) and open weather data.

- Roadmap: [docs/PLAN.md](docs/PLAN.md)
- Sources and quirks: [docs/SOURCES.md](docs/SOURCES.md)

## Setup

```bash
uv sync                      # Python 3.11 env + dependencies
cp .env.example .env         # fill in only if you use Snowflake
uv run ruff check .
uv run pytest
cd dbt/jpower && uv run dbt build --profiles-dir .
```

## Pipeline (Kyushu area supply)

```bash
# 1. Bronze: download the month (or store a file you downloaded by hand)
uv run python -m jpower.ingest.bronze --source kyushu_area_supply --date 2026-10-01
uv run python -m jpower.ingest.bronze --source kyushu_area_supply --date 2026-10-01 --file <path>

# 2. Raw: parse every new bronze file into raw.area_supply
uv run python -m jpower.load --source kyushu_area_supply

# 3. Silver + gold + tests
cd dbt/jpower && uv run dbt build --profiles-dir . && cd ../..

# 4. CSV: data/exports/kyushu_demand_30min.csv
uv run python -m jpower.export --table gold.kyushu_demand_30min
```

| Layer | Table | What it holds |
|---|---|---|
| bronze | files + `bronze.manifest` | raw files unchanged; one manifest row per attempt (new / unchanged / error) |
| raw | `raw.area_supply` | parsed rows of **every** file version, with `downloaded_at_utc` |
| silver | `silver.area_supply` | latest revision per area, half hour, metric; tested for duplicates, gaps, plausibility, Kyushu balance |
| gold | `gold.kyushu_demand_30min` | `period_start_jst, period_end_jst, date, time, demand_mw, quality_flag` |

Identical re-downloads are not stored twice; revised files are kept side by side, and
silver picks the most recent download, so earlier views can always be rebuilt from raw.

## Layout

```
config/sources.yaml   per-source reader config (URL template, encoding, headers, time convention)
src/jpower/           Python package: config, bronze ingestion, readers, loader, export
dbt/jpower/           dbt project: seeds (area codes), silver and gold models
tests/                pytest tests; tests/fixtures/ holds one raw sample file per source
data/                 local DuckDB + bronze files (gitignored)
```
