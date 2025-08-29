"""
Realtime Strategy Service - TradingBot Backend

Denna modul hanterar realtids strategiutvärdering baserat på live tick-data.
Inkluderar automatisk signalgenerering och WebSocket-integration.
"""

from collections.abc import Callable

from utils.logger import get_logger

from services.bitfinex_websocket import bitfinex_ws

logger = get_logger(__name__)


class RealtimeStrategyService:
    """Service för realtids strategiutvärdering."""

    def __init__(self):
        self.active_symbols = set()
        self.strategy_results = {}
        self.signal_callbacks = {}
        self.is_running = False

    async def start_monitoring(self, symbol: str, callback: Callable | None = None):
        """
        Startar övervakning av en symbol med realtids strategiutvärdering.

        Args:
            symbol: Trading pair (t.ex. 'tBTCUSD')
            callback: Funktion som anropas vid nya signaler
        """
        try:
            if symbol in self.active_symbols:
                logger.warning(f"⚠️ {symbol} övervakas redan")
                return

            # Spara callback
            if callback:
                self.signal_callbacks[symbol] = callback

            # Starta WebSocket-övervakning
            await bitfinex_ws.subscribe_with_strategy_evaluation(symbol, self._handle_strategy_result)

            self.active_symbols.add(symbol)
            self.is_running = True

            logger.info(f"🎯 Startade realtids övervakning för {symbol}")

        except Exception as e:
            logger.error(f"❌ Fel vid start av övervakning för {symbol}: {e}")

    async def stop_monitoring(self, symbol: str):
        """
        Stoppar övervakning av en symbol.

        Args:
            symbol: Trading pair
        """
        try:
            if symbol in self.active_symbols:
                self.active_symbols.remove(symbol)

                # Ta bort callback
                if symbol in self.signal_callbacks:
                    del self.signal_callbacks[symbol]

                logger.info(f"🛑 Stoppade övervakning för {symbol}")
            else:
                logger.warning(f"⚠️ {symbol} övervakades inte")

        except Exception as e:
            logger.error(f"❌ Fel vid stopp av övervakning för {symbol}: {e}")

    async def _handle_strategy_result(self, result: dict):
        """
        Hanterar strategi-resultat från WebSocket.

        Args:
            result: Strategi-resultat med signal och data
        """
        try:
            symbol = result.get("symbol", "unknown")
            signal = result.get("signal", "UNKNOWN")
            price = result.get("current_price", 0)

            # Spara senaste resultat
            self.strategy_results[symbol] = result

            # Logga signal
            logger.info(f"🎯 {symbol}: {signal} @ ${price:,.2f} - {result.get('reason', '')}")

            # Anropa callback om den finns
            if symbol in self.signal_callbacks:
                await self.signal_callbacks[symbol](result)

            # Skicka via WebSocket till klienter
            await self._broadcast_signal(result)

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av strategi-resultat: {e}")

    async def _broadcast_signal(self, result: dict):
        """
        Skickar signal via WebSocket till anslutna klienter.

        Args:
            result: Strategi-resultat
        """
        try:
            # Använd delad Socket.IO-server
            from ws.manager import socket_app

            await socket_app.emit("strategy_signal", result)

        except Exception as e:
            logger.error(f"❌ Fel vid broadcast av signal: {e}")

    def get_latest_signal(self, symbol: str) -> dict | None:
        """
        Hämtar senaste signal för en symbol.

        Args:
            symbol: Trading pair

        Returns:
            Senaste strategi-resultat eller None
        """
        return self.strategy_results.get(symbol)

    def get_all_signals(self) -> dict[str, dict]:
        """
        Hämtar alla aktiva signaler.

        Returns:
            Dict med alla aktiva signaler
        """
        return self.strategy_results.copy()

    def get_active_symbols(self) -> list[str]:
        """
        Hämtar lista över aktiva symboler.

        Returns:
            Lista med aktiva symboler
        """
        return list(self.active_symbols)

    async def stop_all_monitoring(self):
        """Stoppar all övervakning."""
        try:
            symbols_to_stop = list(self.active_symbols)
            for symbol in symbols_to_stop:
                await self.stop_monitoring(symbol)

            self.is_running = False
            logger.info("🛑 Stoppade all realtids övervakning")

        except Exception as e:
            logger.error(f"❌ Fel vid stopp av all övervakning: {e}")


# Global instans för enkel åtkomst
realtime_strategy = RealtimeStrategyService()
