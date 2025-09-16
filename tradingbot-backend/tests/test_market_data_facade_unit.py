import asyncio
import pytest

from services.market_data_facade import MarketDataFacade


class _StubRestService:
    async def get_configs_symbols(self):
        return ["BTCUSD", "ETHUSD"]

    async def get_currency_symbol_map(self):
        return {"ALGO": "ALG"}, {"ALG": "ALGO"}


class _StubWSFirst:
    def __init__(self):
        self.rest_service = _StubRestService()
        self._indicator_snapshots = {}

    async def get_ticker(
        self, symbol: str, *, force_fresh: bool = False
    ):  # noqa: ARG002
        return {"symbol": symbol, "last_price": 123.45}

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 5,
        *,
        force_fresh: bool = False,
    ):  # noqa: ARG002
        # Returnera minimalt giltig bitfinex-candle: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
        base = 100.0
        out = []
        for i in range(limit):
            mts = 1700000000000 + i * 60_000
            close = base + i
            out.append([mts, base, close, close + 1, close - 1, 10.0])
        return out

    def get_indicator_snapshot(self, symbol: str, timeframe: str):  # noqa: ARG002
        return self._indicator_snapshots.get((symbol, timeframe))

    def get_stats(self):
        return {"ws_hits": 1, "rest_fallbacks": 0}


@pytest.mark.asyncio
async def test_market_data_facade_basic_ticker_and_candles():
    stub = _StubWSFirst()
    facade = MarketDataFacade(ws_first=stub)

    t = await facade.get_ticker("tBTCUSD")
    assert t and t["last_price"] == 123.45

    cs = await facade.get_candles("tBTCUSD", "1m", 3)
    assert isinstance(cs, list) and len(cs) == 3


@pytest.mark.asyncio
async def test_market_data_facade_configs_and_aliases():
    stub = _StubWSFirst()
    facade = MarketDataFacade(ws_first=stub)

    pairs = await facade.get_configs_symbols()
    assert pairs == ["BTCUSD", "ETHUSD"]

    fwd, rev = await facade.get_currency_symbol_map()
    assert fwd.get("ALGO") == "ALG"
    assert rev.get("ALG") == "ALGO"


def test_market_data_facade_parse_helper():
    facade = MarketDataFacade(ws_first=_StubWSFirst())
    # 2 candles
    raw = [
        [1700000000000, 100.0, 101.0, 102.0, 99.0, 10.0],
        [1700000060000, 101.0, 102.0, 103.0, 100.0, 11.0],
    ]
    parsed = facade.parse_candles_to_strategy_data(raw)
    assert parsed["closes"] == [101.0, 102.0]
    assert parsed["highs"] == [102.0, 103.0]
    assert parsed["lows"] == [99.0, 100.0]
