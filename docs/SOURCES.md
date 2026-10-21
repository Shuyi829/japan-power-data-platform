# Sources and Quirks Log

All sources are public. Verify every URL, format, and convention against a fresh download
before relying on it — sites change. Update this log whenever a new quirk is found.

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
