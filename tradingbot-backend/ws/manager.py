"""
WebSocket Manager - TradingBot Backend

Denna modul hanterar WebSocket-anslutningar och Socket.IO-servern.
"""

import asyncio
from typing import Any, Callable, Dict, Optional

import socketio

from config.settings import Settings
from services.bracket_manager import bracket_manager
from utils.logger import get_logger
from ws.auth import authenticate_socket_io, generate_token
from ws.position_handler import WSPositionHandler
from ws.wallet_handler import WSWalletHandler

logger = get_logger(__name__)

# Skapa Socket.IO-server med autentisering
socket_app = socketio.AsyncServer(
    async_mode="asgi", cors_allowed_origins="*", logger=True, engineio_logger=True
)


# Wrapper för Socket.IO applikation med autentisering
# Använd auth middleware för att hantera autentisering
async def socket_auth_middleware(environ, send):
    # Logga anslutningsförsök
    logger.info(
        f"Socket.IO anslutningsförsök via middleware: {environ.get('REMOTE_ADDR', 'okänd')}"
    )

    # Använd autentiseringsfunktionen
    if authenticate_socket_io(environ):
        # Kopiera user till socket.io_user för kompatibilitet
        environ["socket.io_user"] = environ.get(
            "user", {"sub": "unknown", "scope": "none"}
        )
        return True
    else:
        logger.warning(
            f"❌ Socket.IO autentisering misslyckades från {environ.get('REMOTE_ADDR', 'okänd')}"
        )
        return False


# Skapa ASGI app med anpassad auth
socket_app_asgi = socketio.ASGIApp(socket_app, socketio_path="socket.io")


# Socket.IO-händelser
@socket_app.event
async def connect(sid, environ):
    """Autentiserad Socket.IO-anslutning. Avvisar utan giltig Bearer-token."""
    try:
        logger.info(f"Socket.IO anslutning för sid: {sid}")
        logger.info(f"QUERY_STRING: {environ.get('QUERY_STRING', 'okänd')}")
        logger.info(f"HTTP_ORIGIN: {environ.get('HTTP_ORIGIN', 'okänd')}")
        logger.info(f"PATH_INFO: {environ.get('PATH_INFO', 'okänd')}")

        # Respektera AUTH_REQUIRED för dev
        if Settings().AUTH_REQUIRED and not authenticate_socket_io(environ):
            logger.warning(f"❌ Socket.IO autentisering misslyckades för sid: {sid}")
            raise ConnectionRefusedError("unauthorized")

        user = environ.get("user", {"sub": "unknown"})
        await socket_app.emit(
            "authenticated", {"status": "success", "user": user.get("sub")}, room=sid
        )
        logger.info(f"✅ Socket.IO-klient autentiserad och ansluten: {sid}")
        return True
    except ConnectionRefusedError:
        raise
    except Exception as e:
        logger.error(f"Fel vid Socket.IO-anslutning: {e}")
        return False


@socket_app.event
async def disconnect(sid):
    """Hantera frånkoppling av klient."""
    logger.info(f"Socket.IO-klient frånkopplad: {sid}")


@socket_app.event
async def request_token(sid, data):
    """Generera och skicka en token med refresh token till klienten."""
    try:
        user_id = data.get("user_id", "frontend_user")
        scope = data.get("scope", "read")
        expiry_minutes = data.get("expiry_minutes", 15)  # Default 15 minuter

        # Använd ny token-generation med refresh tokens
        token_response = generate_token(user_id, scope, expiry_minutes)

        if token_response:
            await socket_app.emit("token_generated", token_response, room=sid)
            logger.info(f"✅ Token genererad för användare: {user_id}")
        else:
            await socket_app.emit(
                "token_error", {"error": "Kunde inte generera token"}, room=sid
            )
            logger.error(f"❌ Fel vid generering av token för användare: {user_id}")

    except Exception as e:
        logger.error(f"❌ Fel vid hantering av token-begäran: {e}")
        await socket_app.emit("token_error", {"error": str(e)}, room=sid)


