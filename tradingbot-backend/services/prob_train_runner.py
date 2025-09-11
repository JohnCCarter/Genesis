"""
Runner: tränar en minimal LR‑baseline för tBTCUSD 1m och exporterar modell‑JSON.

Kör i PowerShell från repo‑roten:
  $env:PYTHONPATH='tradingbot-backend'
  python -m services.prob_train_runner
"""

from __future__ import annotations

import asyncio
import os

from services.market_data_facade import get_market_data
from services.prob_train import train_and_export


async def _fetch_candles(symbol: str, timeframe: str, limit: int) -> list[list[float]]:
    svc = get_market_data()
    candles = await svc.get_candles(symbol, timeframe, limit=limit)
    return candles or []


async def main() -> None:
    symbol = "tBTCUSD"
    timeframe = "1m"
    horizon = 20
    tp = 0.002
    sl = 0.002

    candles = await _fetch_candles(symbol, timeframe, limit=2000)
    if not candles:
        print("No candles fetched; check network/API.")
        return

    out_dir = os.path.join("tradingbot-backend", "config", "models")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{symbol[1:]}_{timeframe}.json")
    model = train_and_export(candles, horizon=horizon, tp=tp, sl=sl, out_path=out_path)
    print(f"Exported model to {out_path}")
    # Tips: sätt i .env → PROB_MODEL_FILE={out_path}


if __name__ == "__main__":
    asyncio.run(main())
