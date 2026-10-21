# Japan Power Data Platform

A half-hourly data platform for the Japanese wholesale power market, built entirely
from **public** sources (JEPX, the 9 regional TSOs, OCCTO, HJKS) plus open weather data.

Read `docs/PLAN.md` for the roadmap and `docs/SOURCES.md` for source details and known quirks
before making design decisions.

## Goals

1. **Data engineering showcase (primary):** reliable ingestion of messy, heterogeneous
   sources into a clean warehouse, with data quality built in from day one.
2. **Market learning:** analysis marts that explain Japanese price behaviour
   (floor prices, merit order, market splitting).
3. **Later phases:** forecasting + battery backtest (trading), and a text-to-SQL agent (AI engineering).

## Hard rules

- **Public data only.** Never use, request, or reproduce proprietary data, internal code,
  internal table names, or internal documents from any employer. If something can't be
  built from public sources, leave it out.
- Never commit secrets. Credentials live in `.env` (gitignored); provide `.env.example`.
- Store raw downloads unchanged in the bronze layer so any transform can be re-run.

## Architecture

- **Bronze:** raw files as downloaded (original encoding), plus a manifest row per file
  (source, URL, download time, checksum, HTTP status).
- **Silver:** cleaned, unified long tables. One table per domain, not one table per series.
- **Gold:** analysis-ready marts (e.g. `mart_net_demand_floor`, `mart_merit_order`, `mart_market_split`).
- Local first: Python ingestion + **dbt + DuckDB**. Port to Snowflake or Databricks later (Phase 1, Stage C).
- Orchestration: **Dagster** (schedules, retries, backfills, alerts).

## Core design decisions (keep these consistent)

- **Config-driven readers.** One generic CSV/HTML reader whose per-source behaviour comes from
  config (URL template, encoding, rows to skip, expected headers, column map, units,
  time convention). Adding a source = adding config, not a new class.
- **Schema validation at ingestion.** Compare headers to the expected schema; fail loudly on
  mismatch instead of silently writing shifted columns.
- **Canonical time:** `period_start` timestamp in JST (also store UTC), 30-minute resolution.
  Convert period-ending sources and "24:00" at the silver layer.
- **Missing data = NULL + quality flag.** No sentinel values like -99.
- **Revisions are expected.** Re-pull the current month each run, upsert idempotently, and keep
  `published_at` / `ingested_at` so any point-in-time view can be reconstructed.
- **Store 30-minute data only;** hourly/daily aggregates are dbt models, not separate ingestions.
- **Japanese text:** read Shift-JIS (cp932) where needed; normalize full-width to half-width
  characters; map kanji area names to English area codes in one seed table.

## Monitoring (a first-class feature, not an afterthought)

- Freshness: expected arrival time per source; alert when late.
- Schema drift: header mismatch → failed run + alert.
- Plausibility: value ranges per metric (e.g. no solar at night, no negative demand),
  sudden level shifts vs recent history, missing half-hours, duplicates.
- Unknown entities: new plant codes / area codes are flagged, not silently dropped.

## Conventions

- Python 3.11+, type hints, `ruff` for lint/format, `pytest` for tests.
- Each source has: config entry, fixture sample file under `tests/fixtures/`, parser test.
- Keep `docs/SOURCES.md` quirks log updated whenever a new quirk is found.
- Small, reviewable commits.

## Related project

`../05 weather-api-data-engineering` is the author's earlier weather pipeline. Review it before
scaffolding and reuse its patterns (tooling, layout, ingestion code) where sensible; weather per
area becomes one source in this platform.
