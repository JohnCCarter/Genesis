"""
Performance Service - TradingBot Backend

Denna modul beräknar enkel PnL/Equity och hanterar dagliga snapshots.

Mål (minimum):
- Realized PnL per symbol (via trades FIFO/avg-kostnad)
- Current equity (USD) + history (dagliga snapshots i JSON)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # pragma: no cover
    ZoneInfo = None  # Fallback; använder naive tider

from config.settings import settings
from rest.order_history import OrderHistoryService, TradeItem
from rest.positions import PositionsService
from rest.wallet import WalletService
from services.market_data_facade import get_market_data
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SymbolPosition:
    net_amount: float = 0.0
    avg_price: float = 0.0  # genomsnittspris för öppen position
    realized_pnl: float = 0.0  # i quote-valuta för symbolen
    fees: float = 0.0  # summerade fees i fee_currency (ej konverterade)


class PerformanceService:
    def __init__(self, settings_override: Settings | None = None) -> None:
        self.settings = settings_override or settings
        self.wallet_service = WalletService()
        self.positions_service = PositionsService()
        self.order_history_service = OrderHistoryService()
        self.data_service = get_market_data()
        self._fx_cache: dict[str, float] = {}

        # Persistensfil för equity-historik
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(base_dir, os.pardir))
        self.config_dir = os.path.join(project_root, "config")
        self.history_path = os.path.join(self.config_dir, "performance_history.json")
        os.makedirs(self.config_dir, exist_ok=True)

    async def get_recent_trades(self, hours: int = 24, limit: int = 500) -> list[TradeItem]:
        """Hämta trades från senaste N timmarna.

        Hämtar upp till `limit` trades via REST och filtrerar klient-side på timestamp.
        Returnerar en lista av TradeItem.
        """
        try:
            # Hämta senaste trades (utan symbolfilter)
            trades: list[TradeItem] = await self.order_history_service.get_trades_history(symbol=None, limit=limit)
        except Exception as e:
            logger.warning(f"Kunde inte hämta senaste trades: {e}")
            return []

        try:
            cutoff_ms = int(datetime.now().timestamp() * 1000) - int(hours * 3600 * 1000)
            recent = [
                t for t in trades if hasattr(t, "executed_at") and int(t.executed_at.timestamp() * 1000) >= cutoff_ms
            ]
            return recent
        except Exception:
            # Om filtreringen misslyckas, returnera ofiltrerat (bättre än tom lista)
            return trades

    # ---- Helpers ----
    @staticmethod
    def _parse_base_quote(symbol: str) -> tuple[str, str]:
        s = symbol[1:] if symbol.startswith("t") else symbol
        if ":" in s:
            base, quote = s.split(":", 1)
        else:
            base, quote = s[:-3], s[-3:]
        return base.upper(), quote.upper()

    # ---- FX helpers (quote/fee -> USD) ----
    @staticmethod
    def _looks_like_currency(code: str | None) -> bool:
        if not code:
            return False
        c = str(code).upper()
        # Tillåt bokstäver 3..10 tecken (t.ex. USD, TESTUSD). Exkludera siffror/tecken.
        return c.isalpha() and 3 <= len(c) <= 10

    @staticmethod
    def _is_usd_stablecoin(cur: str) -> bool:
        c = (cur or "").upper()
        return c in {
            "USDT",
            "USDC",
            "TUSD",
            "DAI",
            "PAX",
            "BUSD",
            "TESTUSD",
            "TESTUSDT",
        }

    async def _fx_to_usd(self, currency: str | None) -> float:
        """Get simple FX rate currency->USD using Bitfinex tickers.

        Strategy:
        - If currency is USD or stablecoin → 1.0
        - Try direct pair t{CUR}USD
        - Else try inverse tUSD:{CUR} and invert
        Returns 0.0 if not resolvable (caller should handle gracefully).
        """
        if not currency:
            return 0.0
        cur = currency.upper()
        # Snabb validering – undvik försök för värden som uppenbart inte är valutor (t.ex. "1", "-1")
        if not self._looks_like_currency(cur):
            return 0.0
        # USD och stablecoins (inkl TESTUSD/TESTUSDT) → 1.0
        if cur == "USD" or self._is_usd_stablecoin(cur):
            return 1.0
        if cur in self._fx_cache:
            return self._fx_cache[cur]

        # Begränsa FX‑tickerförsök: endast USD‑quote eller whitelist av direkta FX
        # Tillåt ett litet set av baser för snabb dev: BTC, ETH, ADA, DOT
        FX_BASE_WHITELIST = {"BTC", "ETH", "ADA", "DOT"}
        # Produktion: endast direkta {CUR}USD eller USD:{CUR}
        # Om cur inte är i whitelist (för bas) eller USD‑stablecoin, försök inte
        # externa TEST‑par (minska brus/timeouts)
        if cur.startswith("TEST"):
            # Testvalutor hanteras som 0.0 om inte explicit USD/USDT ovan
            self._fx_cache[cur] = 0.0
            return 0.0

        # Produktion: försök direkt USD-quote, därefter inverse
        try:
            # Om cur är i whitelist, försök direkt {CUR}USD
            if cur in FX_BASE_WHITELIST:
                sym = f"t{cur}USD"
                t = await self.data_service.get_ticker(sym)
                if t and float(t.get("last_price", 0)) > 0:
                    rate = float(t.get("last_price"))
                    self._fx_cache[cur] = rate
                    return rate
        except Exception:
            pass
        try:
            # Inverse USD:{CUR} endast om whitelisted
            if cur in FX_BASE_WHITELIST:
                sym_inv = f"tUSD:{cur}"
                t = await self.data_service.get_ticker(sym_inv)
                if t and float(t.get("last_price", 0)) > 0:
                    rate = 1.0 / float(t.get("last_price"))
                    self._fx_cache[cur] = rate
                    return rate
        except Exception:
            pass
        # Unavailable
        self._fx_cache[cur] = 0.0
        return 0.0

    # ---- Realized PnL via trades (FIFO/avg-kostnad light) ----
    async def compute_realized_pnl(self, limit: int = 1000) -> dict[str, Any]:
        """
        Aggregerar realized PnL per symbol genom att gå igenom trades i tidsordning och
        använda en enkel avg-kostnadsmodell.

        Not:
        - PnL beräknas i symbolens quote-valuta.
        - Fees summeras separat per fee_currency (ingen FX-konvertering här).
        """
        # Hämta trades – var robust mot tillfälliga Bitfinex-fel (t.ex. 5xx)
        try:
            import asyncio

            trades: list[TradeItem] = await asyncio.wait_for(
                self.order_history_service.get_trades_history(symbol=None, limit=limit),
                timeout=5.0,  # 5 sekunder timeout för trades-hämtning
            )
        except TimeoutError:
            logger.warning("⚠️ Timeout vid hämtning av trades för realized PnL")
            trades = []
        except Exception as e:
            logger.warning(f"Kunde inte hämta trades för realized PnL (fortsätter med tom lista): {e}")
            trades = []
        # Sortera i tidsordning
        trades.sort(key=lambda t: t.executed_at)

        symbol_state: dict[str, SymbolPosition] = {}
        fees_by_currency: dict[str, float] = {}

        for t in trades:
            pos = symbol_state.setdefault(t.symbol, SymbolPosition())
            amount = float(t.amount)
            price = float(t.price)

            # Summera fees
            try:
                fees_by_currency[t.fee_currency] = fees_by_currency.get(t.fee_currency, 0.0) + float(t.fee)
                pos.fees += float(t.fee)
            except Exception:
                pass

            # Ingen öppen position ännu
            if pos.net_amount == 0.0:
                pos.net_amount = amount
                pos.avg_price = price
                continue

            # Samma riktning -> utöka position och uppdatera avg_price
            if (pos.net_amount > 0 and amount > 0) or (pos.net_amount < 0 and amount < 0):
                total_qty = abs(pos.net_amount) + abs(amount)
                if total_qty > 0:
                    pos.avg_price = ((abs(pos.net_amount) * pos.avg_price) + (abs(amount) * price)) / total_qty
                pos.net_amount += amount
                continue

            # Motsatt riktning -> stänger delvis/hela och ev. vänder
            closing_qty = min(abs(pos.net_amount), abs(amount))
            if pos.net_amount > 0 and amount < 0:  # stänger long med sälj
                pos.realized_pnl += (price - pos.avg_price) * closing_qty
            elif pos.net_amount < 0 and amount > 0:  # stänger short med köp
                pos.realized_pnl += (pos.avg_price - price) * closing_qty

            # Uppdatera net_amount och hantera eventuell vändning
            new_net = pos.net_amount + amount
            if new_net == 0:
                pos.net_amount = 0.0
                pos.avg_price = 0.0
            elif (pos.net_amount > 0 and new_net < 0) or (pos.net_amount < 0 and new_net > 0):
                # Vi har stängt hela och öppnat ny i motsatt riktning för residual
                residual = new_net
                pos.net_amount = residual
                pos.avg_price = price  # starta ny position på trade-priset
            else:
                # Delvis stängd, kvarvarande riktning oförändrad, avg_price bibehålls
                pos.net_amount = new_net

        # Bygg utdata per symbol
        pnl_by_symbol: dict[str, dict[str, Any]] = {}
        totals: dict[str, Any] = {
            "realized": 0.0,
            "realized_usd": 0.0,
            "fees": fees_by_currency,  # original currencies
            "fees_usd": 0.0,
        }

        # Preload FX for quotes and fee currencies
        needed_fx: set[str] = set()
        for sym in symbol_state.keys():
            _, q = self._parse_base_quote(sym)
            needed_fx.add(q)
        for fee_cur in fees_by_currency.keys():
            if fee_cur and self._looks_like_currency(fee_cur):
                needed_fx.add(fee_cur)
        for c in needed_fx:
            try:
                await self._fx_to_usd(c)
            except Exception:
                pass

        for sym, st in symbol_state.items():
            base, quote = self._parse_base_quote(sym)
            fx = await self._fx_to_usd(quote)
            realized_usd = st.realized_pnl * fx if fx > 0 else None
            pnl_by_symbol[sym] = {
                "base": base,
                "quote": quote,
                "realized": round(st.realized_pnl, 8),
                "realized_usd": (round(realized_usd, 8) if realized_usd is not None else None),
                "fx_quote_usd": round(fx, 8) if fx > 0 else None,
                "open_amount": round(st.net_amount, 8),
                "avg_price": round(st.avg_price, 8),
                "fees_sum": round(st.fees, 8),
            }
            totals["realized"] += st.realized_pnl
            if realized_usd is not None:
                totals["realized_usd"] += realized_usd

        totals["realized"] = round(totals["realized"], 8)
        totals["realized_usd"] = round(totals.get("realized_usd", 0.0), 8)

        # Convert fees to USD (aggregate)
        fees_usd_sum = 0.0
        for fee_cur, amt in fees_by_currency.items():
            try:
                fx = await self._fx_to_usd(fee_cur)
                if fx > 0:
                    fees_usd_sum += float(amt) * fx
            except Exception:
                pass
        totals["fees_usd"] = round(fees_usd_sum, 8)

        return {
            "pnl_by_symbol": pnl_by_symbol,
            "totals": totals,
            "count_trades": len(trades),
        }

    # ---- Equity (USD) + snapshots ----
    async def compute_current_equity(self) -> dict[str, Any]:
        """Beräkna equity i USD med timeout på alla calls:
        - Summan av alla plånböcker konverterade till USD (USD och USD-stablecoins → 1.0)
        - Plus summerad unrealized PnL (om tillgängligt)
        """
        try:
            import asyncio

            # Skapa tasks för wallet och position calls med timeout
            wallets_task = asyncio.create_task(asyncio.wait_for(self.wallet_service.get_wallets(), timeout=1.0))
            positions_task = asyncio.create_task(asyncio.wait_for(self.positions_service.get_positions(), timeout=1.0))

            # Vänta på båda med total timeout
            wallets, positions = await asyncio.wait_for(
                asyncio.gather(wallets_task, positions_task, return_exceptions=True),
                timeout=2.0,
            )

            # Hantera exceptions från tasks
            if isinstance(wallets, Exception):
                logger.warning(f"⚠️ Wallet fetch failed: {wallets}")
                wallets = []
            if isinstance(positions, Exception):
                logger.warning(f"⚠️ Position fetch failed: {positions}")
                positions = []

            wallets_usd_total = 0.0
            for w in wallets:
                cur = (w.currency or "").upper()
                try:
                    fx = (
                        1.0
                        if cur == "USD" or self._is_usd_stablecoin(cur)
                        else await asyncio.wait_for(self._fx_to_usd(cur), timeout=0.5)
                    )
                    wallets_usd_total += float(w.balance) * (fx if fx > 0 else 0.0)
                except TimeoutError:
                    logger.warning(f"⚠️ FX timeout for {cur}, using 0.0")
                    wallets_usd_total += 0.0
                except Exception:
                    # Ignorera korrupta värden
                    pass

            # OBS: profit_loss från Bitfinex är normalt i quote-valuta; i praktiken USD för USD-par
            # Vi antar USD här. (För icke-USD-par kan detta förbättras genom FX per position.)
            unrealized = sum(float(p.profit_loss or 0.0) for p in positions)

            return {
                "total_usd": round(float(wallets_usd_total) + float(unrealized), 8),
                "wallets_usd": round(float(wallets_usd_total), 8),
                "unrealized_pnl_usd": round(float(unrealized), 8),
                "positions_count": len(positions),
            }

        except TimeoutError:
            logger.warning("⚠️ Equity computation timeout - returning fallback")
            return {
                "total_usd": 0.0,
                "wallets_usd": 0.0,
                "unrealized_pnl_usd": 0.0,
                "positions_count": 0,
            }
        except Exception as e:
            logger.error(f"❌ Equity computation error: {e}")
            return {
                "total_usd": 0.0,
                "wallets_usd": 0.0,
                "unrealized_pnl_usd": 0.0,
                "positions_count": 0,
            }

    def _now_local_date(self) -> str:
        tzname = getattr(self.settings, "TIMEZONE", None) or "UTC"
        try:
            if ZoneInfo is not None:
                d = datetime.now(ZoneInfo(tzname)).date()
            else:
                d = date.today()
        except Exception:
            d = date.today()
        return d.isoformat()

    def _load_history(self) -> dict[str, Any]:
        if not os.path.exists(self.history_path):
            return {"equity": []}
        try:
            with open(self.history_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.warning("Kunde inte läsa performance_history.json, initierar ny fil")
            return {"equity": []}

    def _save_history(self, data: dict[str, Any]) -> None:
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Fel vid skrivning av performance_history.json: {e}")

    def get_equity_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        data = self._load_history()
        history: list[dict[str, Any]] = list(data.get("equity", []))
        if limit is not None and limit > 0:
            return history[-limit:]
        return history

    async def snapshot_equity(self) -> dict[str, Any]:
        """Skapa/uppdatera dagens snapshot och returnera hela historiken."""
        equity = await self.compute_current_equity()
        # Ta med realized_usd (kumulativ) i snapshot
        realized = await self.compute_realized_pnl(limit=1000)
        realized_usd = float((realized.get("totals", {}) or {}).get("realized_usd", 0.0) or 0.0)
        today = self._now_local_date()

        data = self._load_history()
        history: list[dict[str, Any]] = list(data.get("equity", []))

        # Hitta föregående dags snapshot för dagsförändring
        prev_total = None
        prev_realized_usd = None
        for row in reversed(history):
            if row.get("date") != today:
                prev_total = float(row.get("total_usd", 0.0) or 0.0)
                prev_realized_usd = float(row.get("realized_usd", 0.0) or 0.0)
                break

        # Uppdatera om dagens post finns, annars append
        updated = False
        for row in history:
            if row.get("date") == today:
                row.update(
                    {
                        "total_usd": equity["total_usd"],
                        "wallets_usd": equity["wallets_usd"],
                        "unrealized_pnl_usd": equity["unrealized_pnl_usd"],
                        "realized_usd": round(realized_usd, 8),
                    }
                )
                # Beräkna dagsförändring relativt föregående dag
                if prev_total is not None:
                    row["day_change_usd"] = round(equity["total_usd"] - prev_total, 8)
                if prev_realized_usd is not None:
                    row["realized_day_change_usd"] = round(realized_usd - prev_realized_usd, 8)
                updated = True
                break
        if not updated:
            history.append(
                {
                    "date": today,
                    **equity,
                    "realized_usd": round(realized_usd, 8),
                    "day_change_usd": (round((equity["total_usd"] - prev_total), 8) if prev_total is not None else 0.0),
                    "realized_day_change_usd": (
                        round((realized_usd - prev_realized_usd), 8) if prev_realized_usd is not None else 0.0
                    ),
                }
            )

        # Spara
        data["equity"] = history
        self._save_history(data)

        # Beräkna dagliga diffar för retur-snapshot (även om historik var tom)
        day_change = 0.0 if prev_total is None else round(equity["total_usd"] - prev_total, 8)
        realized_day_change = 0.0 if prev_realized_usd is None else round(realized_usd - prev_realized_usd, 8)

        return {
            "snapshot": {
                "date": today,
                **equity,
                "realized_usd": round(realized_usd, 8),
                "day_change_usd": day_change,
                "realized_day_change_usd": realized_day_change,
            },
            "count": len(history),
        }
