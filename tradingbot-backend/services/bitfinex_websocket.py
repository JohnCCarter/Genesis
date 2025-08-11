"""
Bitfinex WebSocket Service - TradingBot Backend

Denna modul hanterar WebSocket-anslutning till Bitfinex för realtids tickdata.
Inkluderar automatisk återanslutning och tickdata-hantering.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import websockets  # pylint: disable=import-error,no-name-in-module

from config.settings import Settings
from utils.logger import get_logger
from ws.auth import build_ws_auth_payload

logger = get_logger(__name__)


class BitfinexWebSocketService:
    """Service för WebSocket-anslutning till Bitfinex."""

    def __init__(self):
        self.settings = Settings()
        self.ws_url = self.settings.BITFINEX_WS_URI
        self.websocket = None
        self.is_connected = False
        self.is_authenticated = False
        self.subscriptions = {}
        self.callbacks = {}
        self.private_event_callbacks = {}
        self.latest_prices = {}  # Spara senaste priser
        self.price_history = {}  # Spara pris-historik för strategi
        self.strategy_callbacks = {}  # Callbacks för strategiutvärdering
        # Synk-event för auth-ack
        import asyncio as _asyncio

        self._asyncio = _asyncio
        self._auth_event = _asyncio.Event()

    # Publikt API för andra moduler
    def register_handler(self, event_code: str, callback: Callable[[Any], Any]):
        """Registrera callback för privat kanal 0-event (t.ex. 'ws','wu','ps','pu','on','oc','te','tu','auth')."""
        self.private_event_callbacks[event_code] = callback

    async def send(self, payload: Any):
        """Skicka rått WS-meddelande. Accepterar dict (json.dumps) eller str."""
        try:
            if isinstance(payload, (dict, list)):
                await self.websocket.send(json.dumps(payload))
            elif isinstance(payload, str):
                await self.websocket.send(payload)
            else:
                await self.websocket.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"❌ WS send misslyckades: {e}")

    async def connect(self):
        """Ansluter till Bitfinex WebSocket."""
        try:
            logger.info("🔌 Ansluter till Bitfinex WebSocket...")
            # websockets.connect har dynamiska attribut i runtime; tysta pylint no-member här
            self.websocket = await websockets.connect(  # pylint: disable=no-member
                self.ws_url
            )
            self.is_connected = True
            logger.info("✅ Ansluten till Bitfinex WebSocket")
            # Starta lyssnare i bakgrunden direkt för att fånga auth-ack
            self._asyncio.create_task(self.listen_for_messages())
            # Försök autentisera om nycklar finns
            await self.authenticate()
            return True
        except Exception as e:
            logger.error(f"❌ WebSocket-anslutning misslyckades: {e}")
            return False

    async def authenticate(self):
        """Autentiserar WS-sessionen med Bitfinex v2 auth-event."""
        try:
            # Skicka auth-payload
            auth_msg = build_ws_auth_payload()
            await self.websocket.send(auth_msg)
            logger.info("🔐 WS auth skickad, inväntar bekräftelse...")
            try:
                await self._asyncio.wait_for(self._auth_event.wait(), timeout=10)
            except Exception:
                logger.warning(
                    "⚠️ Ingen auth-bekräftelse inom timeout. Fortsätter utan auth."
                )
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte skicka WS auth: {e}")

    async def send_conf(self, flags: int = 0):
        """Skickar conf-event för att aktivera flaggor (t.ex. seq/checksums)."""
        try:
            msg = {"event": "conf", "flags": flags}
            await self.websocket.send(json.dumps(msg))
            logger.info(f"⚙️ WS conf skickad med flags={flags}")
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte skicka conf: {e}")

    async def enable_dead_man_switch(self, timeout_ms: int = 60000):
        """Aktiverar Dead Man's Switch (auto-cancel vid frånkoppling)."""
        try:
            msg = {"event": "dms", "status": 1, "timeout": timeout_ms}
            await self.websocket.send(json.dumps(msg))
            logger.info(f"🛡️ WS DMS aktiverad med timeout={timeout_ms} ms")
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte aktivera DMS: {e}")

    def on_private_event(self, event_code: str, callback: Callable[[Any], Any]):
        """Registrerar callback för privat WS-event (t.ex. 'os','on','wu','tu',...)."""
        self.private_event_callbacks[event_code] = callback

    async def disconnect(self):
        """Kopplar från WebSocket."""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("🔌 Frånkopplad från Bitfinex WebSocket")

    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """
        Prenumererar på ticker-data för en symbol.

        Args:
            symbol: Trading pair (t.ex. 'tBTCUSD')
            callback: Funktion som anropas vid ny ticker-data
        """
        try:
            if not self.is_connected:
                await self.connect()

            # Skapa subscription-meddelande
            subscribe_msg = {
                "event": "subscribe",
                "channel": "ticker",
                "symbol": symbol,
            }

            await self.websocket.send(json.dumps(subscribe_msg))
            self.subscriptions[symbol] = subscribe_msg
            self.callbacks[symbol] = callback

            logger.info(f"📊 Prenumererar på ticker för {symbol}")

        except Exception as e:
            logger.error(f"❌ Ticker-prenumeration misslyckades: {e}")

    async def subscribe_trades(self, symbol: str, callback: Callable):
        """
        Prenumererar på trades-data för en symbol.

        Args:
            symbol: Trading pair
            callback: Funktion som anropas vid ny trade-data
        """
        try:
            if not self.is_connected:
                await self.connect()

            subscribe_msg = {
                "event": "subscribe",
                "channel": "trades",
                "symbol": symbol,
            }

            await self.websocket.send(json.dumps(subscribe_msg))
            self.subscriptions[f"{symbol}_trades"] = subscribe_msg
            self.callbacks[f"{symbol}_trades"] = callback

            logger.info(f"💱 Prenumererar på trades för {symbol}")

        except Exception as e:
            logger.error(f"❌ Trades-prenumeration misslyckades: {e}")

    async def subscribe_with_strategy_evaluation(self, symbol: str, callback: Callable):
        """
        Prenumererar på ticker och kör automatisk strategiutvärdering.

        Args:
            symbol: Trading pair (t.ex. 'tBTCUSD')
            callback: Funktion som anropas med strategi-resultat
        """
        try:
            if not self.is_connected:
                await self.connect()

            # Spara callback för strategiutvärdering
            self.strategy_callbacks[symbol] = callback

            # Prenumerera på ticker
            await self.subscribe_ticker(symbol, self._handle_ticker_with_strategy)

            logger.info(f"🎯 Prenumererar på {symbol} med strategiutvärdering")

        except Exception as e:
            logger.error(f"❌ Strategi-prenumeration misslyckades: {e}")

    async def _handle_ticker_with_strategy(self, ticker_data: Dict):
        """
        Hanterar ticker-data och kör strategiutvärdering.

        Args:
            ticker_data: Ticker-data från Bitfinex
        """
        try:
            symbol = ticker_data.get("symbol", "unknown")
            price = ticker_data.get("last_price", 0)

            # Uppdatera senaste pris
            self.latest_prices[symbol] = price

            # Lägg till i pris-historik (behåll senaste 100 datapunkter)
            if symbol not in self.price_history:
                self.price_history[symbol] = []

            self.price_history[symbol].append(price)
            if len(self.price_history[symbol]) > 100:
                self.price_history[symbol].pop(0)

            # Kör strategiutvärdering om vi har tillräckligt med data
            if len(self.price_history[symbol]) >= 30:  # Minst 30 datapunkter
                await self._evaluate_strategy_for_symbol(symbol)

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av ticker med strategi: {e}")

    async def _evaluate_strategy_for_symbol(self, symbol: str):
        """
        Utvärderar strategi för en symbol baserat på pris-historik.

        Args:
            symbol: Trading pair
        """
        try:
            from services.strategy import evaluate_strategy

            # Förbered data för strategiutvärdering
            prices = self.price_history[symbol]

            # Skapa mock-data för strategi (eftersom vi bara har closes)
            strategy_data = {
                "closes": prices,
                "highs": prices,  # Använd samma värden som approximation
                "lows": prices,  # Använd samma värden som approximation
            }

            # Utvärdera strategi
            result = evaluate_strategy(strategy_data)

            # Lägg till symbol och timestamp
            result["symbol"] = symbol
            result["current_price"] = self.latest_prices.get(symbol, 0)
            result["timestamp"] = datetime.now().isoformat()

            # Anropa callback om den finns
            if symbol in self.strategy_callbacks:
                await self.strategy_callbacks[symbol](result)

            logger.info(
                f"🎯 Strategiutvärdering för {symbol}: {result['signal']} - {result['reason']}"
            )

        except Exception as e:
            logger.error(f"❌ Fel vid strategiutvärdering för {symbol}: {e}")

    async def listen_for_messages(self):
        """Lyssnar på WebSocket-meddelanden."""
        try:
            logger.info("👂 Lyssnar på WebSocket-meddelanden...")

            async for message in self.websocket:
                try:
                    data = json.loads(message)

                    # Hantera olika meddelandetyper
                    if isinstance(data, list) and len(data) > 1:
                        await self._handle_channel_message(data)
                    elif isinstance(data, dict):
                        await self._handle_event_message(data)

                except json.JSONDecodeError:
                    logger.warning("⚠️ Kunde inte parsa WebSocket-meddelande")
                except Exception as e:
                    logger.error(f"❌ Fel vid hantering av WebSocket-meddelande: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ WebSocket-anslutning stängd")
            self.is_connected = False
        except Exception as e:
            logger.error(f"❌ WebSocket-lyssnare fel: {e}")

    async def _handle_channel_message(self, data: List):
        """Hanterar kanal-meddelanden (publika och privata)."""
        try:
            channel_id = data[0]
            message_data = data[1]

            # Privata kontohändelser sker på channel_id 0 med event-kod som andra element
            if channel_id == 0:
                # Format: [0, 'EVENT_CODE', payload]
                if isinstance(message_data, str):
                    event_code = message_data
                    cb = self.private_event_callbacks.get(event_code)
                    if cb:
                        # Skicka hela ursprungsmeddelandet så handlers kan läsa msg[1] och msg[2]
                        await cb(data)
                    else:
                        logger.debug(f"ℹ️ Ohanterad privat händelse: {event_code}")
                else:
                    # Heartbeat: [0, 'hb'] eller liknande
                    if message_data == "hb":
                        return
                    logger.debug(f"ℹ️ Oväntat privat meddelande: {data}")
                return

            # Publika ticker/trades
            if isinstance(message_data, list) and len(message_data) >= 7:
                ticker_data = {
                    "symbol": self._get_symbol_from_channel_id(channel_id),
                    "bid": message_data[0],
                    "bid_size": message_data[1],
                    "ask": message_data[2],
                    "ask_size": message_data[3],
                    "daily_change": message_data[4],
                    "daily_change_relative": message_data[5],
                    "last_price": message_data[6],
                    "volume": message_data[7] if len(message_data) > 7 else 0,
                    "high": message_data[8] if len(message_data) > 8 else 0,
                    "low": message_data[9] if len(message_data) > 9 else 0,
                }
                for symbol, callback in self.callbacks.items():
                    if symbol in ticker_data["symbol"]:
                        await callback(ticker_data)
                        break
            else:
                for symbol, callback in self.callbacks.items():
                    if symbol in str(message_data):
                        await callback(message_data)
                        break

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av kanal-meddelande: {e}")

    def _get_symbol_from_channel_id(self, channel_id: int) -> str:
        """Hämtar symbol från channel ID baserat på prenumerationer."""
        for symbol, sub_data in self.subscriptions.items():
            if "ticker" in str(sub_data):
                return symbol
        return "unknown"

    async def _handle_event_message(self, data: Dict):
        """Hanterar event-meddelanden (subscribe, auth, etc.)."""
        try:
            event = data.get("event")

            if event == "subscribed":
                logger.info(
                    f"✅ Prenumeration bekräftad: {data.get('symbol', 'unknown')}"
                )
            elif event == "auth":
                status = data.get("status")
                if status == "OK":
                    self.is_authenticated = True
                    self._auth_event.set()
                    logger.info("✅ WS auth bekräftad")
                else:
                    self.is_authenticated = False
                    self._auth_event.set()
                    logger.error(f"❌ WS auth misslyckades: {data}")
                # Vidarebefordra auth-event till ev. registrerad callback
                cb = self.private_event_callbacks.get("auth")
                if cb:
                    await cb(data)
            elif event == "error":
                logger.error(f"❌ WebSocket-fel: {data.get('msg', 'unknown error')}")
            elif event == "info":
                logger.info(f"ℹ️ WebSocket-info: {data.get('msg', 'no message')}")

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av event-meddelande: {e}")

    async def start_listening(self):
        """Startar WebSocket-lyssnare i bakgrunden."""
        if not self.is_connected:
            await self.connect()

        # Starta lyssnare i bakgrunden
        asyncio.create_task(self.listen_for_messages())
        logger.info("🚀 WebSocket-lyssnare startad")


# Global instans för enkel åtkomst
bitfinex_ws = BitfinexWebSocketService()
