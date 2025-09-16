"""
Configuration Settings - TradingBot Backend

Hanterar applikationens konfiguration via miljövariabler.
Projektet använder Pydantic v1 (BaseSettings) enligt requirements.
"""

import os as _os

# Kompatibilitet: Pydantic v2 (pydantic-settings) och v1 (pydantic)
try:  # Pydantic v2
    from pydantic_settings import BaseSettings as _BaseSettings  # type: ignore

    print("Using pydantic-settings (v2)")
except ImportError:  # Fall tillbaka till v1
    try:
        from pydantic import BaseSettings as _BaseSettings  # type: ignore

        print("Using pydantic BaseSettings (v1)")
    except ImportError:
        raise ImportError("Neither pydantic-settings nor pydantic BaseSettings found") from None

_settings_instance = None


class Settings(_BaseSettings):
    """Konfigurationsklass för applikationsinställningar."""

    # Applikationskonfiguration
    # Bindningsadress: defaulta till loopback i dev, 0.0.0.0 i container/CI via env
    HOST: str = _os.environ.get("HOST", "127.0.0.1")
    PORT: int = 8000
    DEBUG: bool = True
    # Kräv JWT för REST/WS. Sätt False i dev för att tillfälligt stänga av
    AUTH_REQUIRED: bool = False

    # CORS
    ALLOWED_ORIGINS: str = (
        '["http://localhost:3000", "http://localhost:8080", "http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"]'
    )

    # Bitfinex REST API - för orderläggning och kontohantering
    BITFINEX_API_KEY: str | None = None
    BITFINEX_API_SECRET: str | None = None
    # REST (auth) bas-URL
    BITFINEX_API_URL: str = "https://api.bitfinex.com/v2"
    # Valfri separat AUTH-bas-URL (om satt i .env har den företräde
    # för auth-anrop)
    BITFINEX_AUTH_API_URL: str | None = None
    # REST (public) bas-URL – använd api-pub för publika endpoints
    BITFINEX_PUBLIC_API_URL: str = "https://api-pub.bitfinex.com/v2"

    # Bitfinex WebSocket API - separera public vs auth domäner
    BITFINEX_WS_API_KEY: str | None = None
    BITFINEX_WS_API_SECRET: str | None = None
    # WS public endast: api-pub
    BITFINEX_WS_PUBLIC_URI: str = "wss://api-pub.bitfinex.com/ws/2"
    # WS auth endast: api
    BITFINEX_WS_AUTH_URI: str = "wss://api.bitfinex.com/ws/2"
    # Bakåtkompatibel (används ej längre om de två ovan finns)
    BITFINEX_WS_URI: str = "wss://api.bitfinex.com/ws/2"

    # WS multi-socket (publika kanaler) - Optimerat för Bitfinex-begränsningar
    WS_USE_POOL: bool = True
    WS_MAX_SUBS_PER_SOCKET: int = 25  # Minskad från 200 (Bitfinex max 25 channels per connection)
    WS_PUBLIC_SOCKETS_MAX: int = 1  # Minskad från 3 (undvik 20 connections/min limit)

    # Lista över symboler att auto‑subscriba vid startup (komma‑separerad)
    WS_SUBSCRIBE_SYMBOLS: str | None = None

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
    # Global av/på för risklager (guards + constraints). Starta Off om du vill toggla i runtime
    RISK_ENABLED: bool = True
    MAX_TRADES_PER_DAY: int = 15
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
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    # SMTP (från din .env)
    SMTP_PORT: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None

    # Exchange ID
    EXCHANGE_ID: str | None = None

    # Nätverksinställningar (timeouts/retries) - Optimerat för server busy
    DATA_HTTP_TIMEOUT: float = 15.0  # Ökad för att undvika timeout
    DATA_MAX_RETRIES: int = 0  # Ingen retry för att undvika rate limit
    DATA_BACKOFF_BASE_MS: int = 1000  # Ökad från 500 (mer försiktig)
    DATA_BACKOFF_MAX_MS: int = 5000  # Ökad från 3000 (respektera rate limits)
    ORDER_HTTP_TIMEOUT: float = 15.0  # Ökad från 8.0 (mer tid för order processing)
    ORDER_MAX_RETRIES: int = 1  # Behåll 1 (undvik rate limit)
    ORDER_BACKOFF_BASE_MS: int = 2000  # Ökad från 1000 (mer försiktig)
    ORDER_BACKOFF_MAX_MS: int = 10000  # Ökad från 5000 (respektera rate limits)

    # Bitfinex API Rate Limiting - Mycket konservativ för att undvika rate limits
    BITFINEX_RATE_LIMIT_REQUESTS_PER_MINUTE: int = 3  # Mycket konservativ
    BITFINEX_RATE_LIMIT_BURST_SIZE: int = 1  # Undvik bursts
    BITFINEX_RATE_LIMIT_WINDOW_SECONDS: int = 60
    BITFINEX_RATE_LIMIT_ENABLED: bool = True
    BITFINEX_SERVER_BUSY_BACKOFF_MIN_SECONDS: float = 30.0  # Längre backoff
    BITFINEX_SERVER_BUSY_BACKOFF_MAX_SECONDS: float = 120.0  # Längre backoff

    # Concurrency caps - Mycket konservativ
    PUBLIC_REST_CONCURRENCY: int = 1
    PRIVATE_REST_CONCURRENCY: int = 1

    # Regex/pattern-baserad mapping av endpoints till limiter-typer
    RATE_LIMIT_PATTERNS: str | None = (
        None  # ex: "^auth/w/=>PRIVATE_TRADING;^auth/r/positions=>PRIVATE_ACCOUNT;^(ticker|candles|book|trades)=>PUBLIC_MARKET"
    )

    # WS ticker prioritet: anse WS-data färsk i X sekunder innan REST-fallback
    WS_TICKER_STALE_SECS: int = 10
    # Vänta kort på första WS‑tick efter auto‑subscribe innan
    # REST‑fallback (ms)
    WS_TICKER_WARMUP_MS: int = 400
    # WS candles timeframes (komma-separerad lista)
    WS_CANDLE_TIMEFRAMES: str = "1m,5m"

    # REST ticker cache TTL för att undvika överpollning
    TICKER_CACHE_TTL_SECS: int = 30  # Ökad från 10 (minska API-anrop)

    # Debug och isolerings-flags
    MARKETDATA_MODE: str = "auto"  # "auto", "rest_only", "ws_only"
    TRADING_MODE: str = "full"  # "full", "read_only", "disabled"
    UI_PUSH_ENABLED: bool = True
    DEBUG_ASYNC: bool = False  # Aktivera asyncio debug

    # Candle cache retention
    CANDLE_CACHE_RETENTION_DAYS: int = 7
    CANDLE_CACHE_MAX_ROWS_PER_PAIR: int = 10000

    # Backfill pacing
    BACKFILL_BATCH_SLEEP_MS: int = 300

    # Metrics security
    METRICS_ACCESS_TOKEN: str | None = None
    METRICS_BASIC_AUTH_USER: str | None = None
    METRICS_BASIC_AUTH_PASS: str | None = None
    # Kommaseparerad lista över tillåtna IP:n (ex: "127.0.0.1,10.0.0.5")
    METRICS_IP_ALLOWLIST: str | None = None

    # Acceptance thresholds (målvärden för stabil drift)
    ACCEPT_CANDLES_P95_MS_MAX: int = 500
    ACCEPT_CANDLES_P99_MS_MAX: int = 1200
    ACCEPT_MAX_429_PER_HOUR: int = 1
    ACCEPT_MAX_503_PER_HOUR: int = 1

    # Probability Model (feature flags)
    PROB_MODEL_ENABLED: bool = False
    PROB_MODEL_FILE: str | None = None
    PROB_MODEL_CONFIDENCE_MIN: float = 0.15
    PROB_MODEL_EV_THRESHOLD: float = 0.0005
    PROB_MODEL_TIME_HORIZON: int = 20
    # Hybrid vikt för probabilistisk vs heuristisk sannolikhet (1.0 = prob-only)
    PROB_HYBRID_WEIGHT: float = 1.0

    # Probability Validation (rolling drift/quality monitoring)
    PROB_VALIDATE_ENABLED: bool = True
    PROB_VALIDATE_INTERVAL_MINUTES: int = 60
    PROB_VALIDATE_SYMBOLS: str | None = None  # komma-separerad lista
    PROB_VALIDATE_TIMEFRAME: str = "1m"
    PROB_VALIDATE_LIMIT: int = 1200
    PROB_VALIDATE_MAX_SAMPLES: int = 500
    # Rolling validation windows and retention
    PROB_VALIDATE_WINDOWS_MINUTES: str | None = None  # ex: "60,360,1440"
    PROB_VALIDATE_HISTORY_MAX_POINTS: int = 1000
    PROB_VALIDATE_HISTORY_RETENTION_MINUTES: int = 2880

    # Probability retraining
    PROB_RETRAIN_ENABLED: bool = False
    PROB_RETRAIN_INTERVAL_HOURS: int = 24
    PROB_RETRAIN_SYMBOLS: str | None = None
    PROB_RETRAIN_TIMEFRAME: str = "1m"
    PROB_RETRAIN_LIMIT: int = 5000
    PROB_RETRAIN_OUTPUT_DIR: str = "config/models"

    # Probability sizing & auto trading
    PROB_AUTOTRADE_ENABLED: bool = False
    PROB_SIZE_MAX_RISK_PCT: float = 1.0
    PROB_SIZE_KELLY_CAP: float = 0.5
    PROB_SIZE_CONF_WEIGHT: float = 0.5

    # Position size fallback (för dev/demo när wallet-saldo saknas)
    # Om > 0 och ingen quote-balans hittas, används detta som total_quote vid beräkning
    POSITION_SIZE_FALLBACK_QUOTE: float = 0.0

    # Probability feature logging (för insyn/debugg)
    PROB_FEATURE_LOG_ENABLED: bool = False
    PROB_FEATURE_LOG_MAX_POINTS: int = 500
    PROB_FEATURE_LOG_INCLUDE_PRICE: bool = False

    # Dry-run (simulera ordrar; lägg inte riktiga ordrar)
    DRY_RUN_ENABLED: bool = False

    # Supabase MCP Server
    MCP_ENABLED: bool = False
    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    MCP_SERVER_URL: str = "https://kxibqgvpdfmklvwhmcry.supabase.co/functions/v1/mcp_server"

    # JWT Authentication
    JWT_SECRET: str | None = None

    # Säkerställ absolut sökväg till .env oavsett var processen startas
    class Config:
        env_file = _os.path.join(
            _os.path.dirname(_os.path.dirname(__file__)),
            ".env",
        )
        case_sensitive = False
        extra = "allow"  # Tillåt extra fält från .env


def get_settings() -> Settings:
    """Returnerar en singleton instans av Settings."""
    global _settings_instance
    if _settings_instance is None:
        try:
            from utils.logger import get_logger
            logger = get_logger(__name__)
            logger.info("⚙️  Creating and caching Settings instance...")
        except Exception:
            print("⚙️  Creating and caching Settings instance...")
        _settings_instance = Settings()
    return _settings_instance

# Exponera en singleton instans för enkel import
settings = get_settings()
