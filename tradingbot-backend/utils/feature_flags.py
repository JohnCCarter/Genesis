# AI Change: Add feature flags utility to replace direct env calls (Agent: Codex, Date: 2025-01-27)
"""
Feature Flags Utility - Ersätter direkta os.environ anrop.

Använd denna utility istället för direkta os.environ.get() anrop för bättre
centralisering och konsistens.
"""

from __future__ import annotations

from typing import Any, Optional

from services.feature_flags_service import feature_flags_service
from utils.logger import get_logger

logger = get_logger(__name__)


def is_pytest_mode() -> bool:
    """Kontrollera om vi kör i pytest-läge."""
    try:
        return bool(feature_flags_service.get_flag("pytest_mode"))
    except Exception:
        # Fallback till direkta env-anrop om feature flags service inte är tillgänglig
        import os

        return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def is_dry_run_enabled() -> bool:
    """Kontrollera om dry run är aktiverat."""
    try:
        return bool(feature_flags_service.get_flag("dry_run_enabled"))
    except Exception:
        return False


def is_trading_paused() -> bool:
    """Kontrollera om trading är pausat."""
    try:
        return bool(feature_flags_service.get_flag("trading_paused"))
    except Exception:
        return False


def is_prob_model_enabled() -> bool:
    """Kontrollera om probability model är aktiverat."""
    try:
        return bool(feature_flags_service.get_flag("prob_model_enabled"))
    except Exception:
        return False


def is_ws_strategy_enabled() -> bool:
    """Kontrollera om WebSocket strategy är aktiverat."""
    try:
        return bool(feature_flags_service.get_flag("ws_strategy_enabled"))
    except Exception:
        return False


def is_ws_connect_on_start() -> bool:
    """Kontrollera om WebSocket ska anslutas vid start."""
    try:
        return bool(feature_flags_service.get_flag("ws_connect_on_start"))
    except Exception:
        return True


def is_scheduler_enabled() -> bool:
    """Kontrollera om scheduler är aktiverat."""
    try:
        return bool(feature_flags_service.get_flag("scheduler_enabled"))
    except Exception:
        return True


def is_health_monitoring_enabled() -> bool:
    """Kontrollera om health monitoring är aktiverat."""
    try:
        return bool(feature_flags_service.get_flag("health_monitoring_enabled"))
    except Exception:
        return True


def is_runtime_config_enabled() -> bool:
    """Kontrollera om runtime config är aktiverat."""
    try:
        return bool(feature_flags_service.get_flag("runtime_config_enabled"))
    except Exception:
        return True


def get_feature_flag(name: str, default_value: Any = None) -> Any:
    """Hämta en feature flag med fallback-värde."""
    try:
        value = feature_flags_service.get_flag(name)
        return value if value is not None else default_value
    except Exception:
        logger.debug(f"Kunde inte hämta feature flag {name}, använder default: {default_value}")
        return default_value


def set_feature_flag(name: str, value: Any) -> bool:
    """Sätt en feature flag."""
    try:
        return feature_flags_service.set_flag(name, value)
    except Exception as e:
        logger.error(f"Kunde inte sätta feature flag {name}: {e}")
        return False


# Bakåtkompatibilitet för runtime_config
def get_env_with_fallback(key: str, default_value: Any = None) -> Any:
    """Hämta miljövariabel med fallback till feature flags."""
    try:
        # Försök först med feature flags
        flag_value = get_feature_flag(key, None)
        if flag_value is not None:
            return flag_value

        # Fallback till direkta env-anrop
        import os

        return os.environ.get(key, default_value)
    except Exception:
        return default_value


def set_env_with_feature_flag(key: str, value: Any) -> bool:
    """Sätt miljövariabel med feature flag-synkronisering."""
    try:
        # Sätt i feature flags först
        success = set_feature_flag(key, value)

        # Synkronisera med runtime_config om det är aktiverat
        if is_runtime_config_enabled():
            import services.runtime_config as rc

            if isinstance(value, bool):
                rc.set_bool(key, value)
            elif isinstance(value, int):
                rc.set_int(key, value)
            elif isinstance(value, float):
                rc.set_float(key, value)
            else:
                rc.set_str(key, str(value))

        return success
    except Exception as e:
        logger.error(f"Kunde inte sätta env/feature flag {key}: {e}")
        return False
