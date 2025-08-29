import asyncio
from typing import Dict, List

from services.bitfinex_websocket import bitfinex_ws

from config.settings import Settings


async def run_test() -> dict[str, dict[str, str]]:
    settings = Settings()
    raw = (settings.WS_SUBSCRIBE_SYMBOLS or "").strip()
    if not raw:
        print("WS_SUBSCRIBE_SYMBOLS is empty")
        return {}

    symbols: list[str] = [s.strip() for s in raw.split(",") if s.strip()]

    # Connect (public subs works on same socket; auth is optional)
    ok = await bitfinex_ws.connect()
    print("connect:", bool(ok))

    # Build mapping original -> effective symbol used
    mapping: dict[str, str] = {}
    for sym in symbols:
        eff = bitfinex_ws._normalize_public_symbol(sym)  # type: ignore[attr-defined]
        eff = await bitfinex_ws._choose_available_pair(eff)  # type: ignore[attr-defined]
        mapping[sym] = eff

    # Subscribe
    for sym in symbols:
        await bitfinex_ws.subscribe_ticker(sym, bitfinex_ws._handle_ticker_with_strategy)  # type: ignore[attr-defined]

    # Wait a bit for first ticks
    await asyncio.sleep(2.0)

    # Collect status
    report: dict[str, dict[str, str]] = {}
    for sym in symbols:
        eff = mapping.get(sym, sym)
        active = "yes" if eff in bitfinex_ws.active_tickers else "no"
        lp = None
        # try both original and effective lookup
        lp = bitfinex_ws.latest_prices.get(sym) or bitfinex_ws.latest_prices.get(eff)
        price_ok = "yes" if lp is not None else "no"
        report[sym] = {
            "eff": eff,
            "active": active,
            "price": price_ok,
        }

    await bitfinex_ws.disconnect()
    return report


def main():
    out = asyncio.get_event_loop().run_until_complete(run_test())
    print("report:")
    for k, v in out.items():
        print(f"  {k} -> {v['eff']} | active={v['active']} price={v['price']}")


if __name__ == "__main__":
    main()
