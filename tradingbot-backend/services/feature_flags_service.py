"""
Feature Flags Service - Enhetlig hantering av alla toggles och feature flags.

Konsoliderar:
- Dry Run mode
- Trading Paused
- Probability Model
- Auto Trading
- WebSocket Strategy
- Validation Warmup
- WebSocket Connect on Start
- Scheduler Running
- Rate Limiting settings

Löser problem med:
- Spridda toggle-implementationer
- Inkonsistenta flagg-hantering
- Svår att debugga toggle-problem
- Olika refresh-intervall för toggle-data
"""

from __future__ import annotations

import os as _os
import services.runtime_config as rc
import asyncio
from datetime import datetime, timedelta
from typing import Any

from config.settings import settings, Settings
from utils.logger import get_logger

logger = get_logger(__name__)


class FeatureFlag:
    """En feature flag med metadata."""

    def __init__(
        self,
        name: str,
        default_value: Any,
        description: str = "",
        category: str = "general",
        requires_restart: bool = False,
    ):
        self.name = name
        self.default_value = default_value
        self.description = description
        self.category = category
        self.requires_restart = requires_restart
        self.current_value = default_value
        self.last_updated: datetime | None = None


class FeatureFlagsService:
    """
    Enhetlig service för all feature flag-hantering i systemet.

    Konsoliderar alla toggles och feature flags från:
    - Settings (miljövariabler)
    - Runtime toggles (möjliga att ändra under körning)
    - UI capabilities
    """

    def __init__(self, settings_override: Settings | None = None):
        self.settings = settings_override or settings
        self.flags: dict[str, FeatureFlag] = {}

        # Debouncing för att förhindra upprepade uppdateringar
        self._last_update_times: dict[str, datetime] = {}
        self._debounce_delay = timedelta(seconds=2)  # 2 sekunder debounce

        # Initialisera alla feature flags
        self._initialize_flags()

        logger.info("🚩 FeatureFlagsService initialiserad - enhetlig toggle-hantering")

    def _initialize_flags(self) -> None:
        """Initialisera alla feature flags från settings och runtime."""

        # Trading Mode Flags
        self.flags["dry_run_enabled"] = FeatureFlag(
            "dry_run_enabled",
            getattr(self.settings, "DRY_RUN_ENABLED", False),
            "Dry Run Mode - Simulerar trades utan att utföra dem",
            "trading",
            True,
        )

        self.flags["trading_paused"] = FeatureFlag(
            "trading_paused",
            getattr(self.settings, "TRADING_PAUSED", False),
            "Trading Paused - Pausar all handel",
            "trading",
            False,
        )

        # Probability Model Flags
        self.flags["prob_model_enabled"] = FeatureFlag(
            "prob_model_enabled",
            getattr(self.settings, "PROB_MODEL_ENABLED", False),
            "Probability Model - Aktiverar ML-baserad signal-generering",
            "probability",
            True,
        )

        self.flags["prob_validate_enabled"] = FeatureFlag(
            "prob_validate_enabled",
            getattr(self.settings, "PROB_VALIDATE_ENABLED", True),
            "Probability Validation - Validerar ML-modellens prestanda",
            "probability",
            True,
        )

        self.flags["prob_autotrade_enabled"] = FeatureFlag(
            "prob_autotrade_enabled",
            getattr(self.settings, "PROB_AUTOTRADE_ENABLED", False),
            "Probability Auto Trading - Automatisk handel baserat på ML-modell",
            "probability",
            False,
        )

        # WebSocket Flags
        self.flags["ws_strategy_enabled"] = FeatureFlag(
            "ws_strategy_enabled",
            self._get_ws_strategy_enabled(),
            "WebSocket Strategy - Aktiverar realtids-strategiutvärdering",
            "websocket",
            False,
        )

        self.flags["ws_connect_on_start"] = FeatureFlag(
            "ws_connect_on_start",
            getattr(self.settings, "WS_CONNECT_ON_START", True),
            "WebSocket Connect on Start - Anslut till WebSocket vid startup",
            "websocket",
            True,
        )

        # Test Environment Flags
        self.flags["pytest_mode"] = FeatureFlag(
            "pytest_mode",
            self._is_pytest_mode(),
            "Pytest Mode - Aktiverar test-isolering och deterministiska beteenden",
            "testing",
            False,
        )

        # Runtime Configuration Flags
        self.flags["runtime_config_enabled"] = FeatureFlag(
            "runtime_config_enabled",
            True,
            "Runtime Config - Aktiverar runtime-konfiguration via API",
            "configuration",
            False,
        )

        # Scheduler Flags
        self.flags["scheduler_enabled"] = FeatureFlag(
            "scheduler_enabled",
            getattr(self.settings, "SCHEDULER_ENABLED", True),
            "Scheduler - Aktiverar schemalagda jobb",
            "scheduling",
            False,
        )

        # Health Monitoring Flags
        self.flags["health_monitoring_enabled"] = FeatureFlag(
            "health_monitoring_enabled",
            getattr(self.settings, "HEALTH_MONITORING_ENABLED", True),
            "Health Monitoring - Aktiverar systemövervakning",
            "monitoring",
            False,
        )

        logger.info(f"🚩 {len(self.flags)} feature flags initialiserade")

        # Validation Flags
        self.flags["validation_on_start"] = FeatureFlag(
            "validation_on_start",
            self._get_validation_on_start(),
            "Validation on Start - Kör validering vid start",
            "validation",
            False,
        )

        # Scheduler Flags
        self.flags["scheduler_running"] = FeatureFlag(
            "scheduler_running",
            self._get_scheduler_running(),
            "Scheduler Running - Aktiverar schemalagda uppgifter",
            "scheduler",
            False,
        )

        # UI Flags
        self.flags["ui_push_enabled"] = FeatureFlag(
            "ui_push_enabled",
            getattr(self.settings, "UI_PUSH_ENABLED", True),
            "UI Push Enabled - Aktiverar push-notifikationer till UI",
            "ui",
            True,
        )

        # Debug Flags
        self.flags["debug_async"] = FeatureFlag(
            "debug_async",
            getattr(self.settings, "DEBUG_ASYNC", False),
            "Debug Async - Aktiverar asyncio debug-läge",
            "debug",
            True,
        )

        # Market Data Flags
        self.flags["marketdata_mode"] = FeatureFlag(
            "marketdata_mode",
            getattr(self.settings, "MARKETDATA_MODE", "auto"),
            "Market Data Mode - auto, rest_only, ws_only",
            "marketdata",
            True,
        )

        # Rate Limiting Flags
        self.flags["rate_limit_enabled"] = FeatureFlag(
            "rate_limit_enabled",
            bool(getattr(self.settings, "ORDER_RATE_LIMIT_MAX", 0)),
            "Rate Limiting Enabled - Aktiverar API rate limiting",
            "rate_limit",
            True,
        )

    def _get_ws_strategy_enabled(self) -> bool:
        """Hämta WebSocket strategy enabled från runtime."""
        try:
            from services.ws_strategy import get_ws_strategy_enabled

            return bool(get_ws_strategy_enabled())
        except Exception:
            return False

    def _get_ws_connect_on_start(self) -> bool:
        """Hämta WebSocket connect on start från runtime."""
        try:
            from services.ws_strategy import get_ws_connect_on_start

            return bool(get_ws_connect_on_start())
        except Exception:
            return False

    def _get_validation_on_start(self) -> bool:
        """Hämta validation on start från runtime."""
        try:
            from services.ws_strategy import get_validation_on_start

            return bool(get_validation_on_start())
        except Exception:
            return False

    def _get_scheduler_running(self) -> bool:
        """Hämta scheduler running från runtime."""
        try:
            from services.scheduler import scheduler

            return bool(scheduler.is_running())
        except Exception:
            return False

    def _is_pytest_mode(self) -> bool:
        """Kontrollera om vi kör i pytest-läge."""
        try:
            return bool(_os.environ.get("PYTEST_CURRENT_TEST"))
        except Exception:
            return False

    def get_flag(self, name: str) -> Any:
        """Hämta värdet för en feature flag."""
        if name in self.flags:
            return self.flags[name].current_value
        logger.warning(f"⚠️ Okänd feature flag: {name}")
        return None

    def set_flag(self, name: str, value: Any) -> bool:
        """Sätt värdet för en feature flag med debouncing."""
        if name not in self.flags:
            logger.error(f"❌ Okänd feature flag: {name}")
            return False

        try:
            flag = self.flags[name]
            old_value = flag.current_value

            # Kontrollera om värdet faktiskt har ändrats
            if old_value == value:
                logger.debug(f"📋 Feature flag {name} har redan värdet {value} - hoppar över uppdatering")
                return True

            # Debouncing: kontrollera om vi har uppdaterat för nyligen
            now = datetime.now()
            last_update = self._last_update_times.get(name)

            if last_update and (now - last_update) < self._debounce_delay:
                logger.debug(f"⏱️ Debouncing feature flag {name} - för nyligen uppdaterad")
                return True

            # Uppdatera flag
            flag.current_value = value
            flag.last_updated = now
            self._last_update_times[name] = now

            # Uppdatera runtime-värden om möjligt
            self._update_runtime_flag(name, value)

            logger.info(f"🚩 Feature flag uppdaterad: {name} = {value} (tidigare: {old_value})")
            return True

        except Exception as e:
            logger.error(f"❌ Fel vid uppdatering av feature flag {name}: {e}")
            return False

    def _update_runtime_flag(self, name: str, value: Any) -> None:
        """Uppdatera runtime-värden för feature flags."""
        try:
            if name == "ws_strategy_enabled":
                from services.ws_strategy import set_ws_strategy_enabled

                set_ws_strategy_enabled(bool(value))

            elif name == "ws_connect_on_start":
                from services.ws_strategy import set_ws_connect_on_start

                set_ws_connect_on_start(bool(value))

            elif name == "validation_on_start":
                from services.ws_strategy import set_validation_on_start

                set_validation_on_start(bool(value))

            elif name == "prob_autotrade_enabled":
                rc.set_bool("PROB_AUTOTRADE_ENABLED", bool(value))

            elif name == "trading_paused":
                rc.set_bool("TRADING_PAUSED", bool(value))

            elif name == "dry_run_enabled":
                rc.set_bool("DRY_RUN_ENABLED", bool(value))

        except Exception as e:
            logger.warning(f"⚠️ Kunde inte uppdatera runtime flag {name}: {e}")

    def get_all_flags(self) -> dict[str, Any]:
        """Hämta alla feature flags med metadata."""
        result = {}
        for name, flag in self.flags.items():
            result[name] = {
                "value": flag.current_value,
                "default_value": flag.default_value,
                "description": flag.description,
                "category": flag.category,
                "requires_restart": flag.requires_restart,
                "last_updated": (flag.last_updated.isoformat() if flag.last_updated else None),
            }
        return result

    def get_flags_by_category(self, category: str) -> dict[str, Any]:
        """Hämta feature flags grupperade efter kategori."""
        result = {}
        for name, flag in self.flags.items():
            if flag.category == category:
                result[name] = {
                    "value": flag.current_value,
                    "default_value": flag.default_value,
                    "description": flag.description,
                    "requires_restart": flag.requires_restart,
                    "last_updated": (flag.last_updated.isoformat() if flag.last_updated else None),
                }
        return result

    def get_categories(self) -> list[str]:
        """Hämta alla tillgängliga kategorier."""
        categories = set()
        for flag in self.flags.values():
            categories.add(flag.category)
        return sorted(list(categories))

    def reset_flag(self, name: str) -> bool:
        """Återställ en feature flag till default-värde."""
        if name not in self.flags:
            logger.error(f"❌ Okänd feature flag: {name}")
            return False

        try:
            flag = self.flags[name]
            old_value = flag.current_value
            flag.current_value = flag.default_value
            flag.last_updated = datetime.now()

            # Uppdatera runtime-värden
            self._update_runtime_flag(name, flag.default_value)

            logger.info(f"🔄 Feature flag återställd: {name} = {flag.default_value} (tidigare: {old_value})")
            return True

        except Exception as e:
            logger.error(f"❌ Fel vid återställning av feature flag {name}: {e}")
            return False

    def reset_all_flags(self) -> bool:
        """Återställ alla feature flags till default-värden."""
        try:
            for name in self.flags:
                self.reset_flag(name)
            logger.info("🔄 Alla feature flags återställda")
            return True
        except Exception as e:
            logger.error(f"❌ Fel vid återställning av alla feature flags: {e}")
            return False

    def get_ui_capabilities(self) -> dict[str, Any]:
        """Hämta UI capabilities baserat på feature flags."""
        return {
            "ws": {
                "connect_on_start": self.get_flag("ws_connect_on_start"),
                "strategy_enabled": self.get_flag("ws_strategy_enabled"),
            },
            "prob": {
                "validate_enabled": self.get_flag("prob_validate_enabled"),
                "model_enabled": self.get_flag("prob_model_enabled"),
                "autotrade_enabled": self.get_flag("prob_autotrade_enabled"),
            },
            "dry_run": self.get_flag("dry_run_enabled"),
            "trading_paused": self.get_flag("trading_paused"),
            "scheduler_running": self.get_flag("scheduler_running"),
            "rate_limit": {
                "enabled": self.get_flag("rate_limit_enabled"),
                "order_max": getattr(self.settings, "ORDER_RATE_LIMIT_MAX", 0),
                "order_window": getattr(self.settings, "ORDER_RATE_LIMIT_WINDOW", 0),
            },
        }

    def refresh_runtime_flags(self) -> None:
        """Uppdatera runtime-flags från deras källor."""
        try:
            # Uppdatera WebSocket flags
            self.flags["ws_strategy_enabled"].current_value = self._get_ws_strategy_enabled()
            self.flags["ws_connect_on_start"].current_value = self._get_ws_connect_on_start()
            self.flags["validation_on_start"].current_value = self._get_validation_on_start()

            # Uppdatera scheduler flag
            self.flags["scheduler_running"].current_value = self._get_scheduler_running()

            logger.debug("🔄 Runtime flags uppdaterade")
        except Exception as e:
            logger.error(f"❌ Fel vid uppdatering av runtime flags: {e}")

    def get_flag_status(self) -> dict[str, Any]:
        """Hämta komplett status för alla feature flags."""
        try:
            # Uppdatera runtime flags först
            self.refresh_runtime_flags()

            return {
                "timestamp": datetime.now().isoformat(),
                "total_flags": len(self.flags),
                "categories": self.get_categories(),
                "flags": self.get_all_flags(),
                "ui_capabilities": self.get_ui_capabilities(),
            }
        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av flag status: {e}")
            raise


# Global instans för enhetlig åtkomst
feature_flags_service = FeatureFlagsService()