@socket_app.event
async def refresh_token(sid, data):
    """Förnya en access token med hjälp av refresh token."""
    try:
        refresh_token = data.get("refresh_token")

        if not refresh_token:
            await socket_app.emit(
                "token_error", {"error": "Refresh token saknas"}, room=sid
            )
            logger.warning("❌ Refresh token saknas i begäran")
            return

        # Använd refresh_access_token för att generera ny access token
        token_response = refresh_access_token(refresh_token)

        if token_response:
            await socket_app.emit("token_refreshed", token_response, room=sid)
            logger.info(
                f"✅ Token förnyad för användare: {token_response.get('user_id')}"
            )
        else:
            await socket_app.emit(
                "token_error", {"error": "Kunde inte förnya token"}, room=sid
            )
            logger.warning("❌ Kunde inte förnya token")

    except Exception as e:
        logger.error(f"❌ Fel vid förnyelse av token: {e}")
        await socket_app.emit("token_error", {"error": str(e)}, room=sid)


class WebSocketManager:
    """Klass för att hantera WebSocket-anslutningar och handlers."""

    def __init__(self, bitfinex_ws_service):
        """
        Initialiserar WebSocketManager.

        Args:
            bitfinex_ws_service: Bitfinex WebSocket-service
        """
        self.bitfinex_ws = bitfinex_ws_service
        self.wallet_handler = WSWalletHandler(socket_app, bitfinex_ws_service)
        self.position_handler = WSPositionHandler(socket_app, bitfinex_ws_service)
        self.handlers = {}

    async def initialize(self):
        """
        Initialiserar WebSocket-hanterare.
        """
        logger.info("Initialiserar WebSocket-hanterare...")

        # Starta wallet-uppdateringar
        wallet_success = await self.wallet_handler.start_wallet_updates()
        if wallet_success:
            logger.info("Wallet-uppdateringar startade")
        else:
            logger.warning("Kunde inte starta wallet-uppdateringar")

        # Starta positions-uppdateringar
        position_success = await self.position_handler.start_position_updates()
        if position_success:
            logger.info("Positions-uppdateringar startade")
        else:
            logger.warning("Kunde inte starta positions-uppdateringar")

        # Registrera Socket.IO-händelser
        self._register_socketio_events()
        # Registrera Bitfinex privata WS-strömmar (orders, trades, mm)
        self._register_private_streams()

        logger.info("WebSocket-hanterare initialiserad")

    def _register_socketio_events(self):
        """
        Registrerar Socket.IO-händelser för att hantera klientförfrågningar.
        """

        @socket_app.event
        async def get_wallets(sid):
            """Hantera förfrågan om att hämta plånböcker."""
            try:
                wallets = await self.wallet_handler.get_wallets()
                await socket_app.emit("wallet_snapshot", wallets, room=sid)
                return {"success": True, "count": len(wallets)}
            except Exception as e:
                logger.error(f"Fel vid hämtning av plånböcker: {e}")
                return {"success": False, "error": str(e)}

        @socket_app.event
        async def get_positions(sid):
            """Hantera förfrågan om att hämta positioner."""
            try:
                positions = await self.position_handler.get_positions()
                await socket_app.emit("position_snapshot", positions, room=sid)
                return {"success": True, "count": len(positions)}
            except Exception as e:
                logger.error(f"Fel vid hämtning av positioner: {e}")
                return {"success": False, "error": str(e)}

        @socket_app.event
        async def ping_health(sid):
            """Returnera enkel hälsostatus till klienten."""
            try:
                from services.bitfinex_websocket import bitfinex_ws

                await socket_app.emit(
                    "health",
                    {
                        "ws_connected": bool(bitfinex_ws.is_connected),
                        "ws_authenticated": bool(bitfinex_ws.is_authenticated),
                    },
                    room=sid,
                )
                return {"success": True}
            except Exception as e:
                logger.error(f"Fel vid health: {e}")
                return {"success": False, "error": str(e)}

    def register_wallet_callback(self, callback: Callable[[list], None]):
        """
        Registrerar en callback-funktion för plånboksuppdateringar.

        Args:
            callback: Callback-funktion som anropas vid plånboksuppdateringar
        """
        self.wallet_handler.register_wallet_callback(callback)

    def register_position_callback(self, callback: Callable[[list], None]):
        """
        Registrerar en callback-funktion för positionsuppdateringar.

        Args:
            callback: Callback-funktion som anropas vid positionsuppdateringar
        """
        self.position_handler.register_position_callback(callback)

    def _register_private_streams(self):
        """Registrerar callbacks för Bitfinex privata händelser via kanal 0."""

        def _emit_safe(event: str, payload):
            try:
                # broadcast till alla
                asyncio.create_task(socket_app.emit(event, payload))
            except Exception as e:
                logger.error(f"Fel vid emit av {event}: {e}")

        # Order snapshot (os)
        async def on_os(msg):
            try:
                # msg: [0, 'os', [ ...orders... ]]
                snapshot = msg[2] if len(msg) > 2 else []
                _emit_safe("order_snapshot", snapshot)
            except Exception as e:
                logger.error(f"Fel i on_os: {e}")

        # Order new (on)
        async def on_on(msg):
            try:
                order = msg[2] if len(msg) > 2 else []
                _emit_safe("order_new", order)
            except Exception as e:
                logger.error(f"Fel i on_on: {e}")

        # Order update (ou)
        async def on_ou(msg):
            try:
                order = msg[2] if len(msg) > 2 else []
                _emit_safe("order_update", order)
            except Exception as e:
                logger.error(f"Fel i on_ou: {e}")

        # Order cancel (oc)
        async def on_oc(msg):
            try:
                order = msg[2] if len(msg) > 2 else []
                _emit_safe("order_cancel", order)
                # Informera BracketManager
                await bracket_manager.handle_private_event("oc", msg)
            except Exception as e:
                logger.error(f"Fel i on_oc: {e}")

        # Trade executions (te/tu)
        async def on_te(msg):
            try:
                trade = msg[2] if len(msg) > 2 else []
                _emit_safe("trade_executed", trade)
                await bracket_manager.handle_private_event("te", msg)
            except Exception as e:
                logger.error(f"Fel i on_te: {e}")

        async def on_tu(msg):
            try:
                trade = msg[2] if len(msg) > 2 else []
                _emit_safe("trade_update", trade)
                await bracket_manager.handle_private_event("tu", msg)
            except Exception as e:
                logger.error(f"Fel i on_tu: {e}")

        # Registrera i WS-servicen
        self.bitfinex_ws.register_handler("os", on_os)
        self.bitfinex_ws.register_handler("on", on_on)
        self.bitfinex_ws.register_handler("ou", on_ou)
        self.bitfinex_ws.register_handler("oc", on_oc)
        self.bitfinex_ws.register_handler("te", on_te)
        self.bitfinex_ws.register_handler("tu", on_tu)

        # Aktivera Dead Man's Switch när auth bekräftas
        async def on_auth(msg):
            try:
                # När auth OK, aktivera DMS
                await self.bitfinex_ws.enable_dead_man_switch(timeout_ms=60000)
                # Försök återregistrera brackets genom att bygga om child-index från sparad state
                try:
                    from services.bracket_manager import bracket_manager

                    # _load_state körs i init; child_to_group är redan byggd vid import
                    # Här kan vi logga hur många aktiva brackets som finns
                    logger.info(
                        f"BracketManager återhämtning: {len(bracket_manager.groups)} grupper aktiva efter reconnect"
                    )
                except Exception as ie:
                    logger.warning(f"BracketManager återhämtning misslyckades: {ie}")
            except Exception as e:
                logger.warning(f"Kunde inte aktivera DMS: {e}")

        self.bitfinex_ws.register_handler("auth", on_auth)

    # Hjälpmetod för att emit:a notifieringar
    @staticmethod
    async def notify(event_type: str, title: str, payload: Optional[dict] = None):
        try:
            await socket_app.emit(
                "notification",
                {"type": event_type, "title": title, "payload": payload or {}},
            )
        except Exception as e:
            logger.error(f"Fel vid notification emit: {e}")

    async def close(self):
        """
        Stänger WebSocket-anslutningar.
        """
        logger.info("Stänger WebSocket-anslutningar...")
        # Här skulle du lägga till kod för att stänga anslutningar om det behövs
        logger.info("WebSocket-anslutningar stängda")
