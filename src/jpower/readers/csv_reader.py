"""Generic config-driven CSV reader: raw bronze bytes -> long, typed rows.

Every source-specific detail (encoding, rows to skip, expected headers, column map,
time convention, unit) comes from SourceConfig. Steps:

1. decode with the configured encoding (e.g. cp932)
2. normalize headers full-width -> half-width (NFKC) and validate against
   ``expected_headers`` -> SchemaMismatchError on any difference (no silent column shifts)
3. build ``period_start`` in JST (and UTC): period-ending labels such as "24:00" are
   shifted back 30 minutes, so 24:00 on 1 Oct becomes 23:30 on 1 Oct
4. melt mapped columns into one row per (period, metric); values that are blank or
   unparseable become NULL with a quality flag, never a sentinel
"""

from __future__ import annotations

import datetime as dt
import io
import unicodedata

import pandas as pd

from jpower.config import SourceConfig

PERIOD = dt.timedelta(minutes=30)
JST_OFFSET = dt.timedelta(hours=9)  # Japan has no daylight saving time

OUTPUT_COLUMNS = [
    "source",
    "area_code",
    "period_start_jst",
    "period_start_utc",
    "metric",
    "value",
    "unit",
    "quality_flag",
]


class SchemaMismatchError(ValueError):
    """Headers in the file differ from the configured expected headers."""


def normalize(text: str) -> str:
    """Full-width -> half-width (Ａ→A, （→(, full-width space→space) and trim."""
    return unicodedata.normalize("NFKC", text).strip()


def validate_headers(source: SourceConfig, headers: list[str]) -> None:
    expected = [normalize(h) for h in source.expected_headers]
    if headers == expected:
        return
    missing = [h for h in expected if h not in headers]
    unexpected = [h for h in headers if h not in expected]
    detail = f"missing={missing} unexpected={unexpected}"
    if not missing and not unexpected:
        detail = "same columns, different order"
    raise SchemaMismatchError(f"{source.name}: header mismatch ({detail}); got {headers}")


def _period_start(source: SourceConfig, dates: pd.Series, times: pd.Series) -> pd.Series:
    day = pd.to_datetime(dates, format=source.date_format)
    hm = times.str.extract(r"^\s*(\d{1,2}):(\d{2})\s*$")
    if hm.isna().any().any():
        bad = times[hm.isna().any(axis=1)].unique()[:5].tolist()
        raise ValueError(f"{source.name}: unparseable time labels {bad}")
    label = day + pd.to_timedelta(hm[0].astype(int) * 60 + hm[1].astype(int), unit="min")
    return label - PERIOD if source.time_convention == "period_end" else label


def parse_csv(source: SourceConfig, content: bytes) -> pd.DataFrame:
    """Parse one raw file into long rows with columns OUTPUT_COLUMNS."""
    text = content.decode(source.encoding)
    df = pd.read_csv(io.StringIO(text), skiprows=source.skip_rows, dtype=str, keep_default_na=False)
    df.columns = [normalize(c) for c in df.columns]
    validate_headers(source, list(df.columns))

    start_jst = _period_start(source, df[source.date_column], df[source.time_column])
    wide = df[list(source.column_map)].rename(columns=source.column_map)
    wide.insert(0, "period_start_jst", start_jst)
    long = wide.melt(id_vars="period_start_jst", var_name="metric", value_name="raw")

    raw = long["raw"].map(normalize)
    long["value"] = pd.to_numeric(raw.str.replace(",", "", regex=False), errors="coerce")
    long["quality_flag"] = "ok"
    long.loc[raw == "", "quality_flag"] = "missing"
    long.loc[(raw != "") & long["value"].isna(), "quality_flag"] = "invalid"

    long["source"] = source.name
    long["area_code"] = source.area_code
    long["period_start_utc"] = long["period_start_jst"] - JST_OFFSET
    long["unit"] = source.unit
    return long[OUTPUT_COLUMNS].reset_index(drop=True)
