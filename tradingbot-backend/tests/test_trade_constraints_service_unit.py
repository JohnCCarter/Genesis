import pytest

from config.settings import Settings
from services.trade_constraints import TradeConstraintsService, ConstraintResult


def test_trade_constraints_blocks_when_window_paused(monkeypatch):
    svc = TradeConstraintsService(Settings())
    # is_paused -> True
    monkeypatch.setattr(svc.trading_window, "is_paused", lambda: True)
    res = svc.check(symbol="tBTCUSD")
    assert not res.allowed
    assert res.reason == "trading_paused"


def test_trade_constraints_blocks_on_symbol_daily_limit(monkeypatch):
    svc = TradeConstraintsService(Settings())
    monkeypatch.setattr(svc.trading_window, "is_paused", lambda: False)
    monkeypatch.setattr(svc.trading_window, "is_open", lambda: True)
    # set per-symbol limit = 1 and stats show already 1
    monkeypatch.setattr(svc.trading_window, "get_limits", lambda: {"max_trades_per_symbol_per_day": 1})
    monkeypatch.setattr(svc.trade_counter, "stats", lambda: {"per_symbol": {"TBTCUSD": 1}})
    res = svc.check(symbol="tBTCUSD")
    assert not res.allowed
    assert res.reason == "symbol_daily_trade_limit_reached"


def test_trade_constraints_passes_and_records(monkeypatch):
    svc = TradeConstraintsService(Settings())
    monkeypatch.setattr(svc.trading_window, "is_paused", lambda: False)
    monkeypatch.setattr(svc.trading_window, "is_open", lambda: True)
    monkeypatch.setattr(svc.trading_window, "get_limits", lambda: {"max_trades_per_symbol_per_day": 0})
    monkeypatch.setattr(svc.trade_counter, "can_execute", lambda: True)

    res = svc.check(symbol="tETHUSD")
    assert res.allowed
    called = {}

    def _rec(symbol=None):  # noqa: ANN001
        called["s"] = symbol

    monkeypatch.setattr(svc.trade_counter, "record_trade_for_symbol", _rec)
    svc.record_trade(symbol="tETHUSD")
    assert called.get("s") == "tETHUSD"


def test_trade_constraints_limits(monkeypatch):
    svc = TradeConstraintsService(Settings())
    monkeypatch.setattr(
        svc.trading_window, "get_limits", lambda: {"max_trades_per_day": 3, "trade_cooldown_seconds": 10}
    )
    monkeypatch.setattr(svc.trade_counter, "stats", lambda: {"count": 1, "max_per_day": 3, "cooldown_seconds": 10})
    lim = svc.limits()
    assert lim["max_trades_per_day"] == 3
    st = svc.status()
    assert st["trades"]["max_per_day"] == 3
