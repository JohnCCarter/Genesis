import asyncio
import os

import pytest

os.environ.setdefault("AUTH_REQUIRED", "False")
os.environ.setdefault("PROB_VALIDATE_ENABLED", "True")


@pytest.mark.asyncio
async def test_scheduler_prob_validation_updates_metrics(monkeypatch):
    from services.scheduler import SchedulerService
    from services.metrics import metrics_store

    # Monkeypatch get_candles to return small deterministic data
    async def fake_candles(self, symbol: str, timeframe: str, limit: int):
        # 30 increasing candles
        base = 100.0
        arr = []
        for i in range(30):
            px = base + i * 0.1
            arr.append([0, 0, px, px, px, 1])
        return arr

    monkeypatch.setattr("services.bitfinex_data.BitfinexDataService.get_candles", fake_candles)

    sch = SchedulerService()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    await sch._maybe_run_prob_validation(now)

    pv = metrics_store.get("prob_validation", {})
    # Efter körning ska antingen aggregat eller by finnas
    assert "brier" in pv or "by" in pv
