"""
Unified Config Manager v2 - Enhetlig konfigurationshantering

Hanterar konfiguration från olika källor med kontextuell prioritet och central store.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path
import logging

from config.key_registry import KEY_REGISTRY, ConfigKey
from config.priority_profiles import PriorityProfile
from services.config_store import ConfigStore, ConfigValue
from services.config_cache import ConfigCache

logger = logging.getLogger(__name__)


@dataclass
class ConfigContext:
    """Kontext för konfigurationshämtning."""

    priority_profile: PriorityProfile = PriorityProfile.GLOBAL
    user: Optional[str] = None
    source_override: Optional[str] = None


class UnifiedConfigManager:
    """
    Enhetlig konfigurationshanterare med kontextuell prioritet.
    """

    def __init__(self, config_store: ConfigStore = None, config_cache: ConfigCache = None):
        """Initiera UnifiedConfigManager."""
        self.config_store = config_store or ConfigStore()
        self.cache = config_cache or ConfigCache(self.config_store)

        # Starta Redis subscription för cache invalidation
        self._setup_redis_subscription()

    def _setup_redis_subscription(self):
        """Sätt upp Redis subscription för cache invalidation."""

        def on_config_change(data):
            """Hantera konfigurationsändringar från Redis."""
            key = data.get("key")
            generation = data.get("generation")
            action = data.get("action")

            if action == "SET":
                # Invalidera cache för denna nyckel
                self.cache.invalidate(key)
            elif action == "DELETE":
                # Invalidera cache för denna nyckel
                self.cache.invalidate(key)
            elif action == "GENERATION_UPDATE":
                # Invalidera alla poster med lägre generation
                self.cache.invalidate_by_generation(generation)

        # Starta subscription i bakgrunden
        import threading

        def subscribe_worker():
            self.config_store.subscribe_to_changes(on_config_change)

        thread = threading.Thread(target=subscribe_worker, daemon=True)
        thread.start()

    def get(self, key: str, context: ConfigContext | None = None) -> Any:
        """
        Hämta konfigurationsvärde med kontextuell prioritet.

        Args:
            key: Konfigurationsnyckel
            context: Konfigurationskontext (optional)

        Returns:
            Konfigurationsvärde
        """
        if key not in KEY_REGISTRY:
            raise ValueError(f"Unknown configuration key: {key}")

        config_key = KEY_REGISTRY[key]
        context = context or ConfigContext()

        # Bestäm prioritetsordning baserat på kontext
        sources = self._get_priority_sources(config_key, context)

        # Prova källor i prioritetsordning
        for source in sources:
            value = self._get_from_source(key, source)
            if value is not None:
                return value

        # Fallback till default
        return config_key.default

    def _get_priority_sources(self, config_key: ConfigKey, context: ConfigContext) -> list[str]:
        """Bestäm prioritetsordning för källor baserat på kontext."""
        base_sources = config_key.allowed_sources.copy()

        # Anpassa prioritet baserat på kontext
        if context.priority_profile == PriorityProfile.DOMAIN_POLICY:
            # För domänspecifika regler, prioritera files högre
            if "files" in base_sources:
                base_sources.remove("files")
                base_sources.insert(0, "files")
        else:
            # För global prioritet, följ standardordning
            pass

        # Lägg till source override om specificerat
        if context.source_override and context.source_override in base_sources:
            base_sources.remove(context.source_override)
            base_sources.insert(0, context.source_override)

        return base_sources

    def _get_from_source(self, key: str, source: str) -> Any:
        """Hämta värde från specifik källa."""
        if source == "cache":
            return self.cache.get(key)
        elif source == "runtime":
            # Runtime overrides (från memory)
            return self._get_runtime_override(key)
        elif source == "feature_flags":
            # Feature flags
            return self._get_feature_flag(key)
        elif source == "settings":
            # Settings från .env
            return self._get_env_setting(key)
        elif source == "files":
            # JSON-filer (t.ex. trading_rules.json)
            return self._get_file_setting(key)
        else:
            return None

    def _get_runtime_override(self, _key: str) -> Any:
        """Hämta runtime override."""
        # Placeholder för runtime overrides
        # I en riktig implementation skulle vi ha en runtime store
        return None

    def _get_feature_flag(self, key: str) -> Any:
        """Hämta från feature flags."""
        # Placeholder för feature flags
        # I en riktig implementation skulle vi integrera med feature flag system
        return None

    def _get_env_setting(self, key: str) -> Any:
        """Hämta från environment variables."""
        if key not in KEY_REGISTRY:
            return None

        config_key = KEY_REGISTRY[key]
        env_value = os.environ.get(key)
        if env_value is not None:
            return self._convert_value(env_value, config_key.type)
        return None

    def _get_file_setting(self, key: str) -> Any:
        """Hämta från JSON-filer."""
        if key.startswith("trading_rules."):
            # För trading rules, kontrollera först .env (högsta prioritet)
            env_value = self._get_env_trading_rules_setting(key)
            if env_value is not None:
                return env_value

            # Om inte i .env, hämta från trading_rules.json
            return self._get_trading_rules_setting(key)
        return None

    def _get_trading_rules_setting(self, key: str) -> Any:
        """Hämta från trading_rules.json."""
        if not key.startswith("trading_rules."):
            return None

        try:
            rules_file = Path("config/trading_rules.json")
            if rules_file.exists():
                with open(rules_file) as f:
                    data = json.load(f)

                # Ta bort trading_rules prefix och mappa till JSON-nycklar
                env_key = key.replace("trading_rules.", "")
                key_mapping = {
                    "MAX_TRADES_PER_DAY": "max_trades_per_day",
                    "MAX_TRADES_PER_SYMBOL_PER_DAY": "max_trades_per_symbol_per_day",
                    "TRADE_COOLDOWN_SECONDS": "trade_cooldown_seconds",
                }

                json_key = key_mapping.get(env_key)
                if json_key and json_key in data:
                    return data[json_key]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

        return None

    def _get_env_trading_rules_setting(self, key: str) -> Any:
        """Hämta trading rules från .env-variabler (högsta prioritet)."""
        # Kontrollera om det är en trading rules nyckel
        if not key.startswith("trading_rules."):
            return None

        # Ta bort trading_rules prefix för att få env variabel namn
        env_key = key.replace("trading_rules.", "")

        try:
            value = os.environ.get(env_key)
            if value is not None:
                # Konvertera till rätt typ baserat på KEY_REGISTRY
                from config.key_registry import KEY_REGISTRY

                if env_key in KEY_REGISTRY:
                    expected_type = KEY_REGISTRY[env_key].type
                    if expected_type == int:
                        return int(value)
                    elif expected_type == bool:
                        return value.lower() in ("true", "1", "yes", "on")
                    elif expected_type == float:
                        return float(value)
                    else:
                        return value
        except (ValueError, TypeError):
            pass

        return None

    def set(self, key: str, value: Any, source: str = "runtime", user: str | None = None) -> bool:
        """
        Sätt konfigurationsvärde.

        Args:
            key: Konfigurationsnyckel
            value: Värde att sätta
            source: Källa för värdet
            user: Användare som gjorde ändringen

        Returns:
            True om satt framgångsrikt
        """
        if key not in KEY_REGISTRY:
            raise ValueError(f"Unknown configuration key: {key}")

        config_key = KEY_REGISTRY[key]

        # Validera att källan är tillåten
        if source not in config_key.allowed_sources:
            raise ValueError(f"Source '{source}' not allowed for key '{key}'")

        # Validera värde
        if not self._validate_value(value, config_key):
            raise ValueError(f"Invalid value for key '{key}': {value}")

        # Sätt i central store
        config_value = ConfigValue(
            key=key,
            value=value,
            source=source,
            generation=self.config_store.get_next_generation(),
            created_at=time.time(),
            updated_at=time.time(),
            user=user,
        )

        self.config_store.set(key, value, source, user)

        # Invalidera cache
        self.cache.invalidate(key)

        logger.info(f"Set config key {key} = {value} from source {source}")
        return True

    def _validate_value(self, value: Any, config_key: ConfigKey) -> bool:
        """Validera konfigurationsvärde."""
        # Typkontroll
        if not isinstance(value, config_key.type):
            return False

        # Range-kontroll
        if config_key.min_value is not None and value < config_key.min_value:
            return False
        if config_key.max_value is not None and value > config_key.max_value:
            return False

        return True

    def _convert_value(self, value: str, target_type: type) -> Any:
        """Konvertera strängvärde till target typ."""
        if target_type == bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif target_type == int:
            return int(value)
        elif target_type == float:
            return float(value)
        else:
            return value

    def get_effective_config(self, context: ConfigContext | None = None) -> Dict[str, Any]:
        """Hämta all effektiv konfiguration."""
        context = context or ConfigContext()
        effective_config = {}

        for key in KEY_REGISTRY:
            try:
                value = self.get(key, context)
                effective_config[key] = value
            except Exception as e:
                logger.warning(f"Failed to get config for key {key}: {e}")
                effective_config[key] = KEY_REGISTRY[key].default

        return effective_config

    def get_config_stats(self) -> Dict[str, Any]:
        """Hämta statistik för konfigurationssystemet."""
        return {
            "total_keys": len(KEY_REGISTRY),
            "cache_stats": self.cache.get_cache_stats(),
            "store_stats": self.config_store.get_store_stats(),
            "timestamp": time.time(),
        }


# Global unified config manager instans
_unified_config_manager: Optional[UnifiedConfigManager] = None


def get_unified_config_manager(
    config_store: ConfigStore | None = None, config_cache: ConfigCache | None = None
) -> UnifiedConfigManager:
    """Hämta global UnifiedConfigManager-instans."""
    global _unified_config_manager
    if _unified_config_manager is None:
        _unified_config_manager = UnifiedConfigManager(config_store, config_cache)

    return _unified_config_manager
