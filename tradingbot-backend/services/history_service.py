"""
History Service - Read-only historisk data för TradingBot.

Konsoliderar:
- Trade history
- Ledger history
- Equity history
- Performance snapshots

Löser problem med:
- Spridda historik-endpoints
- Inkonsistenta historik-data
- Svår att debugga historik-problem
- Olika refresh-intervall för historik-data
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from config.settings import Settings
from rest.order_history import OrderHistoryService
from rest.ledgers import LedgerService
from rest.positions import PositionsService
from rest.wallet import WalletService
from services.performance import PerformanceService
from utils.logger import get_logger

logger = get_logger(__name__)


class HistoryData:
    """Historisk data för en symbol eller tidsperiod."""

    def __init__(self):
        self.timestamp = datetime.now()
        self.trades: list[dict[str, Any]] = []
        self.ledgers: list[dict[str, Any]] = []
        self.equity_history: list[dict[str, Any]] = []
        self.performance_snapshot: dict[str, Any] | None = None


class HistoryService:
    """
    Enhetlig service för all historisk data i systemet.

    Konsoliderar historik från:
    - Order history (trades)
    - Ledger history (wallet changes)
    - Equity history (performance over time)
    - Performance snapshots
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

        # Services för historisk data
        self.order_history = OrderHistoryService()
        self.ledger_service = LedgerService(self.settings)
        self.positions_service = PositionsService()
        self.wallet_service = WalletService()
        self.performance_service = PerformanceService(self.settings)

        # Cache för historik-data
        self._history_cache: dict[str, HistoryData] = {}
        self._cache_ttl = timedelta(minutes=5)  # Historik-data ändras sällan
        self._last_update: datetime | None = None

        logger.info("📚 HistoryService initialiserad - enhetlig historik-hantering")

    async def get_trade_history(
        self, symbol: str | None = None, limit: int = 100, force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        """Hämta trade history för en symbol eller alla."""
        try:
            cache_key = f"trades_{symbol or 'all'}_{limit}"

            # Kontrollera cache
            if (
                not force_refresh
                and cache_key in self._history_cache
                and self._last_update
                and datetime.now() - self._last_update < self._cache_ttl
            ):
                logger.debug(f"📋 Använder cached trade history för {symbol or 'all'}")
                return self._history_cache[cache_key].trades

            # Hämta trade history
            trades = await self.order_history.get_trades_history(limit=limit)

            # Filtrera på symbol om specificerat
            if symbol:
                trades = [t for t in trades if t.symbol == symbol]

            # Spara i cache
            if cache_key not in self._history_cache:
                self._history_cache[cache_key] = HistoryData()
            self._history_cache[cache_key].trades = trades
            self._last_update = datetime.now()

            logger.info(f"📊 Hämtade {len(trades)} trades för {symbol or 'alla symboler'}")
            return trades

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av trade history: {e}")
            return []

    async def get_ledger_history(
        self,
        wallet_type: str | None = None,
        currency: str | None = None,
        limit: int = 100,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Hämta ledger history för en wallet/currency eller alla."""
        try:
            cache_key = f"ledgers_{wallet_type or 'all'}_{currency or 'all'}_{limit}"

            # Kontrollera cache
            if (
                not force_refresh
                and cache_key in self._history_cache
                and self._last_update
                and datetime.now() - self._last_update < self._cache_ttl
            ):
                logger.debug(f"📋 Använder cached ledger history för {wallet_type or 'all'}")
                return self._history_cache[cache_key].ledgers

            # Hämta ledger history
            ledgers = await self.ledger_service.get_ledgers(limit=limit)

            # Filtrera på wallet_type och currency om specificerat
            if wallet_type:
                ledgers = [ledger for ledger in ledgers if ledger.wallet_type == wallet_type]
            if currency:
                ledgers = [ledger for ledger in ledgers if ledger.currency == currency]

            # Spara i cache
            if cache_key not in self._history_cache:
                self._history_cache[cache_key] = HistoryData()
            self._history_cache[cache_key].ledgers = ledgers
            self._last_update = datetime.now()

            logger.info(f"📊 Hämtade {len(ledgers)} ledgers för {wallet_type or 'alla wallets'}")
            return ledgers

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av ledger history: {e}")
            return []

    async def get_equity_history(self, limit: int = 1000, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Hämta equity history över tid."""
        try:
            cache_key = f"equity_{limit}"

            # Kontrollera cache
            if (
                not force_refresh
                and cache_key in self._history_cache
                and self._last_update
                and datetime.now() - self._last_update < self._cache_ttl
            ):
                logger.debug("📋 Använder cached equity history")
                return self._history_cache[cache_key].equity_history

            # Hämta equity history från performance service
            equity_data = await self.performance_service.compute_current_equity()

            # Skapa equity history (förenklad implementation)
            equity_history = [
                {
                    "timestamp": datetime.now().isoformat(),
                    "equity": equity_data.get("equity_usd", 0.0),
                    "unrealized_pnl": equity_data.get("unrealized_pnl_usd", 0.0),
                    "realized_pnl": equity_data.get("realized_pnl_usd", 0.0),
                }
            ]

            # Spara i cache
            if cache_key not in self._history_cache:
                self._history_cache[cache_key] = HistoryData()
            self._history_cache[cache_key].equity_history = equity_history
            self._last_update = datetime.now()

            logger.info(f"📊 Hämtade {len(equity_history)} equity history points")
            return equity_history

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av equity history: {e}")
            return []

    async def get_performance_snapshot(self, force_refresh: bool = False) -> dict[str, Any] | None:
        """Hämta aktuell performance snapshot."""
        try:
            cache_key = "performance_snapshot"

            # Kontrollera cache
            if (
                not force_refresh
                and cache_key in self._history_cache
                and self._last_update
                and datetime.now() - self._last_update < self._cache_ttl
            ):
                logger.debug("📋 Använder cached performance snapshot")
                return self._history_cache[cache_key].performance_snapshot

            # Hämta performance snapshot
            performance_data = await self.performance_service.compute_current_equity()

            # Spara i cache
            if cache_key not in self._history_cache:
                self._history_cache[cache_key] = HistoryData()
            self._history_cache[cache_key].performance_snapshot = performance_data
            self._last_update = datetime.now()

            logger.info("📊 Hämtade performance snapshot")
            return performance_data

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av performance snapshot: {e}")
            return None

    async def get_comprehensive_history(
        self,
        symbol: str | None = None,
        wallet_type: str | None = None,
        currency: str | None = None,
        trades_limit: int = 100,
        ledgers_limit: int = 100,
        equity_limit: int = 1000,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Hämta all historisk data i en enhetlig struktur."""
        try:
            # Hämta all historik parallellt
            trades_task = asyncio.create_task(self.get_trade_history(symbol, trades_limit, force_refresh))
            ledgers_task = asyncio.create_task(
                self.get_ledger_history(wallet_type, currency, ledgers_limit, force_refresh)
            )
            equity_task = asyncio.create_task(self.get_equity_history(equity_limit, force_refresh))
            performance_task = asyncio.create_task(self.get_performance_snapshot(force_refresh))

            # Vänta på alla tasks
            results = await asyncio.gather(
                trades_task,
                ledgers_task,
                equity_task,
                performance_task,
                return_exceptions=True,
            )

            # Hantera exceptions
            trades = results[0] if not isinstance(results[0], Exception) else []
            ledgers = results[1] if not isinstance(results[1], Exception) else []
            equity_history = results[2] if not isinstance(results[2], Exception) else []
            performance_snapshot = results[3] if not isinstance(results[3], Exception) else None

            # Skapa comprehensive history
            comprehensive_history = {
                "timestamp": datetime.now().isoformat(),
                "filters": {
                    "symbol": symbol,
                    "wallet_type": wallet_type,
                    "currency": currency,
                    "trades_limit": trades_limit,
                    "ledgers_limit": ledgers_limit,
                    "equity_limit": equity_limit,
                },
                "trades": {
                    "count": len(trades),
                    "data": trades,
                    "summary": self._calculate_trades_summary(trades),
                },
                "ledgers": {
                    "count": len(ledgers),
                    "data": ledgers,
                    "summary": self._calculate_ledgers_summary(ledgers),
                },
                "equity_history": {
                    "count": len(equity_history),
                    "data": equity_history,
                    "summary": self._calculate_equity_summary(equity_history),
                },
                "performance_snapshot": performance_snapshot,
            }

            logger.info("📚 Comprehensive history genererad")
            return comprehensive_history

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av comprehensive history: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "trades": {"count": 0, "data": [], "summary": {}},
                "ledgers": {"count": 0, "data": [], "summary": {}},
                "equity_history": {"count": 0, "data": [], "summary": {}},
                "performance_snapshot": None,
            }

    def _calculate_trades_summary(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        """Beräkna sammanfattning av trades."""
        try:
            total_volume = 0.0
            total_fees = 0.0
            buy_count = 0
            sell_count = 0

            for trade in trades:
                amount = float(trade.amount)
                fee = float(trade.fee)

                total_volume += abs(amount)
                total_fees += fee

                if amount > 0:
                    buy_count += 1
                elif amount < 0:
                    sell_count += 1

            return {
                "total_volume": total_volume,
                "total_fees": total_fees,
                "buy_count": buy_count,
                "sell_count": sell_count,
                "net_amount": sum(float(t.amount) for t in trades),
            }
        except Exception as e:
            logger.error(f"❌ Fel vid beräkning av trades summary: {e}")
            return {}

    def _calculate_ledgers_summary(self, ledgers: list[dict[str, Any]]) -> dict[str, Any]:
        """Beräkna sammanfattning av ledgers."""
        try:
            by_currency: dict[str, float] = {}
            by_wallet: dict[str, int] = {}

            for ledger in ledgers:
                # ledger kan vara dict eller objekt; hantera båda
                try:
                    currency = ledger.get("currency") if isinstance(ledger, dict) else getattr(ledger, "currency", None)
                    wallet_type = (
                        ledger.get("wallet_type") if isinstance(ledger, dict) else getattr(ledger, "wallet_type", None)
                    )
                    amount_raw = ledger.get("amount") if isinstance(ledger, dict) else getattr(ledger, "amount", 0)
                    amount = float(amount_raw or 0)
                except Exception:
                    currency = None
                    wallet_type = None
                    amount = 0.0

                if currency:
                    by_currency[currency] = by_currency.get(currency, 0) + amount
                if wallet_type:
                    by_wallet[wallet_type] = by_wallet.get(wallet_type, 0) + 1

            return {
                "by_currency": by_currency,
                "by_wallet": by_wallet,
                "total_entries": len(ledgers),
            }
        except Exception as e:
            logger.error(f"❌ Fel vid beräkning av ledgers summary: {e}")
            return {}

    def _calculate_equity_summary(self, equity_history: list[dict[str, Any]]) -> dict[str, Any]:
        """Beräkna sammanfattning av equity history."""
        try:
            if not equity_history:
                return {}

            equity_values = [float(e.get("equity", 0)) for e in equity_history]
            min_equity = min(equity_values) if equity_values else 0
            max_equity = max(equity_values) if equity_values else 0
            latest_equity = equity_values[-1] if equity_values else 0

            return {
                "min_equity": min_equity,
                "max_equity": max_equity,
                "latest_equity": latest_equity,
                "equity_range": max_equity - min_equity,
                "data_points": len(equity_history),
            }
        except Exception as e:
            logger.error(f"❌ Fel vid beräkning av equity summary: {e}")
            return {}

    def clear_cache(self) -> None:
        """Rensa historik cache."""
        self._history_cache.clear()
        self._last_update = None
        logger.info("🗑️ History cache rensad")


# Global instans för enhetlig åtkomst
history_service = HistoryService()
