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


