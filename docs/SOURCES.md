# Sources and Quirks Log

All sources are public. Verify every URL, format, and convention against a fresh download
before relying on it — sites change. Update this log whenever a new quirk is found.

**Clean-room rule:** every entry here comes from the public source itself (its website,
published docs, or a downloaded file). Nothing is taken from any employer's code, configs,
or documents — not even URLs or column mappings.

## General quirks (apply to many sources)

- **Encoding:** CSVs with Japanese headers are often Shift-JIS (cp932). Excel displays them
  incorrectly; read with an explicit encoding.
- **Time conventions differ:** some sources label periods by start time ("00:00-00:30"),
  others by end time, with "24:00" meaning 00:00 of the next day. Normalize to `period_start`.
- **Revisions:** demand/supply data is revised after first publication, and gaps can be
  filled later. Re-pull the current month every run and upsert.
- **Units:** check per file. Japanese data often uses 万kW (1 万kW = 10 MW). Plant data comes as
  kWh per 30 minutes (MW = kWh × 2 / 1000).
- **Text normalization:** full-width characters (Ａ, １, full-width space) appear in names;
  normalize to half-width.
- **Area names:** kanji → codes: 北海道 Hokkaido, 東北 Tohoku, 東京 Tokyo, 中部 Chubu,
  北陸 Hokuriku, 関西 Kansai, 中国 Chugoku, 四国 Shikoku, 九州 Kyushu, 沖縄 Okinawa
  (Okinawa is not part of JEPX).

## 1. JEPX day-ahead prices

- Site: https://www.jepx.jp/en/electricpower/market-data/spot/
- System price + 9 area prices, 48 half-hour periods per day, period labels are period-beginning.
- The page renders prices in an HTML table after picking a date. **First check whether a direct
  30-minute CSV download exists** (much more robust than scraping).

## 2. Area supply–demand / generation mix (9 TSOs)

- Monthly CSVs for most areas, e.g. `eria_jukyu_<yyyymm>_<NN>.csv`, where `NN` is an area code
  (Tokyo 03, Chubu 04, Hokuriku 05, Kansai 06, Chugoku 07, Shikoku 08, Kyushu 09), not a day.
  - Tokyo: https://www.tepco.co.jp/forecast/html/images/eria_jukyu_<yyyymm>_03.csv
  - Chubu: https://powergrid.chuden.co.jp/denki_yoho_content_data/eria_jukyu_<yyyymm>_04.csv
  - Hokuriku: https://www.rikuden.co.jp/nw/denki-yoho/csv/eria_jukyu_<yyyymm>_05.csv
  - Kansai: https://www.kansai-td.co.jp/interchange/denkiyoho/area-performance/eria_jukyu_<yyyymm>_06.csv
  - Chugoku: https://www.energia.co.jp/nw/jukyuu/sys/eria_jukyu_<yyyymm>_07.csv
  - Shikoku: https://www.yonden.co.jp/nw/supply_demand/csv/eria_jukyu_<yyyymm>_08.csv
  - Kyushu: https://www.kyuden.co.jp/td_area_jukyu/csv/eria_jukyu_<yyyymm>_09.csv
- Daily files:
  - Tohoku: https://setsuden.nw.tohoku-epco.co.jp/common/demand/realtime_jukyu/realtime_jukyu_<yyyymmdd>_02.csv
    (CSV content may arrive inside an HTML response rather than as a download)
  - Hokkaido: https://denkiyoho.hepco.co.jp/area/data/<yyyymmdd>_hokkaido_jukyu.csv (extra rows to skip)
- Columns typically include: nuclear, LNG, coal, oil, other thermal, hydro, geothermal, biomass,
  solar, solar curtailed, wind, wind curtailed, pumped storage, battery, interconnection, other, total.
- Known differences: header rows to skip vary (Hokuriku differs); several date formats
  (yyyy/MM/dd, yyyyMMdd, yyyy/M/d …); Chugoku has extra columns (thermal and biomass curtailment)
  which shift later columns; Shikoku lacks some columns; Kyushu appears to be period-ending.
- **Columns can change without notice** → validate headers on every run.

### Kyushu (`kyushu_area_supply`) — verified from a downloaded file, 2026-10-27

Fixture: `tests/fixtures/kyushu/eria_jukyu_202610_09.csv` (October 2026, downloaded 27 Oct).

- **Encoding / layout:** cp932, CRLF, every field quoted. Row 0 is a unit/group line
  (`単位[MW平均]`, …, `供給力`); row 1 is the header. → `skip_rows: 1`.
- **Unit:** average MW per half hour (not 万kW).
- **Columns (20):** DATE, TIME, エリア需要 (area demand), 原子力, 火力（ＬＮＧ／石炭／石油／その他）, 水力,
  地熱, バイオマス, 太陽光発電実績, 太陽光出力制御量, 風力発電実績, 風力出力制御量, 揚水, 蓄電池, 連系線,
  その他, 合計. Thermal headers use **full-width** brackets and letters → NFKC-normalize before matching.
- **Time:** DATE `yyyymmdd`, TIME `0:30` … `24:00` → **period-ending** (confirmed).
  `24:00` belongs to the same DATE; period_start = label − 30 min.
