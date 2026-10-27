import datetime as dt
from pathlib import Path

import duckdb
import pytest

from jpower.config import load_sources
from jpower.ingest.bronze import ingest_file
from jpower.load import load_source

FIXTURE = Path(__file__).parent / "fixtures" / "kyushu" / "eria_jukyu_202610_09.csv"
SOURCE = load_sources()["kyushu_area_supply"]
T0 = dt.datetime(2026, 10, 27, 6, 0, 0)
ROWS = 1269 * 18


@pytest.fixture
def con():
    with duckdb.connect(":memory:") as c:
        yield c


def count(con, where: str = "true") -> int:
    return con.execute(f"select count(*) from raw.area_supply where {where}").fetchone()[0]


def store(con, root: Path, content: bytes, at: dt.datetime) -> None:
    local = root / "download" / FIXTURE.name
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(content)
    ingest_file(
        SOURCE, dt.date(2026, 10, 1), local, con=con, bronze_root=root / "bronze", downloaded_at=at
    )


def test_load_is_idempotent(con, tmp_path: Path):
    store(con, tmp_path, FIXTURE.read_bytes(), T0)

    assert list(load_source(con, SOURCE, bronze_root=tmp_path / "bronze").values()) == [ROWS]
    assert load_source(con, SOURCE, bronze_root=tmp_path / "bronze") == {}  # nothing pending
    load_source(con, SOURCE, bronze_root=tmp_path / "bronze", reload=True)
    assert count(con) == ROWS  # replaced, not appended


def test_each_revision_is_kept_with_its_download_time(con, tmp_path: Path):
    original = FIXTURE.read_bytes()
    store(con, tmp_path, original, T0)
    revised = original.replace(b'"20261001","0:30","7784"', b'"20261001","0:30","7790"')
    store(con, tmp_path, revised, T0 + dt.timedelta(hours=3))
    load_source(con, SOURCE, bronze_root=tmp_path / "bronze")

    assert count(con) == 2 * ROWS
    values = con.execute(
        """
        select downloaded_at_utc, value from raw.area_supply
        where metric = 'demand' and period_start_jst = '2026-10-01 00:00' order by 1
        """
    ).fetchall()
    assert [v for _, v in values] == [7784, 7790]


def test_schema_drift_fails_the_load_loudly(con, tmp_path: Path):
    drifted = FIXTURE.read_bytes().replace("地熱".encode("cp932"), "地熱発電".encode("cp932"))
    store(con, tmp_path, drifted, T0)

    with pytest.raises(RuntimeError, match="SchemaMismatchError"):
        load_source(con, SOURCE, bronze_root=tmp_path / "bronze")
    assert count(con) == 0
