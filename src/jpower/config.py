"""Load per-source reader config from config/sources.yaml.

One generic reader handles every CSV source; what differs per source (URL template,
encoding, rows to skip, expected headers, time convention) lives in config.
Adding a source means adding a config entry, not a new class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "sources.yaml"

TimeConvention = Literal["period_start", "period_end"]


@dataclass(frozen=True)
class SourceConfig:
    name: str
    url_template: str
    frequency: Literal["daily", "monthly", "yearly"]
    encoding: str = "utf-8"
    skip_rows: int = 0
    expected_headers: list[str] = field(default_factory=list)
    time_convention: TimeConvention = "period_start"
    timeout_s: int = 60


def load_sources(path: Path = DEFAULT_CONFIG) -> dict[str, SourceConfig]:
    """Return source configs keyed by name. Fails loudly on unknown or missing keys."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = raw.get("sources") or {}
    return {name: SourceConfig(name=name, **cfg) for name, cfg in sources.items()}
