# Roadmap

Assumes part-time work of roughly 8–10 hours/week. Estimates assume Claude Code
does much of the boilerplate; add 30–50% if writing everything by hand.

## Phase 1 — Data platform (≈130–190 h, ~3–4 months)

### Stage A — End-to-end MVP (≈50–70 h, 5–7 weeks)

Goal: one thin, complete pipeline before going wide.

| # | Step | Hours | Notes |
|---|------|-------|-------|
| 1 | Repo setup | 6–8 | Review `05 weather-api-data-engineering`; dbt + DuckDB; ruff, pytest, simple CI |
| 2 | Source exploration & design | 8–12 | Download samples from every source; start quirks log; define time convention and silver schema |
| 3 | JEPX day-ahead prices | 6–10 | Check for a direct 30-min CSV before scraping HTML; backfill history |
| 4 | Generation mix — Tokyo, Kansai, Kyushu | 14–20 | cp932 encoding, header skipping, Kyushu time shift, monthly re-pulls and revision tracking |
| 5 | Weather per area | 4–6 | Reuse the weather pipeline |
| 6 | Silver models in dbt | 8–10 | Unified long tables, as-of handling, dedup by latest published version |
| 7 | Basic quality tests | 4–6 | Missing half-hours, duplicates, ranges, header validation |

Milestone: Kyushu net demand vs. floor price analysis is possible.

### Stage B — Full coverage (≈60–90 h, 6–9 weeks)

| # | Step | Hours | Notes |
|---|------|-------|-------|
| 8 | Remaining 6 TSOs | 8–12 | Config only, ideally; Chugoku extra columns, Hokuriku headers, Tohoku daily file in HTML |
| 9 | OCCTO interconnectors | 10–16 | Browser automation (Playwright), ZIP with two files, actual vs. forecast by file timestamp |
| 10 | Plant-level generation + own plant master | 14–22 | Hardest step; build master from public data; flag unknown plant codes |
| 11 | HJKS outages | 8–16 | Highest download risk: timeouts, retries; messy records |
| 12 | Orchestration in Dagster | 8–12 | Schedules, retries, backfills, schema-drift alerts |
| 13 | Freshness & quality checks | 6–8 | Per-source expected arrival times |

Simplify steps 9–11 first if running behind (e.g. one region's plants, or units above a size threshold).

### Stage C — Production polish (≈20–30 h, 2–3 weeks)

| # | Step | Hours | Notes |
|---|------|-------|-------|
| 14 | Port to Snowflake or Databricks | 10–14 | Pick the one in target job postings; check free-tier limits |
| 15 | Documentation | 6–10 | README, architecture diagram, data dictionary, quirks write-up |
| 16 | (Optional) OCCTO reserve margins | 6–10 | Day-ahead and week-ahead |

### Possible extra sources (not collected by many existing pipelines)

JEPX intraday prices, imbalance prices, futures settlements.

## Phase 2 — Market analytics marts

Each mart gets a short README explaining what it shows about the market.

- `mart_net_demand_floor` — net demand (demand − solar − wind) vs. day-ahead price per area;
  0.01 JPY/kWh floor periods; curtailment. Start with Kyushu.
- `mart_merit_order` — which units run at which price levels (Tokyo/Kansai).
- `mart_market_split` — interconnector utilization vs. area price spreads; east–west frequency converters.
- Lightweight dashboard (Streamlit or Evidence).

## Phase 3 — Forecasting and trading

- Quantile price forecast (LightGBM, walk-forward backtest, MLflow, FastAPI endpoint).
- Treat 0.01 prices as censored; consider a separate floor-probability model.
- Battery arbitrage backtest turning forecast error into P&L (no negative prices in Japan
  changes the charging economics).
- Optional: cost of demand/solar forecast error in intraday/imbalance prices.

## Phase 4 — AI layer

- Text-to-SQL agent over gold marts, with an evaluation set of questions and expected answers.

## First month checklist

- [ ] Week 1: review weather project; scaffold repo; JEPX ingestion into bronze
- [ ] Week 2: Tokyo, Kansai, Kyushu TSO feeds; unified silver schema
- [ ] Week 3: dbt models, tests, freshness checks; daily runs in Dagster
- [ ] Week 4: `mart_net_demand_floor` + simple chart + first README write-up
