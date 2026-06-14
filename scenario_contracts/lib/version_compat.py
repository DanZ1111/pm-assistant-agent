"""Version compatibility helpers for QA harness tests."""
from __future__ import annotations


def app_version_at_least(current: str, minimum: str) -> bool:
    """Return True when a dotted numeric version is >= the minimum."""
    return _parse_version(current) >= _parse_version(minimum)


def _parse_version(value: str) -> tuple[int, ...]:
    parts = []
    for part in value.split("."):
        digits = ""
        for char in part:
            if not char.isdigit():
                break
            digits += char
        parts.append(int(digits or "0"))
    return tuple(parts)
