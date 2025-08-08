"""
Configuration Settings - TradingBot Backend

Denna modul hanterar alla konfigurationsinställningar för applikationen.
Inkluderar miljövariabler, API-nycklar och applikationskonfiguration.
"""

import os as _os
try:
    from pydantic_settings import BaseSettings as _BaseSettings, SettingsConfigDict
    _V2 = True
except Exception:
    from pydantic import BaseSettings as _BaseSettings  # v1 fallback
    _V2 = False
from typing import List, Optional
import os

class Settings(_BaseSettings):
    """Konfigurationsklass för applikationsinställningar."""
    
    # Applikationskonfiguration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    AUTH_REQUIRED: bool = True  # Kräv JWT för REST/WS. Sätt till false i dev för att tillfälligt stänga av
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # Bitfinex REST API - för orderläggning och kontohantering
    BITFINEX_API_KEY: Optional[str] = None
    BITFINEX_API_SECRET: Optional[str] = None
    BITFINEX_API_URL: str = "https://api.bitfinex.com/v2"
    
    # Bitfinex WebSocket API - för realtidsdata och autentiserade feeds
    BITFINEX_WS_API_KEY: Optional[str] = None
    BITFINEX_WS_API_SECRET: Optional[str] = None
    BITFINEX_WS_URI: str = "wss://api.bitfinex.com/ws/2"
    
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
    TRADE_COOLDOWN_SECONDS: int = 60
    TRADING_PAUSED: bool = False
    
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
    
    # Säkerställ absolut sökväg till .env oavsett var processen startas
    _BASE_DIR = _os.path.dirname(_os.path.dirname(__file__))
    _ENV_FILE = _os.path.join(_BASE_DIR, ".env")

    if _V2:
        # Pydantic v2 settings
        model_config = SettingsConfigDict(env_file=_ENV_FILE, case_sensitive=False, extra="allow")
    else:
        # Pydantic v1 settings
        class Config:
            env_file = Settings._ENV_FILE  # type: ignore[attr-defined]
            case_sensitive = False
            extra = "allow"  # Tillåt extra fält från .env