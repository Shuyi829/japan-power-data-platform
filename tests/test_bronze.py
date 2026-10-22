import datetime as dt
from pathlib import Path

import duckdb
import pytest
import requests

from jpower.config import SourceConfig
from jpower.ingest.bronze import download, fiscal_year, periods_between, render_url

MONTHLY = SourceConfig(
    name="demo", url_template="https://example.com/data_{yyyymm}.csv", frequency="monthly"
)
T0 = dt.datetime(2026, 10, 22, 3, 0, 0)


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code


class FakeSession:
    """Returns queued responses (or raises queued exceptions) in order."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.urls: list[str] = []

    def get(self, url, timeout):
        self.urls.append(url)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def con():
    with duckdb.connect(":memory:") as c:
        yield c


def manifest(con):
    return con.execute(
        "select status, http_status, file_path from bronze.manifest order by downloaded_at_utc"
    ).fetchall()


def test_fiscal_year_starts_in_april():
    assert fiscal_year(dt.date(2026, 3, 31)) == 2025
    assert fiscal_year(dt.date(2026, 4, 1)) == 2026


def test_render_url_placeholders():
    src = SourceConfig(
        name="x", url_template="https://e.com/{yyyy}/{yyyymm}/{yyyymmdd}_{fy}", frequency="daily"
    )
    assert render_url(src, dt.date(2026, 2, 5)) == "https://e.com/2026/202602/20260205_2025"


def test_periods_between_one_date_per_month():
    days = periods_between(MONTHLY, dt.date(2026, 1, 15), dt.date(2026, 3, 1))
    assert [d.strftime("%Y%m") for d in days] == ["202601", "202602", "202603"]


def test_new_download_writes_raw_bytes_and_manifest(con, tmp_path: Path):
    raw = "日付,価格\n".encode("cp932")  # stored as-is, never re-encoded
    session = FakeSession(FakeResponse(raw))
    row = download(
        MONTHLY, dt.date(2026, 10, 1), con=con, bronze_root=tmp_path, session=session, now=T0
    )

    assert session.urls == ["https://example.com/data_202610.csv"]
    assert row.status == "new"
    assert row.file_path == "demo/202610/20261022T030000Z_data_202610.csv"
    assert (tmp_path / row.file_path).read_bytes() == raw
    assert manifest(con) == [("new", 200, row.file_path)]


def test_same_content_is_unchanged_and_not_stored_twice(con, tmp_path: Path):
    session = FakeSession(FakeResponse(b"a,b\n1,2\n"), FakeResponse(b"a,b\n1,2\n"))
    day = dt.date(2026, 10, 1)
    download(MONTHLY, day, con=con, bronze_root=tmp_path, session=session, now=T0)
    row = download(
        MONTHLY, day, con=con, bronze_root=tmp_path, session=session, now=T0 + dt.timedelta(hours=1)
    )

    assert row.status == "unchanged"
    assert row.file_path is None
    assert len(list(tmp_path.rglob("*.csv"))) == 1


def test_revised_content_is_kept_side_by_side(con, tmp_path: Path):
    session = FakeSession(FakeResponse(b"v1"), FakeResponse(b"v2"))
    day = dt.date(2026, 10, 1)
    download(MONTHLY, day, con=con, bronze_root=tmp_path, session=session, now=T0)
    download(
        MONTHLY, day, con=con, bronze_root=tmp_path, session=session, now=T0 + dt.timedelta(hours=1)
    )

    assert [r[0] for r in manifest(con)] == ["new", "new"]
    assert len(list(tmp_path.rglob("*.csv"))) == 2


def test_http_error_is_recorded_and_raised(con, tmp_path: Path):
    session = FakeSession(FakeResponse(b"not found", status_code=404))
    with pytest.raises(RuntimeError, match="HTTP 404"):
        download(
            MONTHLY, dt.date(2026, 10, 1), con=con, bronze_root=tmp_path, session=session, now=T0
        )

    assert manifest(con) == [("error", 404, None)]
    assert not list(tmp_path.rglob("*.csv"))


def test_network_failure_is_recorded_and_raised(con, tmp_path: Path):
    session = FakeSession(requests.ConnectionError("timed out"))
    with pytest.raises(requests.ConnectionError):
        download(
            MONTHLY, dt.date(2026, 10, 1), con=con, bronze_root=tmp_path, session=session, now=T0
        )

    assert manifest(con) == [("error", None, None)]
