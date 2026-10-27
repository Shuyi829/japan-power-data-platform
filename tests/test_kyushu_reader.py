"""Kyushu TSO area supply CSV, parsed with the generic reader and the repo config."""

import dataclasses
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from jpower.config import load_sources
from jpower.readers.csv_reader import SchemaMismatchError, parse_csv

FIXTURE = Path(__file__).parent / "fixtures" / "kyushu" / "eria_jukyu_202610_09.csv"
SOURCE = load_sources()["kyushu_area_supply"]
HEADER = FIXTURE.read_bytes().decode("cp932").splitlines()[:2]


def synthetic(*rows: str, header: list[str] = HEADER) -> bytes:
    """Small file in the same format as the real one (cp932, unit line, header line)."""
    return "\r\n".join([*header, *rows]).encode("cp932")


def row(date: str, time: str, demand: str = "8000") -> str:
    values = [demand, *["0"] * 16, demand]  # 18 value columns
    return ",".join(f'"{v}"' for v in [date, time, *values])


@pytest.fixture(scope="module")
def parsed() -> pd.DataFrame:
    return parse_csv(SOURCE, FIXTURE.read_bytes())


def test_fixture_shape_and_flags(parsed):
    assert len(parsed) == 1269 * 18  # 26 full days + 21 periods, 18 metrics
    assert set(parsed["quality_flag"]) == {"ok"}
    assert set(parsed["area_code"]) == {"KYS"}
    assert set(parsed["unit"]) == {"MW"}
    assert not parsed.duplicated(["period_start_jst", "metric"]).any()


def test_period_end_labels_become_period_start(parsed):
    demand = parsed[parsed["metric"] == "demand"].set_index("period_start_jst")["value"]
    assert demand.index.min() == pd.Timestamp("2026-10-01 00:00")  # label 0:30
    assert demand[pd.Timestamp("2026-10-01 00:00")] == 7784
    assert demand[pd.Timestamp("2026-10-01 23:30")] == 8412  # label 24:00, same day
    assert demand[pd.Timestamp("2026-10-02 00:00")] == 8018  # next day's 0:30


def test_utc_is_jst_minus_nine_hours(parsed):
    diff = parsed["period_start_jst"] - parsed["period_start_utc"]
    assert (diff == pd.Timedelta(hours=9)).all()


def test_half_hours_are_contiguous(parsed):
    periods = parsed.loc[parsed["metric"] == "demand", "period_start_jst"].sort_values()
    assert (periods.diff().dropna() == pd.Timedelta(minutes=30)).all()


def test_supply_balance_identity(parsed):
    """total = generation + storage + other - net export (curtailment excluded).

    Holds exactly in the public file; a future dbt test will check it on every load.
    """
    wide = parsed.pivot(index="period_start_jst", columns="metric", values="value")
    parts = [
        "nuclear", "thermal_lng", "thermal_coal", "thermal_oil", "thermal_other", "hydro",
        "geothermal", "biomass", "solar", "wind", "pumped_storage", "battery", "other",
    ]  # fmt: skip
    balance = wide[parts].sum(axis=1) - wide["interconnector_net_export"]
    assert (balance == wide["total_supply"]).all()


def test_renamed_column_fails_loudly():
    header = [HEADER[0], HEADER[1].replace("地熱", "地熱発電")]
    with pytest.raises(SchemaMismatchError, match="missing=\\['地熱'\\]"):
        parse_csv(SOURCE, synthetic(row("20261001", "0:30"), header=header))


def test_inserted_column_fails_instead_of_shifting_values():
    header = [HEADER[0], HEADER[1].replace('"水力"', '"火力（バイオ混焼）","水力"')]
    with pytest.raises(SchemaMismatchError, match="unexpected"):
        parse_csv(SOURCE, synthetic(row("20261001", "0:30"), header=header))


def test_full_width_headers_are_normalized():
    # The real file writes 火力（ＬＮＧ） in full width; config uses half width.
    assert "（ＬＮＧ）" in HEADER[1]
    out = parse_csv(SOURCE, synthetic(row("20261001", "0:30")))
    assert "thermal_lng" in set(out["metric"])


def test_blank_and_garbage_values_become_null_with_flag():
    out = parse_csv(
        SOURCE, synthetic(row("20261001", "0:30", demand=""), row("20261001", "1:00", "n/a"))
    )
    demand = out[out["metric"] == "demand"].set_index("period_start_jst")
    assert demand.loc[pd.Timestamp("2026-10-01 00:00"), "quality_flag"] == "missing"
    assert demand.loc[pd.Timestamp("2026-10-01 00:30"), "quality_flag"] == "invalid"
    assert demand["value"].isna().all()


def test_period_start_convention_is_not_shifted():
    src = dataclasses.replace(SOURCE, time_convention="period_start")
    out = parse_csv(src, synthetic(row("20261001", "0:30")))
    assert out["period_start_jst"].iloc[0] == dt.datetime(2026, 10, 1, 0, 30)


def test_bad_time_label_fails():
    with pytest.raises(ValueError, match="unparseable time"):
        parse_csv(SOURCE, synthetic(row("20261001", "0時30分")))
