import os

import pytest

from services.ws_first_data_service import WSFirstDataService
from utils.candle_cache import candle_cache


@pytest.mark.asyncio
async def test_wsfirst_reads_from_persisted_cache_before_rest(monkeypatch):
    # Se till att cachen har data för symbol/timeframe
    symbol = "tTESTBTC:TESTUSD"
    timeframe = "1m"
    # Skapa 10 fiktiva candles [mts, open, close, high, low, volume]
    base = 1_700_000_000_000
    candles = [[base + i * 60_000, 1 + i, 1 + i, 1 + i, 1 + i, 1.0] for i in range(10)]
    candle_cache.store(symbol, timeframe, candles)

    svc = WSFirstDataService()

    # Mocka REST-tjänsten så att ett anrop skulle synas om det sker
    called = {"rest": 0}

    async def _mock_get_candles(sym, tf, limit):  # noqa: D401
        called["rest"] += 1
        return candles

    monkeypatch.setattr(svc.rest_service, "get_candles", _mock_get_candles)

    out = await svc.get_candles(symbol, timeframe, limit=5, force_fresh=False)
    assert out is not None
    # Ska INTE ha behövt REST, eftersom vi läser från persist cache först
    assert called["rest"] == 0
    assert len(out) <= 10
