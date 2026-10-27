"""Export a gold table to CSV (UTF-8, header row) under data/exports/.

Usage:

    uv run python -m jpower.export --table gold.kyushu_demand_30min
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import duckdb

from jpower.config import PROJECT_ROOT
from jpower.ingest.bronze import DEFAULT_DB

DEFAULT_EXPORT_DIR = PROJECT_ROOT / "data" / "exports"
TABLE_NAME = re.compile(r"^gold\.[a-z0-9_]+$")  # only gold marts are exported


def export_table(con: duckdb.DuckDBPyConnection, table: str, out_dir: Path) -> Path:
    if not TABLE_NAME.fullmatch(table):
        raise ValueError(f"not a gold table name: {table!r}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{table.split('.', 1)[1]}.csv"
    con.execute(f"copy (select * from {table}) to '{out.as_posix()}' (header, delimiter ',')")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a gold table to CSV.")
    parser.add_argument("--table", required=True, help="e.g. gold.kyushu_demand_30min")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    args = parser.parse_args(argv)

    with duckdb.connect(str(args.db), read_only=True) as con:
        out = export_table(con, args.table, args.out_dir)
        rows = con.execute(f"select count(*) from {args.table}").fetchone()[0]
    print(f"{out}: {rows} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
