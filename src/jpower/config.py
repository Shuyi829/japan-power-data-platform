"""Load per-source reader config from config/sources.yaml.

One generic reader handles every CSV source; what differs per source (URL template,
encoding, rows to skip, expected headers, column map, units, time convention) lives in config.
Adding a source means adding a config entry, not a new class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from jpower.text import normalize

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "sources.yaml"

TimeConvention = Literal["period_start", "period_end"]


@dataclass(frozen=True)
class SourceConfig:
    name: str
    url_template: str
    frequency: Literal["daily", "monthly", "yearly"]
    domain: str = "area_supply"
    encoding: str = "utf-8"
    skip_rows: int = 0
    header_layouts: list[list[str]] = field(default_factory=list)
    time_convention: TimeConvention = "period_start"
    timeout_s: int = 60
    area_code: str | None = None
    date_column: str = "DATE"
    date_formats: list[str] = field(default_factory=lambda: ["%Y%m%d"])
    time_column: str = "TIME"
    unit: str = "MW"
    column_map: dict[str, str] = field(default_factory=dict)


def _check(source: SourceConfig) -> SourceConfig:
    """Config mistakes fail at load time, not halfway through a backfill."""
    known = {normalize(h) for layout in source.header_layouts for h in layout}
    unmapped = [c for c in source.column_map if normalize(c) not in known]
    if unmapped:
        raise ValueError(f"{source.name}: column_map keys not in any header layout: {unmapped}")
    return source


def load_sources(path: Path = DEFAULT_CONFIG) -> dict[str, SourceConfig]:
    """Return source configs keyed by name. Fails loudly on unknown or missing keys."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = raw.get("sources") or {}
    return {name: _check(SourceConfig(name=name, **cfg)) for name, cfg in sources.items()}
