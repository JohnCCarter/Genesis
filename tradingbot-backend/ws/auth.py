"""
WebSocket Authentication - TradingBot Backend

Denna modul hanterar autentisering för WebSocket-anslutningar.
Inkluderar token validering för Socket.IO events.
"""

from datetime import datetime
from typing import Any, Dict

import jwt

from config.settings import Settings
from services.exchange_client import get_exchange_client
from utils.logger import get_logger

logger = get_logger(__name__)

# Bitfinex WebSocket API credentials - separata nycklar för WebSocket
settings = Settings()
# Logga status (utan att visa nycklarna)
logger.info(f"WebSocket API Key status: {'✅ Konfigurerad' if settings.BITFINEX_WS_API_KEY else '❌ Saknas'}")
logger.info(f"WebSocket API Secret status: {'✅ Konfigurerad' if settings.BITFINEX_WS_API_SECRET else '❌ Saknas'}")


def build_ws_auth_payload() -> str:
    """Bygg WS-auth via ExchangeClient (central källa)."""
    return get_exchange_client().build_ws_auth_payload()


# JWT Secret för socket.io autentisering
JWT_SECRET = settings.SOCKETIO_JWT_SECRET or "socket-io-secret"


def generate_token(user_id: str, scope: str = "read", expiry_minutes: int = 15) -> dict:
    """
    Genererar JWT-token med kortare livstid och refresh token för Socket.IO-autentisering.

    Args:
        user_id: Användar-ID eller användarnamn
        scope: Behörighetsomfattning ('read', 'write', 'admin')
        expiry_minutes: Antal minuter tills access token upphör (default 15 min)

    Returns:
        dict: JWT access_token, refresh_token och metadata
    """
    import time
    import uuid

    now = int(time.time())
    access_expiry = now + (expiry_minutes * 60)  # Kort livstid (15 minuter)
    refresh_expiry = now + (24 * 60 * 60)  # Refresh token varar 24 timmar

    # Generera unik token-ID för att kunna återkalla tokens
    token_id = str(uuid.uuid4())

    # Access token payload
    access_payload = {
        "sub": user_id,
        "scope": scope,
        "type": "access",
        "jti": token_id,
        "iat": now,
        "exp": access_expiry,
    }

    # Refresh token payload
    refresh_payload = {
        "sub": user_id,
        "scope": scope,
        "type": "refresh",
        "jti": token_id,
        "iat": now,
        "exp": refresh_expiry,
    }

    try:
        access_token = jwt.encode(access_payload, JWT_SECRET, algorithm="HS256")
        refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm="HS256")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": expiry_minutes * 60,
            "scope": scope,
            "user_id": user_id,
        }
    except Exception as e:
        from utils.token_masking import safe_log_data

        logger.error(safe_log_data(e, "Fel vid generering av tokens"))
        return None


def validate_token(token: str) -> Dict[str, Any]:
    """
    Validerar JWT-token för Socket.IO-autentisering.

    Args:
        token: JWT-token att validera

    Returns:
        Dict: Token payload om giltig, annars None
    """
    try:
        # Dekodera utan verifiering först för att logga information
        unverified = jwt.decode(token, options={"verify_signature": False})
        token_type = unverified.get("type", "access")

        # Sedan utför vi den verkliga verifieringen
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

        # Kontrollera om token är aktiv och inte har löpt ut
        current_time = int(datetime.now().timestamp())

        if payload.get("exp", 0) < current_time:
            logger.warning(f"Token har löpt ut för användare {payload.get('sub')}")
            return None

        logger.info(f"{token_type.capitalize()}-token validerad för användare {payload.get('sub')}")
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("Token har löpt ut")
        return None
    except jwt.InvalidTokenError as e:
        from utils.token_masking import mask_token, safe_log_data

        logger.warning(safe_log_data(e, f"Ogiltig token: {mask_token(token)}"))
        return None
    except Exception as e:
        from utils.token_masking import mask_token, safe_log_data

        logger.error(safe_log_data(e, f"Fel vid validering av token: {mask_token(token)}"))
        return None


