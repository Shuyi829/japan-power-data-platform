from pathlib import Path

import duckdb
import pytest

from jpower.export import export_table


def test_export_writes_csv_named_after_table(tmp_path: Path):
    with duckdb.connect(":memory:") as con:
        con.execute("create schema gold; create table gold.demo as select 1 as a, 'x' as b")
        out = export_table(con, "gold.demo", tmp_path)
    assert out == tmp_path / "demo.csv"
    assert out.read_text().splitlines() == ["a,b", "1,x"]


@pytest.mark.parametrize("name", ["silver.area_supply", "gold.demo; drop table x", "demo"])
def test_only_gold_tables_can_be_exported(name, tmp_path: Path):
    with duckdb.connect(":memory:") as con, pytest.raises(ValueError):
        export_table(con, name, tmp_path)
