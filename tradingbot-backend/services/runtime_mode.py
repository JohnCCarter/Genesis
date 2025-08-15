"""
Runtime mode controller for switching Core Mode on/off at runtime.

Core Mode = minimal features enabled for simpler live running.
This module only stores process-local state; callers are responsible
for applying operational effects (e.g., stopping scheduler).
"""

from __future__ import annotations

from typing import Optional, Tuple

from config.settings import Settings

# Process-local core mode flag (default from Settings at startup)
_CORE_MODE: bool = bool(Settings().CORE_MODE)
_WS_STRATEGY_ENABLED: bool = True
_VALIDATION_ON_START: bool = False
_WS_CONNECT_ON_START: bool = False

# Previous values to restore when leaving core mode
_PREV_RATE_LIMIT: tuple[int, int] | None = None  # (max, window)


def get_core_mode() -> bool:
    return bool(_CORE_MODE)


def set_core_mode(value: bool) -> None:
    global _CORE_MODE
    _CORE_MODE = bool(value)


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


def set_prev_rate_limit(max_requests: int, window_seconds: int) -> None:
    global _PREV_RATE_LIMIT
    _PREV_RATE_LIMIT = (int(max_requests or 0), int(window_seconds or 0))


def get_prev_rate_limit() -> tuple[int, int] | None:
    return _PREV_RATE_LIMIT


def get_ws_connect_on_start() -> bool:
    return bool(_WS_CONNECT_ON_START)


def set_ws_connect_on_start(value: bool) -> None:
    global _WS_CONNECT_ON_START
    _WS_CONNECT_ON_START = bool(value)
