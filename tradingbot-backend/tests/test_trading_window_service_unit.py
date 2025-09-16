import os
from datetime import datetime, time

import pytest

from config.settings import Settings
from services.trading_window import TradingWindowService, WEEKDAY_KEYS


def _today_daykey(now: datetime) -> str:
    return WEEKDAY_KEYS[now.weekday()]


def _rules_path(tmp_path):
    return str(tmp_path / "trading_rules.json")


def test_trading_window_defaults_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADING_RULES_FILE", _rules_path(tmp_path))
    s = Settings()
    tw = TradingWindowService(s)
    assert tw.is_open(now=datetime.utcnow()) is False


def test_trading_window_open_after_setting_window(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADING_RULES_FILE", _rules_path(tmp_path))
    s = Settings()
    tw = TradingWindowService(s)
    now = datetime.utcnow()
    daykey = _today_daykey(now)
    # Öppna hela dagen
    windows = {daykey: [("00:00", "23:59")]}
    tw.save_rules(windows=windows, paused=False)
    assert tw.is_open(now=now) is True


def test_trading_window_pause(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADING_RULES_FILE", _rules_path(tmp_path))
    s = Settings()
    tw = TradingWindowService(s)
    now = datetime.utcnow()
    daykey = _today_daykey(now)
    tw.save_rules(windows={daykey: [("00:00", "23:59")]}, paused=True)
    assert tw.is_open(now=now) is False
    tw.set_paused(False)
    assert tw.is_open(now=now) is True


def test_trading_window_persist_reload(tmp_path, monkeypatch):
    path = _rules_path(tmp_path)
    monkeypatch.setenv("TRADING_RULES_FILE", path)
    s = Settings()
    tw = TradingWindowService(s)
    now = datetime.utcnow()
    daykey = _today_daykey(now)
    tw.save_rules(
        windows={daykey: [("08:00", "17:00")]}, paused=False, max_trades_per_day=7
    )
    # Ny instans läser från fil
    tw2 = TradingWindowService(Settings())
    assert tw2.get_limits()["max_trades_per_day"] == 7
    # Tid inom fönstret
    within = now.replace(hour=9, minute=0)
    assert tw2.is_open(now=within) is True
    # Tid utanför fönstret
    outside = now.replace(hour=20, minute=0)
    assert tw2.is_open(now=outside) is False
