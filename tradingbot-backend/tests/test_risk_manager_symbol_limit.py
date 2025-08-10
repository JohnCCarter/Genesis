from services.risk_manager import RiskManager


def test_symbol_daily_limit_blocks(monkeypatch):
    rm = RiskManager()
    # Tillåt handel i testet
    monkeypatch.setattr(rm.trading_window, "is_paused", lambda: False)
    monkeypatch.setattr(rm.trading_window, "is_open", lambda: True)
    # Sätt per-symbol max till 1 via trading window rules
    rm.trading_window.save_rules(max_trades_per_symbol_per_day=1)
    # Tillåt omedelbara trades (bypassa cooldown/daglig limit i testet)
    monkeypatch.setattr(rm.trade_counter, "can_execute", lambda: True)
    # Nollställ eventuellt persisterad per-symbol state
    rm.trade_counter.symbol_counts = {}

    # Första trade ska passera
    ok, reason = rm.pre_trade_checks(symbol="tBTCUSD")
    assert ok is True
    rm.record_trade(symbol="tBTCUSD")

    # Andra trade ska blockeras
    ok, reason = rm.pre_trade_checks(symbol="tBTCUSD")
    assert ok is False and reason == "symbol_daily_trade_limit_reached"
