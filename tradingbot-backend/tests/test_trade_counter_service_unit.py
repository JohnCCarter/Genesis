import time
from datetime import datetime, timedelta

import pytest

from config.settings import Settings
from services.trade_counter import TradeCounterService, TradeCounterState


def _reset_fresh(tc: TradeCounterService):
    tc.state = TradeCounterState(day=tc._today())
    tc.symbol_counts = {}


def test_trade_counter_max_per_day_blocks(monkeypatch):
    s = Settings()
    tc = TradeCounterService(s)
    # Isolera fil-I/O och limits
    monkeypatch.setattr(tc, "_save_state", lambda: None)
    _reset_fresh(tc)
    monkeypatch.setattr(tc, "_cooldown_seconds_current", lambda: 0)
    monkeypatch.setattr(tc, "_max_per_day_current", lambda: 2)

    assert tc.can_execute() is True
    tc.record_trade()
    assert tc.can_execute() is True
    tc.record_trade()
    # Efter två trades blockeras tredje
    assert tc.can_execute() is False


def test_trade_counter_cooldown_blocks(monkeypatch):
    s = Settings()
    tc = TradeCounterService(s)
    monkeypatch.setattr(tc, "_save_state", lambda: None)
    _reset_fresh(tc)
    monkeypatch.setattr(tc, "_max_per_day_current", lambda: 100)
    monkeypatch.setattr(tc, "_cooldown_seconds_current", lambda: 5)

    assert tc.can_execute() is True
    tc.record_trade()
    # Direkt efter trade ska cooldown blockera
    assert tc.can_execute() is False


def test_trade_counter_per_symbol(monkeypatch):
    s = Settings()
    tc = TradeCounterService(s)
    monkeypatch.setattr(tc, "_save_state", lambda: None)
    _reset_fresh(tc)
    monkeypatch.setattr(tc, "_max_per_day_current", lambda: 100)
    monkeypatch.setattr(tc, "_cooldown_seconds_current", lambda: 0)

    tc.record_trade_for_symbol("tBTCUSD")
    tc.record_trade_for_symbol("tBTCUSD")
    st = tc.stats()
    assert st["per_symbol"].get("TBTCUSD") == 2
