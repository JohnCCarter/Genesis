"""
WebSocket Strategy Service - TradingBot Backend

Denna modul hanterar WebSocket-strategiinställningar och runtime-flaggorna.
Integrerar med runtime_mode för att hantera strategiaktivering.
"""

from services.runtime_mode import (
    get_ws_strategy_enabled,
    set_ws_strategy_enabled,
    get_ws_connect_on_start,
    set_ws_connect_on_start,
    get_validation_on_start,
    set_validation_on_start,
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
        from services.runtime_mode import (
            get_ws_strategy_enabled as _get_ws_strategy_enabled,
            get_ws_connect_on_start as _get_ws_connect_on_start,
            get_validation_on_start as _get_validation_on_start,
        )

        return {
            "ws_strategy_enabled": _get_ws_strategy_enabled(),
            "ws_connect_on_start": _get_ws_connect_on_start(),
            "validation_on_start": _get_validation_on_start(),
        }

    def update_strategy_flag(self, flag_name: str, value: bool) -> bool:
        """Uppdaterar en strategiflagga."""
        try:
            if flag_name == "ws_strategy_enabled":
                set_ws_strategy_enabled(value)
            elif flag_name == "ws_connect_on_start":
                set_ws_connect_on_start(value)
            elif flag_name == "validation_on_start":
                set_validation_on_start(value)
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


# Exportera funktioner för kompatibilitet med feature_flags_service
def get_ws_strategy_enabled() -> bool:
    """Hämtar om WebSocket-strategi är aktiverad."""
    from services.runtime_mode import get_ws_strategy_enabled as _get_ws_strategy_enabled

    return _get_ws_strategy_enabled()


def set_ws_strategy_enabled(value: bool) -> None:
    """Sätter WebSocket-strategiaktivering."""
    from services.runtime_mode import set_ws_strategy_enabled as _set_ws_strategy_enabled

    _set_ws_strategy_enabled(value)


def get_ws_connect_on_start() -> bool:
    """Hämtar om WebSocket ska ansluta vid start."""
    from services.runtime_mode import get_ws_connect_on_start as _get_ws_connect_on_start

    return _get_ws_connect_on_start()


def set_ws_connect_on_start(value: bool) -> None:
    """Sätter WebSocket-anslutning vid start."""
    from services.runtime_mode import set_ws_connect_on_start as _set_ws_connect_on_start

    _set_ws_connect_on_start(value)


def get_validation_on_start() -> bool:
    """Hämtar om validering ska köras vid start."""
    from services.runtime_mode import get_validation_on_start as _get_validation_on_start

    return _get_validation_on_start()


def set_validation_on_start(value: bool) -> None:
    """Sätter validering vid start."""
    from services.runtime_mode import set_validation_on_start as _set_validation_on_start

    _set_validation_on_start(value)
