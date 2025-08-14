from services.risk_manager import RiskManager


def test_risk_manager_paused_blocks(monkeypatch):
    rm = RiskManager()
    monkeypatch.setattr(rm.trading_window, "is_paused", lambda: True)
    ok, reason = rm.pre_trade_checks()
    assert ok is False and reason == "trading_paused"


def test_risk_manager_window_blocks(monkeypatch):
    rm = RiskManager()
    monkeypatch.setattr(rm.trading_window, "is_paused", lambda: False)
    monkeypatch.setattr(rm.trading_window, "is_open", lambda: False)
    ok, reason = rm.pre_trade_checks()
    assert ok is False and reason == "outside_trading_window"


import asyncio
import json
from typing import Any, Dict

import pytest


def _write_rules(path: str, *, paused: bool = False) -> None:
    data: Dict[str, Any] = {
        "timezone": "UTC",
        "windows": {
            d: [["00:00", "23:59"]]
            for d in [
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
                "sat",
                "sun",
            ]
        },
        "max_trades_per_day": 1000,
        "trade_cooldown_seconds": 0,
        "paused": paused,
        "max_trades_per_symbol_per_day": 0,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


@pytest.mark.asyncio
async def test_circuit_breaker_opens_and_notifies(tmp_path, monkeypatch):
    from config.settings import Settings
    from services.notifications import notification_service

    rules_path = tmp_path / "trading_rules.json"
    _write_rules(str(rules_path), paused=False)

    s = Settings()
    # Styr filväg + CB-parametrar så vi inte skriver i repo-filer
    s.TRADING_RULES_FILE = str(rules_path)
    s.CB_ENABLED = True
    s.CB_ERROR_WINDOW_SECONDS = 60
    s.CB_MAX_ERRORS_PER_WINDOW = 2
    s.CB_NOTIFY = True

    rm = RiskManager(s)

    calls = []

    async def fake_notify(level: str, title: str, payload: Dict[str, Any] | None = None):
        calls.append({"level": level, "title": title, "payload": payload or {}})

    # Patcha notiser för att verifiera att create_task körs
    monkeypatch.setattr(notification_service, "notify", fake_notify)

    # Trigga fel två gånger för att öppna CB
    rm.record_error()
    rm.record_error()

    # Låt eventloopen köra schemalagda tasks
    await asyncio.sleep(0)

    assert rm.trading_window.is_paused() is True
    st = rm.status()
    assert st["circuit"]["opened_at"] is not None

    # Verifiera notifiering
    assert any(c.get("title") == "Circuit breaker aktiverad" for c in calls)


def test_circuit_breaker_reset_resumes(tmp_path):
    from config.settings import Settings

    rules_path = tmp_path / "trading_rules.json"
    _write_rules(str(rules_path), paused=False)

    s = Settings()
    s.TRADING_RULES_FILE = str(rules_path)
    s.CB_ENABLED = True
    s.CB_ERROR_WINDOW_SECONDS = 60
    s.CB_MAX_ERRORS_PER_WINDOW = 1
    s.CB_NOTIFY = False

    rm = RiskManager(s)

    # Öppna CB
    rm.record_error()
    assert rm.trading_window.is_paused() is True

    # Återställ (ska återuppta handel och rensa fel)
    out = rm.circuit_reset(resume=True, clear_errors=True, notify=False)
    assert rm.trading_window.is_paused() is False
    assert out["circuit"]["opened_at"] is None
    assert out["circuit"]["errors_in_window"] == 0
