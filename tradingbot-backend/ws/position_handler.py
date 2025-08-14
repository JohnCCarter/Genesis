"""
Position WebSocket Handler - TradingBot Backend

Denna modul hanterar positionsuppdateringar via WebSocket-anslutning till Bitfinex.
"""

import asyncio
from typing import Any, Callable, Dict, List

from config.settings import Settings
from utils.logger import get_logger
from ws.auth import build_ws_auth_payload

logger = get_logger(__name__)


class WSPositionHandler:
    """Klass för att hantera positionsuppdateringar via WebSocket."""

    def __init__(self, sio_client, bitfinex_ws_service):
        """
        Initialiserar WSPositionHandler.

        Args:
            sio_client: Socket.IO-klient för kommunikation med frontend
            bitfinex_ws_service: Bitfinex WebSocket-service
        """
        self.sio = sio_client
        self.bitfinex_ws = bitfinex_ws_service
        self.settings = Settings()
        self.authenticated = False
        self.positions = []
        self.position_callbacks = []

    async def authenticate(self) -> bool:
        """
        Autentiserar WebSocket-anslutningen för att få åtkomst till positionsuppdateringar.

        Returns:
            bool: True om autentiseringen lyckades, False annars
        """
        if self.authenticated:
            logger.info("WebSocket redan autentiserad för positionsuppdateringar")
            return True

        try:
            auth_payload = build_ws_auth_payload()

            # Registrera callback för att hantera autentiseringssvar
            auth_future = asyncio.Future()

            def on_auth_response(msg):
                if isinstance(msg, list) and msg[1] == "ps":
                    logger.info("WebSocket autentisering lyckades för positionsuppdateringar")
                    self.positions = msg[2] if len(msg) > 2 else []
                    self.authenticated = True
                    if not auth_future.done():
                        auth_future.set_result(True)
                elif isinstance(msg, list) and msg[1] == "error":
                    logger.error(f"WebSocket autentiseringsfel för positionsuppdateringar: {msg}")
                    if not auth_future.done():
                        auth_future.set_result(False)

            # Registrera callback för autentiseringssvar
            self.bitfinex_ws.register_handler("ps", on_auth_response)
            self.bitfinex_ws.register_handler("auth", on_auth_response)

            # Skicka autentiseringsmeddelande
            await self.bitfinex_ws.send(auth_payload)

            # Vänta på autentiseringssvar med timeout
            try:
                result = await asyncio.wait_for(auth_future, timeout=10.0)
                return result
            except asyncio.TimeoutError:
                logger.error("Timeout vid WebSocket-autentisering för positionsuppdateringar")
                return False

        except Exception as e:
            logger.exception(f"Fel vid WebSocket-autentisering för positionsuppdateringar: {e}")
            return False

    def register_position_callback(self, callback: Callable[[List[Dict[str, Any]]], None]) -> None:
        """
        Registrerar en callback-funktion som anropas när positionsuppdateringar tas emot.

        Args:
            callback: Callback-funktion som tar emot en lista med positioner
        """
        self.position_callbacks.append(callback)

    async def start_position_updates(self) -> bool:
        """
        Startar prenumeration på positionsuppdateringar.

        Returns:
            bool: True om prenumerationen startades, False annars
        """
        if not self.authenticated:
            success = await self.authenticate()
            if not success:
                return False

        try:
            # Registrera callback för att hantera positionsuppdateringar
            def on_position_update(msg):
                if isinstance(msg, list) and len(msg) > 1:
                    if msg[1] == "pu":  # Position Update
                        position_data = msg[2]
                        self._process_position_update(position_data)
                    elif msg[1] == "ps":  # Position Snapshot
                        position_data = msg[2]
                        self._process_position_snapshot(position_data)
                    elif msg[1] == "pc":  # Position Close
                        position_data = msg[2]
                        self._process_position_close(position_data)

            # Registrera callback för positionsuppdateringar
            self.bitfinex_ws.register_handler("pu", on_position_update)
            self.bitfinex_ws.register_handler("ps", on_position_update)
            self.bitfinex_ws.register_handler("pc", on_position_update)

            logger.info("Prenumeration på positionsuppdateringar startad")
            return True

        except Exception as e:
            logger.exception(f"Fel vid start av positionsuppdateringar: {e}")
            return False

    def _process_position_update(self, position_data: List[Any]) -> None:
        """
        Bearbetar en positionsuppdatering.

        Args:
            position_data: Positionsdata från WebSocket
        """
        try:
            if not isinstance(position_data, list) or len(position_data) < 6:
                logger.warning(f"Ogiltig positionsuppdatering: {position_data}")
                return

            symbol = position_data[0]
            status = position_data[1]
            amount = float(position_data[2])
            base_price = float(position_data[3])
            funding = float(position_data[4]) if len(position_data) > 4 else 0.0
            funding_type = int(position_data[5]) if len(position_data) > 5 else 0

            # Uppdatera intern positionslista
            updated = False
            for i, position in enumerate(self.positions):
                if isinstance(position, list) and len(position) >= 1 and position[0] == symbol:
                    self.positions[i] = position_data
                    updated = True
                    break

            if not updated:
                self.positions.append(position_data)

            # Formatera position för callbacks
            formatted_position = {
                "symbol": symbol,
                "status": status,
                "amount": amount,
                "base_price": base_price,
                "funding": funding,
                "funding_type": funding_type,
                "is_long": amount > 0,
                "is_short": amount < 0,
            }

            # Anropa callbacks
            for callback in self.position_callbacks:
                try:
                    callback([formatted_position])
                except Exception as e:
                    logger.error(f"Fel i positions-callback: {e}")

            # Skicka uppdatering till frontend via Socket.IO
            asyncio.create_task(self.sio.emit("position_update", formatted_position))

            logger.debug(f"Positionsuppdatering bearbetad: {symbol} {status} {amount}")

        except Exception as e:
            logger.error(f"Fel vid bearbetning av positionsuppdatering: {e}")

    def _process_position_snapshot(self, positions_data: List[List[Any]]) -> None:
        """
        Bearbetar en positions-snapshot (alla positioner).

        Args:
            positions_data: Lista med positioner från WebSocket
        """
        try:
            if not isinstance(positions_data, list):
                logger.warning(f"Ogiltig positions-snapshot: {positions_data}")
                return

            # Uppdatera intern positionslista
            self.positions = positions_data

            # Formatera positioner för callbacks
            formatted_positions = []
            for position in positions_data:
                if isinstance(position, list) and len(position) >= 6:
                    amount = float(position[2])
                    formatted_position = {
                        "symbol": position[0],
                        "status": position[1],
                        "amount": amount,
                        "base_price": float(position[3]),
                        "funding": float(position[4]) if len(position) > 4 else 0.0,
                        "funding_type": int(position[5]) if len(position) > 5 else 0,
                        "is_long": amount > 0,
                        "is_short": amount < 0,
                    }
                    formatted_positions.append(formatted_position)

            # Anropa callbacks
            for callback in self.position_callbacks:
                try:
                    callback(formatted_positions)
                except Exception as e:
                    logger.error(f"Fel i positions-callback: {e}")

            # Skicka uppdatering till frontend via Socket.IO
            asyncio.create_task(self.sio.emit("position_snapshot", formatted_positions))

            logger.info(f"Positions-snapshot bearbetad: {len(formatted_positions)} positioner")

        except Exception as e:
            logger.error(f"Fel vid bearbetning av positions-snapshot: {e}")

    def _process_position_close(self, position_data: List[Any]) -> None:
        """
        Bearbetar en positionsstängning.

        Args:
            position_data: Positionsdata från WebSocket
        """
        try:
            if not isinstance(position_data, list) or len(position_data) < 1:
                logger.warning(f"Ogiltig positionsstängning: {position_data}")
                return

            symbol = position_data[0]

            # Ta bort från intern positionslista
            self.positions = [
                p
                for p in self.positions
                if not (isinstance(p, list) and len(p) >= 1 and p[0] == symbol)
            ]

            # Formatera position för callbacks
            formatted_position = {"symbol": symbol, "status": "CLOSED", "closed": True}

            # Anropa callbacks
            for callback in self.position_callbacks:
                try:
                    callback([formatted_position])
                except Exception as e:
                    logger.error(f"Fel i positions-callback: {e}")

            # Skicka uppdatering till frontend via Socket.IO
            asyncio.create_task(self.sio.emit("position_close", formatted_position))

            logger.info(f"Position stängd: {symbol}")

        except Exception as e:
            logger.error(f"Fel vid bearbetning av positionsstängning: {e}")

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Hämtar alla positioner från senaste snapshot.

        Returns:
            Lista med positioner
        """
        if not self.authenticated:
            success = await self.authenticate()
            if not success:
                return []

        # Formatera positioner
        formatted_positions = []
        for position in self.positions:
            if isinstance(position, list) and len(position) >= 6:
                amount = float(position[2])
                formatted_position = {
                    "symbol": position[0],
                    "status": position[1],
                    "amount": amount,
                    "base_price": float(position[3]),
                    "funding": float(position[4]) if len(position) > 4 else 0.0,
                    "funding_type": int(position[5]) if len(position) > 5 else 0,
                    "is_long": amount > 0,
                    "is_short": amount < 0,
                }
                formatted_positions.append(formatted_position)

        return formatted_positions
