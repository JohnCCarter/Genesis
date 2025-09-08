"""
Runtime Config Service

Enkel in‑memory override-butik för att hot‑reloada vissa inställningar utan omstart.

API:
- set_override(key, value)
- set_overrides(dict)
- get_str/int/float/bool(key, fallback)
- current()
"""

from __future__ import annotations

from typing import Any

_overrides: dict[str, Any] = {}


def set_override(key: str, value: Any) -> None:
    _overrides[str(key)] = value


def set_overrides(values: dict[str, Any]) -> None:
    for k, v in (values or {}).items():
        set_override(str(k), v)


def clear_override(key: str) -> None:
    _overrides.pop(str(key), None)


def current() -> dict[str, Any]:
    return dict(_overrides)


def get_str(key: str, fallback: str | None = None) -> str | None:
    if key in _overrides:
        val = _overrides[key]
        return str(val) if val is not None else None
    return fallback


def _to_int(val: Any) -> int:
    try:
        return int(float(val))
    except Exception:
        return 0


def _to_float(val: Any) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def _to_bool(val: Any) -> bool:
    s = str(val).strip().lower()
    return s in ("1", "true", "yes", "on")


def get_int(key: str, fallback: int) -> int:
    if key in _overrides:
        return _to_int(_overrides[key])
    return int(fallback)


def get_float(key: str, fallback: float) -> float:
    if key in _overrides:
        return _to_float(_overrides[key])
    return float(fallback)


def get_bool(key: str, fallback: bool) -> bool:
    if key in _overrides:
        return _to_bool(_overrides[key])
    return bool(fallback)
