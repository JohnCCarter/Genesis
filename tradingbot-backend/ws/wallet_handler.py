"""
Wallet WebSocket Handler - TradingBot Backend

Denna modul hanterar plånboksuppdateringar via WebSocket-anslutning till Bitfinex.
"""

import asyncio
from typing import Any, Callable, Dict, List

from config.settings import Settings
from utils.logger import get_logger
from ws.auth import build_ws_auth_payload

logger = get_logger(__name__)


class WSWalletHandler:
    """Klass för att hantera plånboksuppdateringar via WebSocket."""

    def __init__(self, sio_client, bitfinex_ws_service):
        """
        Initialiserar WSWalletHandler.

        Args:
            sio_client: Socket.IO-klient för kommunikation med frontend
            bitfinex_ws_service: Bitfinex WebSocket-service
        """
        self.sio = sio_client
        self.bitfinex_ws = bitfinex_ws_service
        self.settings = Settings()
        self.authenticated = False
        self.wallets = []
        self.wallet_callbacks = []

    async def authenticate(self) -> bool:
        """
        Autentiserar WebSocket-anslutningen för att få åtkomst till plånboksuppdateringar.

        Returns:
            bool: True om autentiseringen lyckades, False annars
        """
        if self.authenticated:
            logger.info("WebSocket redan autentiserad för plånboksuppdateringar")
            return True

        try:
            auth_payload = build_ws_auth_payload()

            # Registrera callback för att hantera autentiseringssvar
            auth_future = asyncio.Future()

            def on_auth_response(msg):
                if isinstance(msg, list) and msg[1] == "ws":
                    logger.info(
                        "WebSocket autentisering lyckades för plånboksuppdateringar"
                    )
                    self.wallets = msg[2] if len(msg) > 2 else []
                    self.authenticated = True
                    if not auth_future.done():
                        auth_future.set_result(True)
                elif isinstance(msg, list) and msg[1] == "error":
                    logger.error(
                        f"WebSocket autentiseringsfel för plånboksuppdateringar: {msg}"
                    )
                    if not auth_future.done():
                        auth_future.set_result(False)

            # Registrera callback för autentiseringssvar
            self.bitfinex_ws.register_handler("ws", on_auth_response)
            self.bitfinex_ws.register_handler("auth", on_auth_response)

            # Skicka autentiseringsmeddelande
            await self.bitfinex_ws.send(auth_payload)

            # Vänta på autentiseringssvar med timeout
            try:
                result = await asyncio.wait_for(auth_future, timeout=10.0)
                return result
            except asyncio.TimeoutError:
                logger.error(
                    "Timeout vid WebSocket-autentisering för plånboksuppdateringar"
                )
                return False

        except Exception as e:
            logger.exception(
                f"Fel vid WebSocket-autentisering för plånboksuppdateringar: {e}"
            )
            return False

    def register_wallet_callback(
        self, callback: Callable[[List[Dict[str, Any]]], None]
    ) -> None:
        """
        Registrerar en callback-funktion som anropas när plånboksuppdateringar tas emot.

        Args:
            callback: Callback-funktion som tar emot en lista med plånböcker
        """
        self.wallet_callbacks.append(callback)

    async def start_wallet_updates(self) -> bool:
        """
        Startar prenumeration på plånboksuppdateringar.

        Returns:
            bool: True om prenumerationen startades, False annars
        """
        if not self.authenticated:
            success = await self.authenticate()
            if not success:
                return False

        try:
            # Registrera callback för att hantera plånboksuppdateringar
            def on_wallet_update(msg):
                if isinstance(msg, list) and len(msg) > 1:
                    if msg[1] == "wu":  # Wallet Update
                        wallet_data = msg[2]
                        self._process_wallet_update(wallet_data)
                    elif msg[1] == "ws":  # Wallet Snapshot
                        wallet_data = msg[2]
                        self._process_wallet_snapshot(wallet_data)

            # Registrera callback för plånboksuppdateringar
            self.bitfinex_ws.register_handler("wu", on_wallet_update)
            self.bitfinex_ws.register_handler("ws", on_wallet_update)

            logger.info("Prenumeration på plånboksuppdateringar startad")
            return True

        except Exception as e:
            logger.exception(f"Fel vid start av plånboksuppdateringar: {e}")
            return False

    def _process_wallet_update(self, wallet_data: List[Any]) -> None:
        """
        Bearbetar en plånboksuppdatering.

        Args:
            wallet_data: Plånboksdata från WebSocket
        """
        try:
            if not isinstance(wallet_data, list) or len(wallet_data) < 4:
                logger.warning(f"Ogiltig plånboksuppdatering: {wallet_data}")
                return

            wallet_type = wallet_data[0]
            currency = wallet_data[1]
            balance = float(wallet_data[2])
            unsettled_interest = float(wallet_data[3]) if len(wallet_data) > 3 else 0.0
            available_balance = float(wallet_data[4]) if len(wallet_data) > 4 else None

            # Uppdatera intern plånbokslista
            updated = False
            for i, wallet in enumerate(self.wallets):
                if (
                    isinstance(wallet, list)
                    and len(wallet) >= 2
                    and wallet[0] == wallet_type
                    and wallet[1] == currency
                ):
                    self.wallets[i] = wallet_data
                    updated = True
                    break

            if not updated:
                self.wallets.append(wallet_data)

            # Formatera plånbok för callbacks
            formatted_wallet = {
                "wallet_type": wallet_type,
                "currency": currency,
                "balance": balance,
                "unsettled_interest": unsettled_interest,
                "available_balance": available_balance,
            }

            # Anropa callbacks
            for callback in self.wallet_callbacks:
                try:
                    callback([formatted_wallet])
                except Exception as e:
                    logger.error(f"Fel i plånboks-callback: {e}")

            # Skicka uppdatering till frontend via Socket.IO
            asyncio.create_task(self.sio.emit("wallet_update", formatted_wallet))

            logger.debug(
                f"Plånboksuppdatering bearbetad: {wallet_type} {currency} {balance}"
            )

        except Exception as e:
            logger.error(f"Fel vid bearbetning av plånboksuppdatering: {e}")

    def _process_wallet_snapshot(self, wallets_data: List[List[Any]]) -> None:
        """
        Bearbetar en plånboks-snapshot (alla plånböcker).

        Args:
            wallets_data: Lista med plånböcker från WebSocket
        """
        try:
            if not isinstance(wallets_data, list):
                logger.warning(f"Ogiltig plånboks-snapshot: {wallets_data}")
                return

            # Uppdatera intern plånbokslista
            self.wallets = wallets_data

            # Formatera plånböcker för callbacks
            formatted_wallets = []
            for wallet in wallets_data:
                if isinstance(wallet, list) and len(wallet) >= 4:
                    formatted_wallet = {
                        "wallet_type": wallet[0],
                        "currency": wallet[1],
                        "balance": float(wallet[2]),
                        "unsettled_interest": (
                            float(wallet[3]) if len(wallet) > 3 else 0.0
                        ),
                        "available_balance": (
                            float(wallet[4]) if len(wallet) > 4 else None
                        ),
                    }
                    formatted_wallets.append(formatted_wallet)

            # Anropa callbacks
            for callback in self.wallet_callbacks:
                try:
                    callback(formatted_wallets)
                except Exception as e:
                    logger.error(f"Fel i plånboks-callback: {e}")

            # Skicka uppdatering till frontend via Socket.IO
            asyncio.create_task(self.sio.emit("wallet_snapshot", formatted_wallets))

            logger.info(
                f"Plånboks-snapshot bearbetad: {len(formatted_wallets)} plånböcker"
            )

        except Exception as e:
            logger.error(f"Fel vid bearbetning av plånboks-snapshot: {e}")

    async def get_wallets(self) -> List[Dict[str, Any]]:
        """
        Hämtar alla plånböcker från senaste snapshot.

        Returns:
            Lista med plånböcker
        """
        if not self.authenticated:
            success = await self.authenticate()
            if not success:
                return []

        # Formatera plånböcker
        formatted_wallets = []
        for wallet in self.wallets:
            if isinstance(wallet, list) and len(wallet) >= 4:
                formatted_wallet = {
                    "wallet_type": wallet[0],
                    "currency": wallet[1],
                    "balance": float(wallet[2]),
                    "unsettled_interest": float(wallet[3]) if len(wallet) > 3 else 0.0,
                    "available_balance": float(wallet[4]) if len(wallet) > 4 else None,
                }
                formatted_wallets.append(formatted_wallet)

        return formatted_wallets
