"""
Strategy Tests - TradingBot Backend

Denna modul testar tradingstrategier och tekniska indikatorer.
"""

from typing import Any, Dict, List

import pytest

from indicators.atr import calculate_atr
from indicators.ema import calculate_ema
from indicators.rsi import calculate_rsi
from services.strategy import evaluate_strategy, evaluate_weighted_strategy


class TestIndicators:
    """Testklass för tekniska indikatorer."""

    def test_ema_calculation(self):
        """Testar EMA-beräkning."""
        prices = [
            100,
            101,
            102,
            103,
            104,
            105,
            106,
            107,
            108,
            109,
            110,
            111,
            112,
            113,
            114,
        ]
        ema = calculate_ema(prices, period=14)

        assert ema is not None
        assert isinstance(ema, float)
        assert ema > 0

    def test_rsi_calculation(self):
        """Testar RSI-beräkning."""
        prices = [
            100,
            101,
            102,
            103,
            104,
            105,
            106,
            107,
            108,
            109,
            110,
            111,
            112,
            113,
            114,
        ]
        rsi = calculate_rsi(prices, period=14)

        assert rsi is not None
        assert isinstance(rsi, float)
        assert 0 <= rsi <= 100

    def test_atr_calculation(self):
        """Testar ATR-beräkning."""
        highs = [105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118]
        lows = [95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108]
        closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113]

        atr = calculate_atr(highs, lows, closes, period=14)

        assert atr is not None
        assert isinstance(atr, float)
        assert atr > 0


class TestStrategy:
    """Testklass för tradingstrategi."""

    def test_evaluate_strategy_buy_signal(self):
        """Testar BUY-signal från strategi."""
        data = {
            "closes": [
                100,
                101,
                102,
                103,
                104,
                105,
                106,
                107,
                108,
                109,
                110,
                111,
                112,
                113,
                114,
                115,
                116,
                117,
                118,
                119,
                120,
                121,
                122,
                123,
                124,
                125,
                126,
                127,
                128,
                129,
                130,
            ],
            "highs": [
                105,
                106,
                107,
                108,
                109,
                110,
                111,
                112,
                113,
                114,
                115,
                116,
                117,
                118,
                119,
                120,
                121,
                122,
                123,
                124,
                125,
                126,
                127,
                128,
                129,
                130,
                131,
                132,
                133,
                134,
                135,
            ],
            "lows": [
                95,
                96,
                97,
                98,
                99,
                100,
                101,
                102,
                103,
                104,
                105,
                106,
                107,
                108,
                109,
                110,
                111,
                112,
                113,
                114,
                115,
                116,
                117,
                118,
                119,
                120,
                121,
                122,
                123,
                124,
                125,
            ],
        }

        result = evaluate_strategy(data)

        assert "signal" in result
        assert "reason" in result
        assert "ema" in result
        assert "rsi" in result
        assert "atr" in result
        assert "timestamp" in result
        assert result["signal"] in ["BUY", "SELL", "HOLD", "WAIT"]

    def test_evaluate_strategy_no_data(self):
        """Testar strategi med tom data."""
        data = {"closes": []}

        result = evaluate_strategy(data)

        assert result["signal"] == "WAIT"
        assert "Ingen prisdata" in result["reason"]

    def test_evaluate_strategy_insufficient_data(self):
        """Testar strategi med otillräcklig data."""
        data = {
            "closes": [100, 101, 102],  # För lite data för beräkningar
            "highs": [105, 106, 107],
            "lows": [95, 96, 97],
        }

        result = evaluate_strategy(data)

        assert result["signal"] == "WAIT"
        assert result["ema"] is None or result["rsi"] is None or result["atr"] is None


# TODO: Lägg till integrationstester med riktiga marknadsdata


class TestWeightedStrategy:
    """Tester för viktad strategiutvärdering."""

    def test_weighted_strategy_buy(self):
        data = {"ema": "buy", "rsi": "buy", "atr": "high"}
        result = evaluate_weighted_strategy(data)
        assert result["signal"] == "buy"
        p = result["probabilities"]
        assert 0.0 <= p["buy"] <= 1.0
        assert 0.0 <= p["sell"] <= 1.0
        assert 0.0 <= p["hold"] <= 1.0
        assert abs(p["buy"] + p["sell"] + p["hold"] - 1.0) < 1e-6

    def test_weighted_strategy_sell(self):
        data = {"ema": "sell", "rsi": "sell", "atr": "low"}
        result = evaluate_weighted_strategy(data)
        assert result["signal"] == "sell"

    def test_weighted_strategy_hold(self):
        data = {"ema": "buy", "rsi": "sell", "atr": "low"}
        result = evaluate_weighted_strategy(data)
        assert result["signal"] == "hold"
