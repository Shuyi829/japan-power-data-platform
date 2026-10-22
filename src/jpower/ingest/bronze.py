"""Bronze layer: download source files unchanged and record one manifest row per attempt.

Layout (one folder per source and period, one file per distinct download):

    data/bronze/<source>/<period_key>/<downloaded_at>_<filename>

Every attempt writes a row to the DuckDB table ``bronze.manifest``:

    status = 'new'        content differs from the last stored copy -> file written
             'unchanged'  same checksum as the last stored copy      -> no file written
             'error'      HTTP error or network failure              -> exception re-raised

Re-pulling the same period is therefore safe (idempotent), and every revision a source
publishes is kept side by side, so silver can be rebuilt as of any point in time.

Usage:

    uv run python -m jpower.ingest.bronze --source <name> --date 2026-10-01
    uv run python -m jpower.ingest.bronze --source <name> --start 2026-04-01 --end 2026-10-01
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import duckdb
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jpower.config import PROJECT_ROOT, SourceConfig, load_sources

DEFAULT_BRONZE_ROOT = PROJECT_ROOT / "data" / "bronze"
DEFAULT_DB = PROJECT_ROOT / "data" / "japan_power.duckdb"
USER_AGENT = "japan-power-data-platform/0.1 (public-data research project)"

MANIFEST_DDL = """
create schema if not exists bronze;
create table if not exists bronze.manifest (
    source            varchar not null,
    period_key        varchar not null,
    url               varchar not null,
    status            varchar not null,   -- new | unchanged | error
    http_status       integer,
    file_path         varchar,            -- relative to the bronze root
    sha256            varchar,
    bytes             bigint,
    downloaded_at_utc timestamp not null,
    error             varchar
);
"""


class HttpSession(Protocol):
    def get(self, url: str, timeout: float) -> requests.Response: ...


@dataclass(frozen=True)
class ManifestRow:
    source: str
    period_key: str
    url: str
    status: str
    http_status: int | None
    file_path: str | None
    sha256: str | None
    bytes: int | None
    downloaded_at_utc: dt.datetime
    error: str | None = None


def fiscal_year(day: dt.date) -> int:
    """Japanese fiscal year: FY2026 runs from 1 April 2026 to 31 March 2027."""
    return day.year if day.month >= 4 else day.year - 1


def period_key(source: SourceConfig, day: dt.date) -> str:
    if source.frequency == "daily":
        return day.strftime("%Y%m%d")
    if source.frequency == "monthly":
        return day.strftime("%Y%m")
    return str(day.year)


def render_url(source: SourceConfig, day: dt.date) -> str:
    return source.url_template.format(
        yyyymmdd=day.strftime("%Y%m%d"),
        yyyymm=day.strftime("%Y%m"),
        yyyy=day.strftime("%Y"),
        fy=fiscal_year(day),
    )


def periods_between(source: SourceConfig, start: dt.date, end: dt.date) -> list[dt.date]:
    """One representative date per file period from start to end (inclusive)."""
    days: list[dt.date] = []
    seen: set[str] = set()
    day = start
    while day <= end:
        key = period_key(source, day)
        if key not in seen:
            seen.add(key)
            days.append(day)
        day += dt.timedelta(days=1)
    return days


def make_session() -> requests.Session:
    """Session with retries and backoff for flaky public sites (429 and 5xx)."""
    retry = Retry(
        total=4,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def _latest_sha256(con: duckdb.DuckDBPyConnection, source: str, key: str) -> str | None:
    row = con.execute(
        """
        select sha256 from bronze.manifest
        where source = ? and period_key = ? and status = 'new'
        order by downloaded_at_utc desc
        limit 1
        """,
        [source, key],
    ).fetchone()
    return row[0] if row else None


def _insert(con: duckdb.DuckDBPyConnection, row: ManifestRow) -> None:
    con.execute(
        "insert into bronze.manifest values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            row.source,
            row.period_key,
            row.url,
            row.status,
            row.http_status,
            row.file_path,
            row.sha256,
            row.bytes,
            row.downloaded_at_utc,
            row.error,
        ],
    )


def download(
    source: SourceConfig,
    day: dt.date,
    *,
    con: duckdb.DuckDBPyConnection,
    bronze_root: Path = DEFAULT_BRONZE_ROOT,
    session: HttpSession | None = None,
    now: dt.datetime | None = None,
) -> ManifestRow:
    """Download one file for the period containing ``day`` into bronze.

    Raises on HTTP errors after recording an 'error' manifest row, so failures are loud.
    """
    con.execute(MANIFEST_DDL)
    session = session or make_session()
    downloaded_at = (now or dt.datetime.now(dt.UTC)).replace(tzinfo=None)
    key = period_key(source, day)
    url = render_url(source, day)

    def error_row(http_status: int | None, message: str) -> ManifestRow:
        row = ManifestRow(
            source.name, key, url, "error", http_status, None, None, None, downloaded_at, message
        )
        _insert(con, row)
        return row

    try:
        resp = session.get(url, timeout=source.timeout_s)
    except requests.RequestException as exc:
        error_row(None, f"{type(exc).__name__}: {exc}")
        raise
    if resp.status_code != 200:
        error_row(resp.status_code, f"HTTP {resp.status_code}")
        raise RuntimeError(f"{source.name} {key}: HTTP {resp.status_code} for {url}")

    content = resp.content
    sha = hashlib.sha256(content).hexdigest()
    if sha == _latest_sha256(con, source.name, key):
        row = ManifestRow(
            source.name, key, url, "unchanged", 200, None, sha, len(content), downloaded_at
        )
        _insert(con, row)
        return row

    filename = Path(urlparse(url).path).name or "download"
    rel_path = Path(source.name) / key / f"{downloaded_at:%Y%m%dT%H%M%SZ}_{filename}"
    target = bronze_root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)  # raw bytes, original encoding, never modified

    row = ManifestRow(
        source.name, key, url, "new", 200, rel_path.as_posix(), sha, len(content), downloaded_at
    )
    _insert(con, row)
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download source files into bronze.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--date", type=dt.date.fromisoformat, help="single period")
    parser.add_argument("--start", type=dt.date.fromisoformat)
    parser.add_argument("--end", type=dt.date.fromisoformat)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)

    source = load_sources()[args.source]
    if args.date:
        days = [args.date]
    elif args.start and args.end:
        days = periods_between(source, args.start, args.end)
    else:
        parser.error("give --date, or --start and --end")

    args.db.parent.mkdir(parents=True, exist_ok=True)
    failures = 0
    session = make_session()
    with duckdb.connect(str(args.db)) as con:
        for day in days:
            try:
                row = download(source, day, con=con, session=session)
                print(f"{row.period_key}: {row.status} ({row.bytes} bytes)")
            except Exception as exc:  # keep going; every failure is in the manifest
                failures += 1
                print(f"{period_key(source, day)}: FAILED {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
