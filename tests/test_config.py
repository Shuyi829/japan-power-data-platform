from pathlib import Path

import pytest

from jpower.config import DEFAULT_CONFIG, load_sources


def test_repo_config_loads():
    assert isinstance(load_sources(DEFAULT_CONFIG), dict)


def test_source_entry_parsed(tmp_path: Path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "sources:\n"
        "  demo:\n"
        "    url_template: https://example.com/{yyyy}.csv\n"
        "    frequency: yearly\n"
        "    encoding: cp932\n"
        "    skip_rows: 1\n"
        "    header_layouts: [[date, period, price]]\n",
        encoding="utf-8",
    )
    demo = load_sources(cfg)["demo"]
    assert demo.encoding == "cp932"
    assert demo.header_layouts == [["date", "period", "price"]]
    assert demo.time_convention == "period_start"


def test_unknown_key_fails_loudly(tmp_path: Path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "sources:\n  demo:\n    url_template: x\n    frequency: daily\n    typo_key: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(TypeError):
        load_sources(cfg)


def test_column_map_key_missing_from_layouts_fails(tmp_path: Path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "sources:\n  demo:\n    url_template: x\n    frequency: daily\n"
        "    header_layouts: [[DATE, TIME, a]]\n    column_map: {a: m1, typo: m2}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="typo"):
        load_sources(cfg)
