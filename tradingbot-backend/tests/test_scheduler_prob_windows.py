import os
import pytest


@pytest.mark.asyncio
async def test_scheduler_prob_rolling_windows_retention(monkeypatch):
    os.environ.setdefault("AUTH_REQUIRED", "False")
    os.environ.setdefault("PROB_VALIDATE_ENABLED", "True")
    os.environ.setdefault("PROB_VALIDATE_WINDOWS_MINUTES", "1,5")
    os.environ.setdefault("PROB_VALIDATE_HISTORY_MAX_POINTS", "3")

    from services.scheduler import SchedulerService
    from services.metrics import metrics_store

    # mocka candles
    async def fake_candles(self, symbol: str, timeframe: str, limit: int):
        base = 100.0
        return [[0, 0, base + i * 0.1, base + i * 0.2, base, 1] for i in range(60)]

    monkeypatch.setattr(
        "services.bitfinex_data.BitfinexDataService.get_candles", fake_candles
    )

    sch = SchedulerService()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    # Kör validering flera gånger för att fylla rullande fönster
    for _ in range(5):
        await sch._maybe_run_prob_validation(now)

    rolling = metrics_store.get("prob_validation", {}).get("rolling", {})
    # Varje fönster ska finnas och inte ha fler än max-punkter
    for key, series in rolling.items():
        assert isinstance(series, list)
        assert len(series) <= 3
