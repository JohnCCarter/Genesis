# AI Change: Add startup configuration to enable components (Agent: Codex, Date: 2025-01-27)
"""
Startup Configuration - Aktiverar komponenter vid startup.

Denna fil hanterar automatisk aktivering av komponenter baserat på miljövariabler
och feature flags.
"""

from __future__ import annotations

import os
from typing import Any

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def enable_components_on_startup() -> None:
    """Aktivera komponenter vid startup baserat på miljövariabler."""

    _settings = settings

    # 1. Aktivera Dry Run om miljövariabel är satt
    if os.environ.get("ENABLE_DRY_RUN", "").lower() in ("true", "1", "yes"):
        try:
            import services.runtime_config as rc

            rc.set_bool("DRY_RUN_ENABLED", True)
            _settings.DRY_RUN_ENABLED = True
            logger.info("✅ Dry Run aktiverat via miljövariabel")
        except Exception as e:
            logger.warning(f"Kunde inte aktivera Dry Run: {e}")

    # 2. Aktivera Probability Model om miljövariabel är satt
    if os.environ.get("ENABLE_PROB_MODEL", "").lower() in ("true", "1", "yes"):
        try:
            import services.runtime_config as rc

            rc.set_bool("PROB_MODEL_ENABLED", True)
            _settings.PROB_MODEL_ENABLED = True
            logger.info("✅ Probability Model aktiverat via miljövariabel")
        except Exception as e:
            logger.warning(f"Kunde inte aktivera Probability Model: {e}")

    # 3. Aktivera Scheduler om miljövariabel är satt
    if os.environ.get("ENABLE_SCHEDULER", "").lower() in ("true", "1", "yes"):
        try:
            import services.runtime_config as rc

            rc.set_bool("SCHEDULER_ENABLED", True)
            _settings.SCHEDULER_ENABLED = True
            logger.info("✅ Scheduler aktiverat via miljövariabel")
        except Exception as e:
            logger.warning(f"Kunde inte aktivera Scheduler: {e}")

    # 4. Aktivera alla komponenter om DEV_MODE är satt
    if os.environ.get("DEV_MODE", "").lower() in ("true", "1", "yes"):
        try:
            import services.runtime_config as rc

            # Aktivera alla komponenter i dev-läge
            rc.set_bool("DRY_RUN_ENABLED", True)
            rc.set_bool("PROB_MODEL_ENABLED", True)
            rc.set_bool("SCHEDULER_ENABLED", True)
            rc.set_bool("PROB_AUTOTRADE_ENABLED", True)

            _settings.DRY_RUN_ENABLED = True
            _settings.PROB_MODEL_ENABLED = True
            _settings.SCHEDULER_ENABLED = True
            _settings.PROB_AUTOTRADE_ENABLED = True

            logger.info("🚀 DEV_MODE: Alla komponenter aktiverade")
        except Exception as e:
            logger.warning(f"Kunde inte aktivera DEV_MODE komponenter: {e}")


def get_component_status() -> dict[str, Any]:
    """Hämta status för alla komponenter."""

    _settings = settings

    return {
        "dry_run_enabled": getattr(_settings, "DRY_RUN_ENABLED", False),
        "prob_model_enabled": getattr(_settings, "PROB_MODEL_ENABLED", False),
        "prob_autotrade_enabled": getattr(_settings, "PROB_AUTOTRADE_ENABLED", False),
        "scheduler_enabled": getattr(_settings, "SCHEDULER_ENABLED", True),
        "ws_connect_on_start": getattr(_settings, "WS_CONNECT_ON_START", True),
        "dev_mode": os.environ.get("DEV_MODE", "").lower() in ("true", "1", "yes"),
        "environment_variables": {
            "ENABLE_DRY_RUN": os.environ.get("ENABLE_DRY_RUN", "not set"),
            "ENABLE_PROB_MODEL": os.environ.get("ENABLE_PROB_MODEL", "not set"),
            "ENABLE_SCHEDULER": os.environ.get("ENABLE_SCHEDULER", "not set"),
            "DEV_MODE": os.environ.get("DEV_MODE", "not set"),
        },
    }


def log_startup_status() -> None:
    """Logga status för alla komponenter vid startup."""

    status = get_component_status()

    logger.info("🔧 Komponent-status vid startup:")
    logger.info(f"  📝 Dry Run: {'✅ Aktiverat' if status['dry_run_enabled'] else '❌ Inaktiverat'}")
    logger.info(f"  🧠 Probability Model: {'✅ Aktiverat' if status['prob_model_enabled'] else '❌ Inaktiverat'}")
    logger.info(f"  🤖 Auto Trading: {'✅ Aktiverat' if status['prob_autotrade_enabled'] else '❌ Inaktiverat'}")
    logger.info(f"  🗓️ Scheduler: {'✅ Aktiverat' if status['scheduler_enabled'] else '❌ Inaktiverat'}")
    logger.info(f"  🌐 WebSocket Connect: {'✅ Aktiverat' if status['ws_connect_on_start'] else '❌ Inaktiverat'}")
    logger.info(f"  🚀 Dev Mode: {'✅ Aktiverat' if status['dev_mode'] else '❌ Inaktiverat'}")

    # Logga miljövariabler
    env_vars = status["environment_variables"]
    logger.info("🔧 Miljövariabler:")
    for key, value in env_vars.items():
        logger.info(f"  {key}: {value}")
