"""
Runtime mode helpers for runtime toggles (WS strategy, validation, WS connect).
State is process‑local; callers apply operational effects.
"""

from __future__ import annotations

# Intentionally minimal dependencies; no external imports needed

_WS_STRATEGY_ENABLED: bool = False
_VALIDATION_ON_START: bool = False
_WS_CONNECT_ON_START: bool = False


def get_ws_strategy_enabled() -> bool:
    return bool(_WS_STRATEGY_ENABLED)


def set_ws_strategy_enabled(value: bool) -> None:
    global _WS_STRATEGY_ENABLED
    _WS_STRATEGY_ENABLED = bool(value)


def get_validation_on_start() -> bool:
    return bool(_VALIDATION_ON_START)


def set_validation_on_start(value: bool) -> None:
    global _VALIDATION_ON_START
    _VALIDATION_ON_START = bool(value)


def get_ws_connect_on_start() -> bool:
    return bool(_WS_CONNECT_ON_START)


def set_ws_connect_on_start(value: bool) -> None:
    global _WS_CONNECT_ON_START
    _WS_CONNECT_ON_START = bool(value)
