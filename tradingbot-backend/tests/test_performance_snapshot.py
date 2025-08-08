import pytest

from services.performance import PerformanceService


class _Wallet:
    def __init__(self, currency: str, balance: float, available_balance: float = 0):
        self.currency = currency
        self.balance = balance
        self.available_balance = available_balance
    def dict(self):
        return {"currency": self.currency, "balance": self.balance}


@pytest.mark.asyncio
async def test_snapshot_includes_realized_and_day_change(monkeypatch):
    perf = PerformanceService()

    # Mock wallets -> 1000 USD
    async def _mock_wallets():
        return [_Wallet("USD", 1000.0)]
    monkeypatch.setattr(perf.wallet_service, "get_wallets", _mock_wallets)

    # Mock positions -> none
    async def _mock_positions():
        return []
    monkeypatch.setattr(perf.positions_service, "get_positions", _mock_positions)

    # Mock realized pnl totals
    async def _mock_realized(limit: int = 1000):
        return {"totals": {"realized_usd": 123.45}}
    monkeypatch.setattr(perf, "compute_realized_pnl", _mock_realized)

    # Ensure clean history
    monkeypatch.setattr(perf, "_load_history", lambda: {"equity": []})
    saved = {}
    monkeypatch.setattr(perf, "_save_history", lambda data: saved.update(data))

    snap = await perf.snapshot_equity()
    assert snap["snapshot"]["realized_usd"] == 123.45
    assert "day_change_usd" in snap["snapshot"]
    assert "realized_day_change_usd" in snap["snapshot"]