- **Current month is partial and updated intraday:** the file downloaded at ~15:00 JST ended at
  the 10:30 label → re-pull the current month every run; bronze keeps each revision.
- **Signs:** 揚水 (pumped storage) and 蓄電池 (battery) are negative when pumping/charging;
  連系線 positive = **net export** out of Kyushu; solar can be slightly negative at night (−8 MW seen).
- **Balance identity (holds exactly on all 1,269 rows):**
  合計 = Σ(generation, 揚水, 蓄電池, その他) − 連系線, with the two 出力制御量 (curtailment) columns
  excluded. Curtailment is reported alongside, not part of supply. Good automatic quality check.
- 合計 vs エリア需要 differ by −32…+18 MW (losses/rounding); not an error.
- URL template **confirmed 2026-10-27**: plain HTTP GET returns the file (HTTP 200), no session or form needed.
- Re-download 22 minutes later already contained one more half hour (file grows through the day).

**History and formats (backfill 2026-10-27, months 2016-04 … 2026-09 requested):**

- **Available: 2023-10 onwards (36 months back from Oct 2026), no gaps.** Every month from
  2016-04 to 2023-09 returns HTTP 404 at this URL. Looks like a rolling ~3-year window;
  older history may live elsewhere or in another format (not yet investigated).
  → Keep every file in bronze: once a month drops out of the window it cannot be re-pulled.
  → Re-check next month whether 2023-10 has disappeared (confirms the rolling window).
- **Three layouts over time** (all cp932, all have the unit line in row 0):

  | Months | Unit line | Columns | Quoted | End of day |
  |---|---|---|---|---|
  | 2023-10…2024-02, current months (2026-09, 2026-10) | `供給力` | 20 | yes | `24:00` |
  | 2024-03…2026-03 | `供給力(確報)` (**final**) | 20 | no | `24:00:00` |
  | 2026-04…2026-08 | `供給力(確報)` | 22: adds 火力出力制御量, バイオマス出力制御量 | no | `24:00:00` |

  The unmarked layout appears to be **preliminary** (速報); recent months are later replaced at
  the same URL by final (確報) files. Why 2023-10…2024-02 were never re-published as final is unknown.
- **New curtailment columns from April 2026 (FY2026):** thermal and biomass curtailment, mapped to
  `thermal_curtailment` / `biomass_curtailment`. They are not part of the balance identity either.
- **Date format varies per file:** the 2025-12 final file writes `2025/12/1` instead of `20251201`.
- **Wind can be slightly negative** (−2 MW, 16 half hours, only in preliminary files) — station power.

## 3. OCCTO interconnectors and reserve margins

- Site: https://web-kohyo.occto.or.jp/kks-web-public/ (browser automation needed).
- Downloads are ZIPs containing two CSVs; select by filename:
  - 広域予備率ブロック情報 — reserve margin / demand by block (day after next, weekly)
  - 広域予備率連系線情報 — interconnector information
- Interconnectors (12), including the Hokkaido–Honshu link and the east–west frequency converters.
  Metrics: operating capacity, margin, planned flow, free capacity (both directions),
  and a split flag (分断あり = split, 分断なし = no split).
- Actual vs. forecast rows are distinguished by the file's update timestamp → keep `published_at`.

## 4. Plant-level generation actuals

- Site: https://hatsuden-kokai.occto.or.jp/hks-web-public/info/hks
- Terms-acceptance click, dropdowns, date range → CSV. Published after ~15:00 JST.
- Unit-level kWh per 30 minutes, columns 00:30 … 24:00 (period-ending).
- Build an own plant master (code, unit, area, fuel, capacity) from public data.
  New plants appear regularly → flag unknown codes.

## 5. HJKS outages

- Site: https://hjks.jepx.or.jp/hjks/outages
- CSV download of planned/unplanned outages and capacity reductions.
- Download can be slow or time out → generous timeouts, retries, alerting.
- Messy records: missing recovery dates, deleted entries (削除), placeholder dates.

## 6. Weather

- Open-Meteo (reuse `05 weather-api-data-engineering`), one or more points per area.

## Quirks found during development

<!-- Add entries as: YYYY-MM-DD — source — quirk — how it was handled -->

- 2026-10-27 — Kyushu — full-width （ＬＮＧ） in headers — headers NFKC-normalized before validation
- 2026-10-27 — Kyushu — period-ending TIME with 24:00 — shifted −30 min to period_start in the reader
- 2026-10-27 — Kyushu — 連系線 sign undocumented in file — inferred from exact balance identity: positive = export
- 2026-10-27 — Kyushu — files before 2023-10 return 404 — bronze keeps every file; investigate older archive later
- 2026-10-27 — Kyushu — 22-column layout from 2026-04 — second entry in `header_layouts`; unknown layouts still fail
- 2026-10-27 — Kyushu — `24:00:00` in final files — time parser accepts H:MM and H:MM:00
- 2026-10-27 — Kyushu — `2025/12/1` dates in 2025-12 — `date_formats` list in config, each matched exactly
- 2026-10-27 — Kyushu — wind −2 MW — plausibility test allows −50 MW for solar and wind
