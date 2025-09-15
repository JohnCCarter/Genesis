"""
WebSocket Strategy Service - TradingBot Backend

Denna modul hanterar WebSocket-strategiinställningar och runtime-flaggorna.
Integrerar med runtime_mode för att hantera strategiaktivering.
"""

from utils.feature_flags import (
    get_feature_flag as _get_flag,
    set_feature_flag as _set_flag,
)
from services.runtime_mode import (
    get_ws_strategy_enabled as _rt_get_ws_strategy_enabled,
    set_ws_strategy_enabled as _rt_set_ws_strategy_enabled,
    get_ws_connect_on_start as _rt_get_ws_connect_on_start,
    set_ws_connect_on_start as _rt_set_ws_connect_on_start,
    get_validation_on_start as _rt_get_validation_on_start,
    set_validation_on_start as _rt_set_validation_on_start,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class WSStrategyService:
    """Service för WebSocket-strategihantering."""

    def __init__(self):
        self.logger = logger
        self.logger.info("🎯 WS Strategy Service initialiserad")

    def get_strategy_status(self) -> dict[str, bool]:
        """Hämtar aktuell strategistatus."""
        return {
            "ws_strategy_enabled": bool(_get_flag("ws_strategy_enabled", False)),
            "ws_connect_on_start": bool(_get_flag("ws_connect_on_start", True)),
            "validation_on_start": bool(_get_flag("validation_on_start", False)),
        }

    def update_strategy_flag(self, flag_name: str, value: bool) -> bool:
        """Uppdaterar en strategiflagga."""
        try:
            if flag_name in ("ws_strategy_enabled", "ws_connect_on_start", "validation_on_start"):
                _set_flag(flag_name, bool(value))
            else:
                self.logger.warning(f"⚠️ Okänd strategiflagga: {flag_name}")
                return False

            self.logger.info(f"✅ Strategiflagga uppdaterad: {flag_name} = {value}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Fel vid uppdatering av strategiflagga {flag_name}: {e}")
            return False


# Skapa global instans
ws_strategy_service = WSStrategyService()


# --- Re-exports for FeatureFlagsService runtime updates ---


def get_ws_strategy_enabled() -> bool:
    return _rt_get_ws_strategy_enabled()


def set_ws_strategy_enabled(value: bool) -> None:
    _rt_set_ws_strategy_enabled(bool(value))


def get_ws_connect_on_start() -> bool:
    return _rt_get_ws_connect_on_start()


def set_ws_connect_on_start(value: bool) -> None:
    _rt_set_ws_connect_on_start(bool(value))


def get_validation_on_start() -> bool:
    return _rt_get_validation_on_start()


def set_validation_on_start(value: bool) -> None:
    _rt_set_validation_on_start(bool(value))


# Ta bort wrapper-dubletter som skuggar runtime_mode (inte nödvändiga)
