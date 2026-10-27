"""Japanese text helpers shared by config and readers."""

from __future__ import annotations

import unicodedata


def normalize(text: str) -> str:
    """Full-width -> half-width (Ａ→A, （→(, full-width space→space) and trim."""
    return unicodedata.normalize("NFKC", text).strip()
