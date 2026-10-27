"""Generic config-driven CSV reader: raw bronze bytes -> long, typed rows.

Every source-specific detail (encoding, rows to skip, expected headers, column map,
time convention, unit) comes from SourceConfig. Steps:

1. decode with the configured encoding (e.g. cp932)
2. normalize headers full-width -> half-width (NFKC) and validate against the known
   ``header_layouts`` -> SchemaMismatchError on any other layout (no silent column shifts)
3. build ``period_start`` in JST (and UTC): period-ending labels such as "24:00" are
   shifted back 30 minutes, so 24:00 on 1 Oct becomes 23:30 on 1 Oct
4. melt mapped columns into one row per (period, metric); values that are blank or
   unparseable become NULL with a quality flag, never a sentinel
"""

from __future__ import annotations

import datetime as dt
import io

import pandas as pd

from jpower.config import SourceConfig
from jpower.text import normalize

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


def validate_headers(source: SourceConfig, headers: list[str]) -> None:
    """Headers must match one of the source's known layouts exactly (after normalization).

    A source can publish more than one layout over time (e.g. columns added in a new
    fiscal year). Each layout is listed explicitly in config; anything else fails.
    """
    layouts = [[normalize(h) for h in layout] for layout in source.header_layouts]
    if headers in layouts:
        return

    def diff(layout: list[str]) -> tuple[list[str], list[str]]:
        return [h for h in layout if h not in headers], [h for h in headers if h not in layout]

    closest = min(layouts, key=lambda lay: sum(map(len, diff(lay))), default=[])
    missing, unexpected = diff(closest)
    if missing or unexpected:
        detail = f"vs closest known layout: missing [{', '.join(missing)}], "
        detail += f"unexpected [{', '.join(unexpected)}]"
    else:
        detail = "same columns as a known layout, different order"
    raise SchemaMismatchError(
        f"{source.name}: header mismatch ({detail}); got [{', '.join(headers)}]"
    )


def _period_start(source: SourceConfig, dates: pd.Series, times: pd.Series) -> pd.Series:
    day = pd.Series(pd.NaT, index=dates.index, dtype="datetime64[ns]")
    for fmt in source.date_formats:  # e.g. 20251201 in most files, 2025/12/1 in some
        todo = day.isna()
        day[todo] = pd.to_datetime(dates[todo], format=fmt, errors="coerce")
    if day.isna().any():
        bad = dates[day.isna()].unique()[:5].tolist()
        raise ValueError(f"{source.name}: dates match none of {source.date_formats}: {bad}")
    hm = times.str.extract(r"^\s*(\d{1,2}):(\d{2})(?::00)?\s*$")  # 0:30, 24:00, 24:00:00
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
    present = [c for c in source.column_map if c in df.columns]  # layouts differ per period
    wide = df[present].rename(columns=source.column_map)
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