def refresh_access_token(refresh_token: str) -> dict:
    """
    Förnyar en access token med hjälp av en giltig refresh token.

    Args:
        refresh_token: JWT refresh token

    Returns:
        dict: Ny access_token och metadata eller None vid fel
    """
    try:
        # Validera refresh token
        payload = validate_token(refresh_token)

        if not payload:
            logger.warning("❌ Ogiltig refresh token")
            return None

        # Kontrollera att det är en refresh token
        if payload.get("type") != "refresh":
            logger.warning("❌ Försök att förnya med fel typ av token")
            return None

        # Generera ny access token med samma användarinformation
        user_id = payload.get("sub")
        scope = payload.get("scope", "read")
        jti = payload.get("jti")  # Behåll samma token ID

        # Standard livstid för förnyad token är 15 minuter
        expiry_minutes = 15

        # Skapa ny access token
        now = int(datetime.now().timestamp())
        access_expiry = now + (expiry_minutes * 60)

        access_payload = {
            "sub": user_id,
            "scope": scope,
            "type": "access",
            "jti": jti,
            "iat": now,
            "exp": access_expiry,
            "renewed": True,  # Markera att detta är en förnyad token
        }

        access_token = jwt.encode(access_payload, JWT_SECRET, algorithm="HS256")

        logger.info(f"✅ Access token förnyad för användare {user_id}")

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": expiry_minutes * 60,
            "scope": scope,
            "user_id": user_id,
        }

    except Exception as e:
        logger.error(f"❌ Fel vid förnyelse av token: {e}")
        return None


def authenticate_socket_io(environ) -> bool:
    """
    Autentiserar Socket.IO-anslutning baserat på Authorization-header.

    Args:
        environ: Socket.IO miljö-dictionary

    Returns:
        bool: True om autentiseringen lyckades, annars False
    """
    try:
        # Detaljerad loggning för debugging
        logger.info(f"Socket.IO anslutningsförsök från {environ.get('REMOTE_ADDR', 'okänd')}")
        logger.info(f"HTTP_USER_AGENT: {environ.get('HTTP_USER_AGENT', 'okänd')}")

        # Temporär fix: Tillåt anslutning från localhost utan autentisering för utveckling
        remote_addr = environ.get("REMOTE_ADDR", "")
        if remote_addr in ["127.0.0.1", "localhost", "::1"]:
            logger.info("🔓 Tillåter localhost-anslutning utan autentisering (utvecklingsläge)")
            environ["user"] = {"sub": "localhost_user", "scope": "read"}
            return True

        # Hämta Authorization-header
        auth_header = environ.get("HTTP_AUTHORIZATION", "")

        # Om ingen Authorization-header finns, prova query-parameter som fallback
        if not auth_header:
            from urllib.parse import parse_qs

            query = environ.get("QUERY_STRING", "")
            params = parse_qs(query)
            token_param = params.get("token", [None])[0]

            if token_param:
                logger.warning("⚠️ Token skickades via URL-parameter istället för Authorization-header")
                auth_header = f"Bearer {token_param}"
            else:
                logger.warning("❌ Ingen Authorization-header eller token-parameter hittades")
                return False

        # Extrahera token från Authorization-header (format: "Bearer TOKEN")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Ta bort "Bearer " prefix
        else:
            logger.warning("❌ Felaktigt format på Authorization-header (måste vara 'Bearer TOKEN')")
            return False

        # Validera token
        payload = validate_token(token)

        if not payload:
            logger.warning("❌ Token validering misslyckades")
            return False

        # Kontrollera NTP-drift mellan client och server
        current_time = int(datetime.now().timestamp())
        token_iat = payload.get("iat", 0)

        # Tillåt max 5 minuters drift mellan klient och server
        if abs(current_time - token_iat) > 300:
            logger.warning(f"⚠️ Möjlig NTP-drift detekterad. Server: {current_time}, Token: {token_iat}")
            # Vi tillåter det ändå men loggar varningen

        # Sätt användarinformation i environ för senare användning
        environ["user"] = payload
        logger.info(f"✅ Autentisering lyckades för användare: {payload.get('sub')}")
        return True

    except Exception as e:
        logger.error(f"❌ Fel vid autentisering av Socket.IO: {e}")
        return False
