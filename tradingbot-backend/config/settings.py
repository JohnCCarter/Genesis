"""
Configuration Settings - TradingBot Backend

Hanterar applikationens konfiguration via miljövariabler.
Projektet använder Pydantic v1 (BaseSettings) enligt requirements.
"""

import os as _os
from typing import List, Optional

from pydantic import BaseSettings as _BaseSettings


class Settings(_BaseSettings):
    """Konfigurationsklass för applikationsinställningar."""

    # Applikationskonfiguration
    CORE_MODE: bool = False  # Enkel drift: endast kärnfunktioner aktiva
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    # Kräv JWT för REST/WS. Sätt False i dev för att tillfälligt stänga av
    AUTH_REQUIRED: bool = True

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # Bitfinex REST API - för orderläggning och kontohantering
    BITFINEX_API_KEY: Optional[str] = None
    BITFINEX_API_SECRET: Optional[str] = None
    # REST (auth) bas-URL
    BITFINEX_API_URL: str = "https://api.bitfinex.com/v2"
    # Valfri separat AUTH-bas-URL (om satt i .env har den företräde för auth-anrop)
    BITFINEX_AUTH_API_URL: Optional[str] = None
    # REST (public) bas-URL – använd api-pub för publika endpoints
    BITFINEX_PUBLIC_API_URL: str = "https://api-pub.bitfinex.com/v2"

    # Bitfinex WebSocket API - separera public vs auth domäner
    BITFINEX_WS_API_KEY: Optional[str] = None
    BITFINEX_WS_API_SECRET: Optional[str] = None
    # WS public endast: api-pub
    BITFINEX_WS_PUBLIC_URI: str = "wss://api-pub.bitfinex.com/ws/2"
    # WS auth endast: api
    BITFINEX_WS_AUTH_URI: str = "wss://api.bitfinex.com/ws/2"
    # Bakåtkompatibel (används ej längre om de två ovan finns)
    BITFINEX_WS_URI: str = "wss://api.bitfinex.com/ws/2"

    # WS multi-socket (publika kanaler)
    WS_USE_POOL: bool = True
    WS_MAX_SUBS_PER_SOCKET: int = 200
    WS_PUBLIC_SOCKETS_MAX: int = 3

    # Lista över symboler att auto‑subscriba vid startup (komma‑separerad)
    WS_SUBSCRIBE_SYMBOLS: Optional[str] = None

    # JWT Autentisering
    JWT_SECRET_KEY: str = "your_jwt_secret_key_here"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Socket.IO autentisering
    SOCKETIO_JWT_SECRET: str = "socket_io_secret_key_here"

    # Loggning
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "tradingbot.log"

    # Trading konfiguration
    DEFAULT_TRADING_PAIR: str = "BTCUSD"
    MAX_POSITION_SIZE: float = 0.01
    RISK_PERCENTAGE: float = 2.0

    # Risk- och handelsregler
    TIMEZONE: str = "UTC"
    TRADING_RULES_FILE: str = "config/trading_rules.json"
    MAX_TRADES_PER_DAY: int = 10
    # Per-symbol daglig gräns (0 = inaktiverad)
    MAX_TRADES_PER_SYMBOL_PER_DAY: int = 0
    TRADE_COOLDOWN_SECONDS: int = 60
    TRADING_PAUSED: bool = False
    # Persistensfil för trade counter
    TRADE_COUNTER_FILE: str = "config/trade_counter.json"

    # Bracket/OCO state (persistens för GID-gruppering och återhämtning)
    BRACKET_STATE_FILE: str = "config/bracket_state.json"
    BRACKET_PARTIAL_ADJUST: bool = False

    # Circuit Breaker
    CB_ENABLED: bool = True
    CB_ERROR_WINDOW_SECONDS: int = 60
    CB_MAX_ERRORS_PER_WINDOW: int = 5
    CB_NOTIFY: bool = True

    # Telegram notifieringar
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # SMTP (från din .env)
    SMTP_PORT: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    # Exchange ID
    EXCHANGE_ID: Optional[str] = None

    # Nätverksinställningar (timeouts/retries)
    DATA_HTTP_TIMEOUT: float = 10.0
    DATA_MAX_RETRIES: int = 3
    DATA_BACKOFF_BASE_MS: int = 250
    DATA_BACKOFF_MAX_MS: int = 2000
    ORDER_HTTP_TIMEOUT: float = 15.0
    ORDER_MAX_RETRIES: int = 2
    ORDER_BACKOFF_BASE_MS: int = 300
    ORDER_BACKOFF_MAX_MS: int = 2000

    # WS ticker prioritet: anse WS-data färsk i X sekunder innan REST-fallback
    WS_TICKER_STALE_SECS: int = 10
    # Vänta kort på första WS‑tick efter auto‑subscribe innan REST‑fallback (ms)
    WS_TICKER_WARMUP_MS: int = 400

    # REST ticker cache TTL för att undvika överpollning
    TICKER_CACHE_TTL_SECS: int = 10

    # Candle cache retention
    CANDLE_CACHE_RETENTION_DAYS: int = 7
    CANDLE_CACHE_MAX_ROWS_PER_PAIR: int = 10000

    # Metrics security
    METRICS_ACCESS_TOKEN: Optional[str] = None
    METRICS_BASIC_AUTH_USER: Optional[str] = None
    METRICS_BASIC_AUTH_PASS: Optional[str] = None
    # Kommaseparerad lista över tillåtna IP:n (ex: "127.0.0.1,10.0.0.5")
    METRICS_IP_ALLOWLIST: Optional[str] = None

    # Säkerställ absolut sökväg till .env oavsett var processen startas
    class Config:
        env_file = _os.path.join(
            _os.path.dirname(_os.path.dirname(__file__)),
            ".env",
        )
        case_sensitive = False
        extra = "allow"  # Tillåt extra fält från .env
