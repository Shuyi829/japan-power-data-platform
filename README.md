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

## Layout

```
config/sources.yaml   per-source reader config (URL template, encoding, headers, time convention)
src/jpower/           Python package: config loader, ingestion (bronze)
dbt/jpower/           dbt project: seeds (area codes), silver and gold models
tests/                pytest tests; tests/fixtures/ holds one raw sample file per source
data/                 local DuckDB + bronze files (gitignored)
```
