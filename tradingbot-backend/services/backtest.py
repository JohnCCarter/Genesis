"""
Backtest Service - enkel sandbox-backtest mot historiska candles via Bitfinex REST.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Dict, List

from services.bitfinex_data import BitfinexDataService
from services.strategy import evaluate_strategy
from utils.logger import get_logger

logger = get_logger(__name__)


class BacktestService:
    async def run(
        self, symbol: str, timeframe: str, limit: int = 500, tz_offset_minutes: int = 0
    ) -> dict[str, Any]:
        data = BitfinexDataService()
        candles = await data.get_candles(symbol, timeframe, limit)
        if not candles:
            return {"success": False, "error": "no_data"}
        parsed = data.parse_candles_to_strategy_data(candles)

        # Rullande strategiutvärdering och pseudo-PnL (mycket förenklad)
        closes: list[float] = parsed.get("closes", [])
        highs: list[float] = parsed.get("highs", [])
        lows: list[float] = parsed.get("lows", [])
        equity = 1000.0
        peak = equity
        max_dd = 0.0
        wins = 0
        losses = 0
        trades = 0
        trade_returns: list[float] = []
        equity_curve: list[dict] = []
        heatmap_sum: dict[str, dict[str, float]] = {}
        heatmap_cnt: dict[str, dict[str, int]] = {}
        heatmap_wins: dict[str, dict[str, int]] = {}

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
            # timestamp (ms) om möjligt
            ts_ms = None
            try:
                idx_in_candles = len(candles) - len(closes) + i
                idx_in_candles = idx_in_candles if 0 <= idx_in_candles < len(candles) else i
                ts_ms = int(candles[idx_in_candles][0])
            except Exception:
                ts_ms = None
            # Enkel exekvering: byt position på buy/sell, ingen avgift/slippage
            if sig == "buy" and pos <= 0:
                if pos < 0:
                    # stäng short
                    factor = entry_price / price
                    equity *= factor
                    trade_returns.append(factor - 1.0)
                    if ts_ms is not None:
                        dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
                        if tz_offset_minutes:
                            dt = dt + timedelta(minutes=tz_offset_minutes)
                        dow = str(dt.weekday())  # 0=Mon
                        hour = str(dt.hour)
                        heatmap_sum.setdefault(dow, {})
                        heatmap_cnt.setdefault(dow, {})
                        heatmap_wins.setdefault(dow, {})
                        heatmap_sum[dow][hour] = heatmap_sum[dow].get(hour, 0.0) + (factor - 1.0)
                        heatmap_cnt[dow][hour] = heatmap_cnt[dow].get(hour, 0) + 1
                        if factor - 1.0 > 0:
                            heatmap_wins[dow][hour] = heatmap_wins[dow].get(hour, 0) + 1
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
                    factor = price / entry_price
                    equity *= factor
                    trade_returns.append(factor - 1.0)
                    if ts_ms is not None:
                        dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
                        if tz_offset_minutes:
                            dt = dt + timedelta(minutes=tz_offset_minutes)
                        dow = str(dt.weekday())
                        hour = str(dt.hour)
                        heatmap_sum.setdefault(dow, {})
                        heatmap_cnt.setdefault(dow, {})
                        heatmap_wins.setdefault(dow, {})
                        heatmap_sum[dow][hour] = heatmap_sum[dow].get(hour, 0.0) + (factor - 1.0)
                        heatmap_cnt[dow][hour] = heatmap_cnt[dow].get(hour, 0) + 1
                        if factor - 1.0 > 0:
                            heatmap_wins[dow][hour] = heatmap_wins[dow].get(hour, 0) + 1
                    trades += 1
                    if equity >= peak:
                        wins += 1
                    else:
                        losses += 1
                    peak = max(peak, equity)
                    max_dd = max(max_dd, (peak - equity) / peak)
                pos = -1
                entry_price = price
            if ts_ms is not None:
                equity_curve.append({"ts": ts_ms, "equity": round(equity, 2)})

        winrate = (wins / trades) if trades > 0 else 0.0
        # Sharpe (förenklad per trade)
        sharpe = 0.0
        if len(trade_returns) > 1:
            mu = sum(trade_returns) / len(trade_returns)
            var = sum((r - mu) ** 2 for r in trade_returns) / (len(trade_returns) - 1)
            std = math.sqrt(var) if var > 0 else 0.0
            if std > 0:
                sharpe = (mu / std) * math.sqrt(len(trade_returns))

        # Distribution (bins)
        bins = [-0.1, -0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.05, 0.1]
        dist: dict[str, int] = {str(b): 0 for b in bins}
        dist.update({"lt_min": 0, "gt_max": 0})
        for r in trade_returns:
            if r < bins[0]:
                dist["lt_min"] += 1
            elif r > bins[-1]:
                dist["gt_max"] += 1
            else:
                for b in bins:
                    if r <= b:
                        dist[str(b)] += 1
                        break

        # Heatmap averages (avg return) och winrate
        heatmap_avg: dict[str, dict[str, float]] = {}
        heatmap_wr: dict[str, dict[str, float]] = {}
        for d, hours in heatmap_sum.items():
            for h, s in hours.items():
                c = max(heatmap_cnt.get(d, {}).get(h, 0), 1)
                heatmap_avg.setdefault(d, {})[h] = round(s / c, 6)
                w = heatmap_wins.get(d, {}).get(h, 0)
                heatmap_wr.setdefault(d, {})[h] = round(w / c, 6)

        return {
            "success": True,
            "trades": trades,
            "final_equity": round(equity, 2),
            "winrate": round(winrate, 4),
            "max_drawdown": round(max_dd, 4),
            "sharpe": round(sharpe, 4),
            "distribution": dist,
            "equity_curve": equity_curve[-500:],
            "heatmap": heatmap_avg,  # alias för bakåtkompatibilitet
            "heatmap_return": heatmap_avg,
            "heatmap_winrate": heatmap_wr,
            "heatmap_counts": heatmap_cnt,
            "heatmap_tz_offset_minutes": tz_offset_minutes,
        }
