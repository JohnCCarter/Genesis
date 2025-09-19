"""
Central Key Registry för Konfigurationshantering

Definierar alla konfigurationsnycklar med deras schema, metadata och prioritetsprofiler.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Type, Dict, Union
from .priority_profiles import PriorityProfile


@dataclass
class ConfigKey:
    """
    Definition av en konfigurationsnyckel med alla metadata.
    """

    name: str
    type: Type
    default: Any
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    priority_profile: PriorityProfile = PriorityProfile.GLOBAL
    allowed_sources: List[str] = field(default_factory=lambda: ["runtime", "feature_flags", "settings", "files"])
    sensitive: bool = False
    restart_required: bool = False
    namespaces: List[str] = field(default_factory=list)
    description: str = ""
    validation_rules: List[str] = field(default_factory=list)

    def validate_value(self, value: Any) -> bool:
        """
        Validera ett värde mot denna nyckels definition.

        Args:
            value: Värde att validera

        Returns:
            True om värdet är giltigt
        """
        # Typvalidering
        if not isinstance(value, self.type):
            return False

        # Min/max validering för numeriska typer
        if self.min_value is not None and value < self.min_value:
            return False

        if self.max_value is not None and value > self.max_value:
            return False

        return True

    def get_masked_value(self, value: Any) -> Any:
        """
        Returnera maskerat värde om nyckeln är känslig.

        Args:
            value: Värde att maskera

        Returns:
            Maskerat värde om känslig, annars originalvärdet
        """
        if self.sensitive:
            if isinstance(value, str):
                return "***" if len(value) > 6 else "***"
            else:
                return "***"
        return value


class KeyRegistry:
    """
    Central registry för alla konfigurationsnycklar.
    """

    def __init__(self):
        self._keys: Dict[str, ConfigKey] = {}
        self._initialize_default_keys()

    def _initialize_default_keys(self):
        """Initialisera alla standardkonfigurationsnycklar."""

        # Trading Mode Keys
        self.register_key(
            ConfigKey(
                name="DRY_RUN_ENABLED",
                type=bool,
                default=True,
                priority_profile=PriorityProfile.GLOBAL,
                allowed_sources=["runtime", "feature_flags", "settings"],
                description="Dry Run Mode - Simulerar trades utan att utföra dem",
                restart_required=False,
            )
        )

        self.register_key(
            ConfigKey(
                name="TRADING_PAUSED",
                type=bool,
                default=False,
                priority_profile=PriorityProfile.GLOBAL,
                allowed_sources=["runtime", "feature_flags", "settings"],
                description="Trading Paused - Pausar all handel",
                restart_required=False,
            )
        )

        # Probability Model Keys
        self.register_key(
            ConfigKey(
                name="PROB_MODEL_ENABLED",
                type=bool,
                default=False,
                priority_profile=PriorityProfile.GLOBAL,
                allowed_sources=["runtime", "feature_flags", "settings"],
                description="Probability Model - Aktiverar ML-baserad signal-generering",
                restart_required=True,
            )
        )

        self.register_key(
            ConfigKey(
                name="PROB_AUTOTRADE_ENABLED",
                type=bool,
                default=False,
                priority_profile=PriorityProfile.GLOBAL,
                allowed_sources=["runtime", "feature_flags", "settings"],
                description="Probability Auto Trading - Automatisk handel baserat på ML-modell",
                restart_required=True,
            )
        )

        # WebSocket Keys
        self.register_key(
            ConfigKey(
                name="WS_CONNECT_ON_START",
                type=bool,
                default=True,
                priority_profile=PriorityProfile.GLOBAL,
                allowed_sources=["runtime", "feature_flags", "settings"],
                description="WebSocket Connect on Start - Anslut WebSocket vid startup",
                restart_required=True,
            )
        )

        self.register_key(
            ConfigKey(
                name="WS_SUBSCRIBE_SYMBOLS",
                type=str,
                default="tBTCUSD,tETHUSD,tADAUSD,tDOTUSD",
                priority_profile=PriorityProfile.GLOBAL,
                allowed_sources=["runtime", "settings"],
                description="WebSocket Subscribe Symbols - Symboler att prenumerera på",
                restart_required=True,
            )
        )

        # Risk Management Keys
        self.register_key(
            ConfigKey(
                name="RISK_PERCENTAGE",
                type=float,
                default=2.0,
                min_value=0.1,
                max_value=10.0,
                priority_profile=PriorityProfile.DOMAIN_POLICY,
                allowed_sources=["runtime", "files", "feature_flags", "settings"],
                namespaces=["risk"],
                description="Risk Percentage - Max risk per trade i procent",
                restart_required=False,
            )
        )

        self.register_key(
            ConfigKey(
                name="MAX_POSITION_SIZE",
                type=float,
                default=0.01,
                min_value=0.001,
                max_value=1.0,
                priority_profile=PriorityProfile.DOMAIN_POLICY,
                allowed_sources=["runtime", "files", "feature_flags", "settings"],
                namespaces=["risk"],
                description="Max Position Size - Maximal positionstorlek",
                restart_required=False,
            )
        )

        # Trading Rules Keys (DOMAIN_POLICY prioritet)
        self.register_key(
            ConfigKey(
                name="MAX_TRADES_PER_DAY",
                type=int,
                default=200,
                min_value=1,
                max_value=10000,
                priority_profile=PriorityProfile.DOMAIN_POLICY,
                allowed_sources=["runtime", "files", "feature_flags", "settings"],
                namespaces=["trading_rules"],
                description="Max Trades Per Day - Maximalt antal affärer per dag",
                restart_required=False,
            )
        )

        self.register_key(
            ConfigKey(
                name="MAX_TRADES_PER_SYMBOL_PER_DAY",
                type=int,
                default=0,
                min_value=0,
                max_value=1000,
                priority_profile=PriorityProfile.DOMAIN_POLICY,
                allowed_sources=["runtime", "files", "feature_flags", "settings"],
                namespaces=["trading_rules"],
                description="Max Trades Per Symbol Per Day - Max affärer per symbol per dag (0 = inga gränser)",
                restart_required=False,
            )
        )

        self.register_key(
            ConfigKey(
                name="TRADE_COOLDOWN_SECONDS",
                type=int,
                default=60,
                min_value=1,
                max_value=3600,
                priority_profile=PriorityProfile.DOMAIN_POLICY,
                allowed_sources=["runtime", "files", "feature_flags", "settings"],
                namespaces=["trading_rules"],
                description="Trade Cooldown Seconds - Väntetid mellan affärer i sekunder",
                restart_required=False,
            )
        )

        # Trading Rules Keys (DOMAIN_POLICY prioritet) - Namespaced för UnifiedConfigManager
        self.register_key(
            ConfigKey(
                name="trading_rules.MAX_TRADES_PER_DAY",
                type=int,
                default=200,
                min_value=1,
                max_value=10000,
                priority_profile=PriorityProfile.DOMAIN_POLICY,
                allowed_sources=["runtime", "files", "settings"],
                restart_required=False,
                namespaces=["trading_rules"],
                description="Max Trades Per Day - Global gräns för antal affärer per dag",
            )
        )

        self.register_key(
            ConfigKey(
                name="trading_rules.MAX_TRADES_PER_SYMBOL_PER_DAY",
                type=int,
                default=0,
                min_value=0,
                max_value=1000,
                priority_profile=PriorityProfile.DOMAIN_POLICY,
                allowed_sources=["runtime", "files", "settings"],
                restart_required=False,
                namespaces=["trading_rules"],
                description="Max Trades Per Symbol Per Day - Gräns per symbol per dag",
            )
        )

        self.register_key(
            ConfigKey(
                name="trading_rules.TRADE_COOLDOWN_SECONDS",
                type=int,
                default=60,
                min_value=0,
                max_value=3600,
                priority_profile=PriorityProfile.DOMAIN_POLICY,
                allowed_sources=["runtime", "files", "settings"],
                restart_required=False,
                namespaces=["trading_rules"],
                description="Trade Cooldown Seconds - Cooldown mellan affärer i sekunder",
            )
        )

        # Scheduler Keys
        self.register_key(
            ConfigKey(
                name="SCHEDULER_ENABLED",
                type=bool,
                default=True,
                priority_profile=PriorityProfile.GLOBAL,
                allowed_sources=["runtime", "feature_flags", "settings"],
                description="Scheduler Enabled - Aktivera bakgrundsscheduler",
                restart_required=True,
            )
        )

        # Authentication Keys
        self.register_key(
            ConfigKey(
                name="AUTH_REQUIRED",
                type=bool,
                default=False,
                priority_profile=PriorityProfile.GLOBAL,
                allowed_sources=["runtime", "settings"],
                description="Auth Required - Kräv autentisering för API:er",
                restart_required=True,
            )
        )

        # API Keys (sensitive)
        self.register_key(
            ConfigKey(
                name="BITFINEX_API_KEY",
                type=str,
                default="",
                priority_profile=PriorityProfile.GLOBAL,
                allowed_sources=["settings"],
                sensitive=True,
                description="Bitfinex API Key - API-nyckel för Bitfinex",
                restart_required=True,
            )
        )

        self.register_key(
            ConfigKey(
                name="BITFINEX_API_SECRET",
                type=str,
                default="",
                priority_profile=PriorityProfile.GLOBAL,
                allowed_sources=["settings"],
                sensitive=True,
                description="Bitfinex API Secret - API-hemlighet för Bitfinex",
                restart_required=True,
            )
        )

    def register_key(self, key: ConfigKey):
        """
        Registrera en ny konfigurationsnyckel.

        Args:
            key: ConfigKey att registrera
        """
        self._keys[key.name] = key

    def get_key(self, name: str) -> Optional[ConfigKey]:
        """
        Hämta en konfigurationsnyckel.

        Args:
            name: Namn på nyckeln

        Returns:
            ConfigKey om hittad, None annars
        """
        return self._keys.get(name)

    def get_all_keys(self) -> Dict[str, ConfigKey]:
        """
        Hämta alla registrerade nycklar.

        Returns:
            Dictionary med alla nycklar
        """
        return self._keys.copy()

    def get_keys_by_namespace(self, namespace: str) -> Dict[str, ConfigKey]:
        """
        Hämta alla nycklar inom ett namespace.

        Args:
            namespace: Namespace att filtrera på

        Returns:
            Dictionary med nycklar inom namspace
        """
        return {name: key for name, key in self._keys.items() if namespace in key.namespaces}

    def get_keys_by_priority_profile(self, profile: PriorityProfile) -> Dict[str, ConfigKey]:
        """
        Hämta alla nycklar med en specifik prioritetprofil.

        Args:
            profile: Prioritetprofil att filtrera på

        Returns:
            Dictionary med nycklar med profilen
        """
        return {name: key for name, key in self._keys.items() if key.priority_profile == profile}

    def validate_key_value(self, name: str, value: Any) -> bool:
        """
        Validera ett värde för en specifik nyckel.

        Args:
            name: Namn på nyckeln
            value: Värde att validera

        Returns:
            True om värdet är giltigt
        """
        key = self.get_key(name)
        if key is None:
            return False

        return key.validate_value(value)

    def is_sensitive(self, name: str) -> bool:
        """
        Kontrollera om en nyckel är känslig.

        Args:
            name: Namn på nyckeln

        Returns:
            True om nyckeln är känslig
        """
        key = self.get_key(name)
        return key.sensitive if key else False

    def requires_restart(self, name: str) -> bool:
        """
        Kontrollera om en nyckel kräver omstart.

        Args:
            name: Namn på nyckeln

        Returns:
            True om nyckeln kräver omstart
        """
        key = self.get_key(name)
        return key.restart_required if key else False


# Global registry instance
key_registry = KeyRegistry()

# För kompatibilitet med UnifiedConfigManager
KEY_REGISTRY = key_registry.get_all_keys()
