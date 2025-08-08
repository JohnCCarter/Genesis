"""
Backtest Service - enkel sandbox-backtest mot historiska candles via Bitfinex REST.
"""

from __future__ import annotations

from typing import Dict, Any, List

from services.bitfinex_data import BitfinexDataService
from services.strategy import evaluate_strategy
from utils.logger import get_logger

logger = get_logger(__name__)


class BacktestService:
    async def run(self, symbol: str, timeframe: str, limit: int = 500) -> Dict[str, Any]:
        data = BitfinexDataService()
        candles = await data.get_candles(symbol, timeframe, limit)
        if not candles:
            return {"success": False, "error": "no_data"}
        parsed = data.parse_candles_to_strategy_data(candles)

        # Rullande strategiutvärdering och pseudo-PnL (mycket förenklad)
        closes: List[float] = parsed.get("closes", [])
        highs: List[float] = parsed.get("highs", [])
        lows: List[float] = parsed.get("lows", [])
        equity = 1000.0
        peak = equity
        max_dd = 0.0
        wins = 0
        losses = 0
        trades = 0

        pos = 0  # +1 long, -1 short, 0 flat
        entry_price = 0.0

        for i in range(50, len(closes)):
            window = {
                "closes": closes[: i + 1],
                "highs": highs[: i + 1],
                "lows": lows[: i + 1],
            }
            strat = evaluate_strategy(window)
            sig = (strat.get("weighted", {}) or {}).get("signal", "hold")
            price = closes[i]
            # Enkel exekvering: byt position på buy/sell, ingen avgift/slippage
            if sig == "buy" and pos <= 0:
                if pos < 0:
                    # stäng short
                    equity *= (entry_price / price)
                    trades += 1
                    if equity >= peak:
                        wins += 1
                    else:
                        losses += 1
                    peak = max(peak, equity)
                    max_dd = max(max_dd, (peak - equity) / peak)
                pos = 1
                entry_price = price
            elif sig == "sell" and pos >= 0:
                if pos > 0:
                    # stäng long
                    equity *= (price / entry_price)
                    trades += 1
                    if equity >= peak:
                        wins += 1
                    else:
                        losses += 1
                    peak = max(peak, equity)
                    max_dd = max(max_dd, (peak - equity) / peak)
                pos = -1
                entry_price = price

        winrate = (wins / trades) if trades > 0 else 0.0
        return {
            "success": True,
            "trades": trades,
            "final_equity": round(equity, 2),
            "winrate": round(winrate, 4),
            "max_drawdown": round(max_dd, 4),
        }


