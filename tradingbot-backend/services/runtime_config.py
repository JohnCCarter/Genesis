"""
Runtime Config Service

Enkel in‑memory override-butik för att hot‑reloada vissa inställningar utan omstart.

API:
- set_override(key, value)
- set_overrides(dict)
- get_str/int/float/bool(key, fallback)
- current()
"""

# AI Change: Add runtime_config helpers for runtime flags (Agent: Codex, Date: 2025-09-11)
from __future__ import annotations

import os
from typing import Any

from config.settings import Settings

# Processlokal cache för write-through uppdateringar (påverkar inte .env)
_runtime_overrides: dict[str, Any] = {}


def set_str(key: str, value: str) -> None:
    _runtime_overrides[key] = str(value)
    os.environ[key] = str(value)


def set_bool(key: str, value: bool) -> None:
    _runtime_overrides[key] = bool(value)
    os.environ[key] = "True" if bool(value) else "False"


def set_int(key: str, value: int) -> None:
    _runtime_overrides[key] = int(value)
    os.environ[key] = str(int(value))


def set_float(key: str, value: float) -> None:
    _runtime_overrides[key] = float(value)
    os.environ[key] = str(float(value))


def get_str(key: str, default: str | None = None) -> str | None:
    if key in _runtime_overrides:
        return str(_runtime_overrides[key])
    return str(getattr(Settings(), key, default)) if hasattr(Settings(), key) else default


def get_bool(key: str, default: bool | None = None) -> bool:
    if key in _runtime_overrides:
        return bool(_runtime_overrides[key])
    val = getattr(Settings(), key, default)
    return bool(val) if val is not None else False


def get_int(key: str, default: int | None = None) -> int:
    if key in _runtime_overrides:
        return int(_runtime_overrides[key])
    val = getattr(Settings(), key, default)
    try:
        return int(val) if val is not None else int(default or 0)
    except Exception:
        return int(default or 0)


def get_float(key: str, default: float | None = None) -> float:
    if key in _runtime_overrides:
        return float(_runtime_overrides[key])
    val = getattr(Settings(), key, default)
    try:
        return float(val) if val is not None else float(default or 0.0)
    except Exception:
        return float(default or 0.0)
