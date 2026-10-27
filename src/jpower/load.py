"""Load bronze files into the warehouse: parse every new file into raw.<domain>.

raw.<domain> holds every parsed row from every stored file version, tagged with the
file it came from and when that file was downloaded. Picking the latest revision per
half hour is a dbt (silver) concern, so any point-in-time view can be rebuilt.

Loading is idempotent: a file's rows are replaced, never appended twice, and files
already in raw are skipped unless --reload is given.

Usage:

    uv run python -m jpower.load --source kyushu_area_supply
    uv run python -m jpower.load --init        # create empty raw tables (used by CI)
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import duckdb

from jpower.config import SourceConfig, load_sources
from jpower.ingest.bronze import DEFAULT_BRONZE_ROOT, DEFAULT_DB, MANIFEST_DDL
from jpower.readers.csv_reader import parse_csv

RAW_DDL = """
create schema if not exists raw;
create table if not exists raw.{domain} (
    source            varchar   not null,
    area_code         varchar,
    period_start_jst  timestamp not null,
    period_start_utc  timestamp not null,
    metric            varchar   not null,
    value             double,
    unit              varchar   not null,
    quality_flag      varchar   not null,   -- ok | missing | invalid
    file_path         varchar   not null,   -- bronze file the row was parsed from
    downloaded_at_utc timestamp not null,   -- when that file version was fetched
    loaded_at_utc     timestamp not null
);
"""


def init_tables(con: duckdb.DuckDBPyConnection, domains: set[str]) -> None:
    con.execute(MANIFEST_DDL)
    for domain in sorted(domains):
        con.execute(RAW_DDL.format(domain=domain))


def pending_files(
    con: duckdb.DuckDBPyConnection, source: SourceConfig, reload: bool = False
) -> list[tuple[str, dt.datetime]]:
    """Stored bronze files (status 'new') for a source not yet in raw, oldest first."""
    already = "" if reload else f"and file_path not in (select file_path from raw.{source.domain})"
    return con.execute(
        f"""
        select file_path, downloaded_at_utc from bronze.manifest
        where source = ? and status = 'new' {already}
        order by downloaded_at_utc
        """,
        [source.name],
    ).fetchall()


def load_file(
    con: duckdb.DuckDBPyConnection,
    source: SourceConfig,
    file_path: str,
    downloaded_at: dt.datetime,
    *,
    bronze_root: Path = DEFAULT_BRONZE_ROOT,
) -> int:
    """Parse one bronze file and replace its rows in raw.<domain>. Returns row count."""
    df = parse_csv(source, (bronze_root / file_path).read_bytes())
    df["file_path"] = file_path
    df["downloaded_at_utc"] = downloaded_at
    df["loaded_at_utc"] = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    table = f"raw.{source.domain}"
    con.execute("begin")
    try:
        con.execute(f"delete from {table} where file_path = ?", [file_path])
        con.register("parsed", df)
        con.execute(f"insert into {table} by name select * from parsed")
        con.unregister("parsed")
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise
    return len(df)


def load_source(
    con: duckdb.DuckDBPyConnection,
    source: SourceConfig,
    *,
    bronze_root: Path = DEFAULT_BRONZE_ROOT,
    reload: bool = False,
) -> dict[str, int]:
    """Load all pending files for a source. Raises after trying every file if any failed."""
    init_tables(con, {source.domain})
    loaded: dict[str, int] = {}
    errors: list[str] = []
    for file_path, downloaded_at in pending_files(con, source, reload):
        try:
            loaded[file_path] = load_file(
                con, source, file_path, downloaded_at, bronze_root=bronze_root
            )
        except Exception as exc:  # e.g. SchemaMismatchError: keep going, then fail loudly
            errors.append(f"{file_path}: {type(exc).__name__}: {exc}")
    if errors:
        raise RuntimeError(f"{len(errors)} file(s) failed to load:\n" + "\n".join(errors))
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load bronze files into raw tables.")
    parser.add_argument("--source", help="source name from config/sources.yaml")
    parser.add_argument("--init", action="store_true", help="only create empty tables")
    parser.add_argument("--reload", action="store_true", help="re-parse already loaded files")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)

    sources = load_sources()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(args.db)) as con:
        if args.init:
            init_tables(con, {s.domain for s in sources.values()})
            print("tables created")
            return 0
        if not args.source:
            parser.error("give --source, or --init")
        try:
            loaded = load_source(con, sources[args.source], reload=args.reload)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 1
    for file_path, rows in loaded.items():
        print(f"{file_path}: {rows} rows")
    print(f"{len(loaded)} file(s) loaded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
