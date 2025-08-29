"""
Enhetlig Trading Service för Genesis Trading Bot

Konsoliderar alla trading-operationer från olika moduler:
- Standard trading (TradingIntegration)
- Enhanced trading (EnhancedAutoTrader)
- WebSocket trading (BitfinexWebSocketService)
"""

from datetime import datetime
from typing import Any

from models.signal_models import SignalResponse
from utils.logger import get_logger

from services.bitfinex_websocket import BitfinexWebSocketService
from services.enhanced_auto_trader import EnhancedAutoTrader
from services.trading_integration import TradingIntegrationService

logger = get_logger(__name__)


class TradingService:
    """
    Enhetlig service för all trading-operationer i systemet.

    Konsoliderar:
    - Standard trading via REST API
    - Enhanced trading med position sizing
    - WebSocket trading för realtids-execution
    """

    def __init__(self):
        self._trading_integration = TradingIntegrationService()
        self._enhanced_trader = EnhancedAutoTrader()
        self._ws_service: BitfinexWebSocketService | None = None

        # Enhetlig trade-historik
        self._trade_history: list[dict[str, Any]] = []
        self._last_trade_time: dict[str, datetime] = {}

        logger.info("🚀 TradingService initialiserad - enhetlig trading-hantering")

    def set_websocket_service(self, ws_service: BitfinexWebSocketService):
        """Sätt WebSocket service för realtids-trading"""
        self._ws_service = ws_service
        logger.info("🔗 WebSocket service kopplad till TradingService")

    async def execute_signal(self, symbol: str, signal: SignalResponse, mode: str = "standard") -> dict[str, Any]:
        """
        Enhetlig trade-execution för alla moduler.

        Args:
            symbol: Trading symbol
            signal: Signal att exekvera
            mode: "standard", "enhanced", eller "realtime"

        Returns:
            Dict med trade-resultat
        """
        logger.info(f"💼 Exekverar {mode}-trade för {symbol}: {signal.signal_type}")

        # Kontrollera trade-intervall
        if not self._should_allow_trade(symbol, mode):
            return {
                "success": False,
                "error": "Trade blocked - too frequent",
                "symbol": symbol,
                "mode": mode,
            }

        if mode == "enhanced":
            return await self._execute_enhanced_trade(symbol, signal)
        elif mode == "realtime":
            return await self._execute_realtime_trade(symbol, signal)
        else:
            return await self._execute_standard_trade(symbol, signal)

    async def _execute_standard_trade(self, symbol: str, signal: SignalResponse) -> dict[str, Any]:
        """Standard trading via TradingIntegration"""
        try:
            # Konvertera SignalResponse till dict-format för TradingIntegration
            signal_dict = {
                "symbol": symbol,
                "signal_type": signal.signal_type,
                "confidence": signal.confidence,
                "price": signal.price,
                "metadata": signal.metadata or {},
            }

            result = await self._trading_integration.execute_trading_signal(symbol, signal_dict)

            # Uppdatera trade-historik
            self._record_trade(symbol, "standard", result)

            return result
        except Exception as e:
            logger.error(f"❌ Fel vid standard trade för {symbol}: {e}")
            return {"success": False, "error": str(e), "symbol": symbol, "mode": "standard"}

    async def _execute_enhanced_trade(self, symbol: str, signal: SignalResponse) -> dict[str, Any]:
        """Enhanced trading med position sizing"""
        try:
            # Skapa dummy realtime_result för enhanced trading
            realtime_result = {
                "symbol": symbol,
                "current_price": signal.price,
                "timestamp": datetime.now(),
            }

            result = await self._enhanced_trader._execute_enhanced_trade(symbol, signal, realtime_result)

            # Uppdatera trade-historik
            self._record_trade(symbol, "enhanced", result)

            return result
        except Exception as e:
            logger.error(f"❌ Fel vid enhanced trade för {symbol}: {e}")
            return {"success": False, "error": str(e), "symbol": symbol, "mode": "enhanced"}

    async def _execute_realtime_trade(self, symbol: str, signal: SignalResponse) -> dict[str, Any]:
        """Realtids-trading via WebSocket (om tillgängligt)"""
        if not self._ws_service:
            logger.warning("⚠️ WebSocket service inte tillgänglig, fallback till standard")
            return await self._execute_standard_trade(symbol, signal)

        try:
            # Använd WebSocket för realtids-execution
            result = await self._ws_service._handle_ticker_with_strategy(
                {"symbol": symbol, "signal": signal, "timestamp": datetime.now()}
            )

            # Uppdatera trade-historik
            self._record_trade(symbol, "realtime", result)

            return result
        except Exception as e:
            logger.error(f"❌ Fel vid realtids-trade för {symbol}: {e}")
            return {"success": False, "error": str(e), "symbol": symbol, "mode": "realtime"}

    def _should_allow_trade(self, symbol: str, mode: str) -> bool:
        """Kontrollera om trade ska tillåtas baserat på frekvens"""
        now = datetime.now()
        last_trade = self._last_trade_time.get(symbol)

        if not last_trade:
            return True

        # Olika intervall för olika modes
        intervals = {
            "standard": 60,
            "enhanced": 30,
            "realtime": 10,
        }  # 1 minut  # 30 sekunder  # 10 sekunder

        min_interval = intervals.get(mode, 60)
        time_since_last = (now - last_trade).total_seconds()

        return time_since_last >= min_interval

    def _record_trade(self, symbol: str, mode: str, result: dict[str, Any]):
        """Registrera trade i historik"""
        trade_record = {
            "symbol": symbol,
            "mode": mode,
            "timestamp": datetime.now(),
            "success": result.get("success", False),
            "result": result,
        }

        self._trade_history.append(trade_record)
        self._last_trade_time[symbol] = datetime.now()

        # Begränsa historik till senaste 100 trades
        if len(self._trade_history) > 100:
            self._trade_history = self._trade_history[-100:]

    def get_trade_history(self, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Hämta trade-historik"""
        history = self._trade_history

        if symbol:
            history = [trade for trade in history if trade["symbol"] == symbol]

        return history[-limit:] if limit else history

    def get_trading_stats(self) -> dict[str, Any]:
        """Hämta trading-statistik"""
        if not self._trade_history:
            return {
                "total_trades": 0,
                "successful_trades": 0,
                "success_rate": 0.0,
                "last_trade": None,
            }

        total_trades = len(self._trade_history)
        successful_trades = sum(1 for trade in self._trade_history if trade["success"])
        success_rate = (successful_trades / total_trades) * 100 if total_trades > 0 else 0

        return {
            "total_trades": total_trades,
            "successful_trades": successful_trades,
            "success_rate": round(success_rate, 2),
            "last_trade": self._trade_history[-1] if self._trade_history else None,
            "trades_by_mode": self._get_trades_by_mode(),
        }

    def _get_trades_by_mode(self) -> dict[str, int]:
        """Gruppera trades efter mode"""
        mode_counts = {}
        for trade in self._trade_history:
            mode = trade["mode"]
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        return mode_counts

    def clear_history(self, symbol: str | None = None):
        """Rensa trade-historik"""
        if symbol:
            self._trade_history = [trade for trade in self._trade_history if trade["symbol"] != symbol]
            self._last_trade_time.pop(symbol, None)
            logger.info(f"🗑️ Trade-historik rensad för {symbol}")
        else:
            self._trade_history.clear()
            self._last_trade_time.clear()
            logger.info("🗑️ All trade-historik rensad")


# Global instans för enhetlig åtkomst
trading_service = TradingService()
