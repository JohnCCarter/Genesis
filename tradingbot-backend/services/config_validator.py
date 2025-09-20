"""
ConfigValidator v2 med key registry integration och domänspecifik validering

Validerar konfigurationsvärden baserat på schema och domänspecifika regler.
"""

import re
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from config.key_registry import KEY_REGISTRY, ConfigKey
from config.priority_profiles import PriorityProfile


class ValidationSeverity(Enum):
    """Valideringsseveritet."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Resultat av validering."""

    is_valid: bool
    severity: ValidationSeverity
    message: str
    key: str
    value: Any
    suggested_fix: str | None = None


@dataclass
class ValidationRule:
    """En valideringsregel."""

    name: str
    description: str
    validator: Callable[[Any, ConfigKey], ValidationResult]
    severity: ValidationSeverity = ValidationSeverity.ERROR
    domains: list[str] = None  # None betyder alla domäner


class ConfigValidator:
    """
    Avancerad konfigurationsvaliderare med domänspecifik logik.
    """

    def __init__(self):
        """Initiera validator."""
        self._rules: dict[str, list[ValidationRule]] = {}
        self._domain_rules: dict[str, list[ValidationRule]] = {}
        self._register_default_rules()

    def _register_default_rules(self):
        """Registrera standardvalideringsregler."""
        # Typvalidering
        self.add_rule(
            ValidationRule(
                name="type_validation",
                description="Validerar att värdet är av rätt typ",
                validator=self._validate_type,
                severity=ValidationSeverity.ERROR,
            )
        )

        # Min/max-validering
        self.add_rule(
            ValidationRule(
                name="range_validation",
                description="Validerar att värdet är inom tillåtna gränser",
                validator=self._validate_range,
                severity=ValidationSeverity.ERROR,
            )
        )

        # Sensitive data-validering
        self.add_rule(
            ValidationRule(
                name="sensitive_validation",
                description="Validerar känsliga data",
                validator=self._validate_sensitive,
                severity=ValidationSeverity.CRITICAL,
                domains=["auth", "api_keys"],
            )
        )

        # Trading-specifika regler
        self.add_rule(
            ValidationRule(
                name="trading_rules_validation",
                description="Validerar trading-regler",
                validator=self._validate_trading_rules,
                severity=ValidationSeverity.WARNING,
                domains=["trading"],
            )
        )

        # Risk-specifika regler
        self.add_rule(
            ValidationRule(
                name="risk_validation",
                description="Validerar riskparametrar",
                validator=self._validate_risk_params,
                severity=ValidationSeverity.CRITICAL,
                domains=["risk"],
            )
        )

        # WebSocket-specifika regler
        self.add_rule(
            ValidationRule(
                name="websocket_validation",
                description="Validerar WebSocket-konfiguration",
                validator=self._validate_websocket,
                severity=ValidationSeverity.WARNING,
                domains=["websocket"],
            )
        )

    def add_rule(self, rule: ValidationRule):
        """Lägg till valideringsregel."""
        if rule.domains is None:
            # Global regel
            if "global" not in self._rules:
                self._rules["global"] = []
            self._rules["global"].append(rule)
        else:
            # Domänspecifik regel
            for domain in rule.domains:
                if domain not in self._domain_rules:
                    self._domain_rules[domain] = []
                self._domain_rules[domain].append(rule)

    def validate(self, key: str, value: Any, context: dict[str, Any] | None = None) -> list[ValidationResult]:
        """
        Validera en konfigurationsnyckel och värde.

        Args:
            key: Konfigurationsnyckel
            value: Värde att validera
            context: Ytterligare kontext för validering

        Returns:
            Lista med valideringsresultat
        """
        if key not in KEY_REGISTRY:
            return [
                ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Unknown configuration key: {key}",
                    key=key,
                    value=value,
                )
            ]

        config_key = KEY_REGISTRY[key]
        results = []

        # Kör globala regler
        if "global" in self._rules:
            for rule in self._rules["global"]:
                result = rule.validator(value, config_key)
                result.key = key
                result.value = value
                results.append(result)

        # Kör domänspecifika regler
        domain = self._get_domain_from_key(key)
        if domain in self._domain_rules:
            for rule in self._domain_rules[domain]:
                result = rule.validator(value, config_key)
                result.key = key
                result.value = value
                results.append(result)

        # Kör kontextspecifika valideringar
        if context:
            context_results = self._validate_context(key, value, config_key, context)
            results.extend(context_results)

        return results

    def _get_domain_from_key(self, key: str) -> str:
        """Extrahera domän från nyckel."""
        if key.startswith("trading_rules."):
            return "trading"
        elif key.startswith("RISK_") or key.startswith("MAX_POSITION"):
            return "risk"
        elif key.startswith("WS_") or key.startswith("BITFINEX_WS"):
            return "websocket"
        elif key.startswith("BITFINEX_API"):
            return "api_keys"
        elif key.startswith("AUTH_") or key.startswith("JWT_"):
            return "auth"
        else:
            return "general"

    def _validate_type(self, value: Any, config_key: ConfigKey) -> ValidationResult:
        """Validera typ."""
        if isinstance(value, config_key.type):
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message=f"Type validation passed for {config_key.name}",
                key=config_key.name,
                value=value,
            )
        else:
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Expected {config_key.type.__name__}, got {type(value).__name__}",
                key=config_key.name,
                value=value,
                suggested_fix=f"Convert to {config_key.type.__name__}",
            )

    def _validate_range(self, value: Any, config_key: ConfigKey) -> ValidationResult:
        """Validera min/max-gränser."""
        if config_key.min_value is not None and value < config_key.min_value:
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Value {value} below minimum {config_key.min_value}",
                key=config_key.name,
                value=value,
                suggested_fix=f"Use value >= {config_key.min_value}",
            )

        if config_key.max_value is not None and value > config_key.max_value:
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Value {value} above maximum {config_key.max_value}",
                key=config_key.name,
                value=value,
                suggested_fix=f"Use value <= {config_key.max_value}",
            )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Range validation passed for {config_key.name}",
            key=config_key.name,
            value=value,
        )

    def _validate_sensitive(self, value: Any, config_key: ConfigKey) -> ValidationResult:
        """Validera känsliga data."""
        if not config_key.sensitive:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message=f"Sensitive validation passed for {config_key.name}",
                key=config_key.name,
                value=value,
            )

        # Kontrollera att känsliga värden inte är tomma eller default
        if value is None or value in ("", config_key.default):
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                message=f"Sensitive key {config_key.name} has no value set",
                key=config_key.name,
                value=value,
                suggested_fix="Set a proper value for this sensitive configuration",
            )

        # Kontrollera längd för API-nycklar
        if "API_KEY" in config_key.name and len(str(value)) < 10:
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message=f"API key {config_key.name} seems too short",
                key=config_key.name,
                value=value,
                suggested_fix="Verify API key is correct",
            )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Sensitive validation passed for {config_key.name}",
            key=config_key.name,
            value=value,
        )

    def _validate_trading_rules(self, value: Any, config_key: ConfigKey) -> ValidationResult:
        """Validera trading-regler."""
        if not config_key.name.startswith("trading_rules."):
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message=f"Not a trading rule, skipping",
                key=config_key.name,
                value=value,
            )

        # Specifika valideringar för trading-regler
        if config_key.name == "trading_rules.MAX_TRADES_PER_DAY":
            if value > 1000:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    message=f"MAX_TRADES_PER_DAY {value} seems very high",
                    key=config_key.name,
                    value=value,
                    suggested_fix="Consider if this is realistic for your trading strategy",
                )

        elif config_key.name == "trading_rules.TRADE_COOLDOWN_SECONDS":
            if value < 1:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"TRADE_COOLDOWN_SECONDS {value} is too low",
                    key=config_key.name,
                    value=value,
                    suggested_fix="Use at least 1 second cooldown",
                )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Trading rules validation passed for {config_key.name}",
            key=config_key.name,
            value=value,
        )

    def _validate_risk_params(self, value: Any, config_key: ConfigKey) -> ValidationResult:
        """Validera riskparametrar."""
        if config_key.name == "RISK_PERCENTAGE":
            if value > 10.0:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Risk percentage {value}% is very high",
                    key=config_key.name,
                    value=value,
                    suggested_fix="Consider reducing risk to < 5%",
                )
            elif value < 0.1:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    message=f"Risk percentage {value}% is very low",
                    key=config_key.name,
                    value=value,
                    suggested_fix="Consider if this provides meaningful exposure",
                )

        elif config_key.name == "MAX_POSITION_SIZE":
            if value > 1.0:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Max position size {value} is > 100%",
                    key=config_key.name,
                    value=value,
                    suggested_fix="Position size should be <= 1.0 (100%)",
                )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Risk validation passed for {config_key.name}",
            key=config_key.name,
            value=value,
        )

    def _validate_websocket(self, value: Any, config_key: ConfigKey) -> ValidationResult:
        """Validera WebSocket-konfiguration."""
        if config_key.name == "WS_SUBSCRIBE_SYMBOLS":
            if isinstance(value, str):
                symbols = value.split(",")
                if len(symbols) > 50:
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        message=f"Too many symbols ({len(symbols)}), may impact performance",
                        key=config_key.name,
                        value=value,
                        suggested_fix="Consider reducing number of symbols",
                    )

                # Kontrollera symbolformat
                for symbol in symbols:
                    if not re.match(r'^t[A-Z]{3,6}USD$', symbol.strip()):
                        return ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.WARNING,
                            message=f"Symbol {symbol} doesn't match expected format",
                            key=config_key.name,
                            value=value,
                            suggested_fix="Use format like tBTCUSD, tETHUSD",
                        )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"WebSocket validation passed for {config_key.name}",
            key=config_key.name,
            value=value,
        )

    def _validate_context(
        self, key: str, value: Any, config_key: ConfigKey, context: dict[str, Any]
    ) -> list[ValidationResult]:
        """Validera baserat på kontext."""
        results = []

        # Kontrollera prioritetsprofil
        priority_profile = context.get("priority_profile")
        if priority_profile == PriorityProfile.DOMAIN_POLICY:
            # För domänspecifika regler, kontrollera att filer finns
            if "files" in config_key.allowed_sources:
                file_path = context.get("file_path")
                if file_path:
                    import os

                    if not os.path.exists(file_path):
                        results.append(
                            ValidationResult(
                                is_valid=False,
                                severity=ValidationSeverity.WARNING,
                                message=f"Referenced file {file_path} does not exist",
                                key=key,
                                value=value,
                                suggested_fix="Create the file or use different source",
                            )
                        )

        # Kontrollera restart-krav
        if config_key.restart_required and context.get("restart_required_check", False):
            results.append(
                ValidationResult(
                    is_valid=True,
                    severity=ValidationSeverity.INFO,
                    message=f"Key {key} requires restart to take effect",
                    key=key,
                    value=value,
                    suggested_fix="Restart the application after setting this value",
                )
            )

        return results

    def validate_all(
        self, config_dict: dict[str, Any], context: dict[str, Any] | None = None
    ) -> dict[str, list[ValidationResult]]:
        """
        Validera hela konfigurationen.

        Args:
            config_dict: Dictionary med konfigurationsvärden
            context: Kontext för validering

        Returns:
            Dictionary med valideringsresultat per nyckel
        """
        results = {}
        for key, value in config_dict.items():
            results[key] = self.validate(key, value, context)
        return results

    def validate_key(self, key: str, value: Any, context: dict[str, Any] | None = None) -> list[ValidationResult]:
        """Alias för validate för kompatibilitet med tester."""
        return self.validate(key, value, context)

    def validate_configuration(
        self, config_dict: dict[str, Any], context: dict[str, Any] | None = None
    ) -> dict[str, list[ValidationResult]]:
        """Alias för validate_all för kompatibilitet med tester."""
        return self.validate_all(config_dict, context)

    def get_validation_summary(self, results: dict[str, list[ValidationResult]]) -> dict[str, Any]:
        """
        Hämta sammanfattning av valideringsresultat.

        Args:
            results: Valideringsresultat

        Returns:
            Sammanfattning
        """
        total_keys = len(results)
        total_validations = sum(len(vals) for vals in results.values())

        by_severity = {
            ValidationSeverity.INFO: 0,
            ValidationSeverity.WARNING: 0,
            ValidationSeverity.ERROR: 0,
            ValidationSeverity.CRITICAL: 0,
        }

        invalid_keys = []

        for key, validations in results.items():
            key_valid = True
            for validation in validations:
                by_severity[validation.severity] += 1
                if not validation.is_valid and validation.severity in [
                    ValidationSeverity.ERROR,
                    ValidationSeverity.CRITICAL,
                ]:
                    key_valid = False

            if not key_valid:
                invalid_keys.append(key)

        return {
            "total_keys": total_keys,
            "total_validations": total_validations,
            "valid_keys": total_keys - len(invalid_keys),
            "invalid_keys": len(invalid_keys),
            "invalid_key_list": invalid_keys,
            "by_severity": {k.value: v for k, v in by_severity.items()},
            "overall_valid": len(invalid_keys) == 0,
        }


# Global instans
_config_validator: ConfigValidator | None = None


def get_config_validator() -> ConfigValidator:
    """Hämta global ConfigValidator-instans."""
    global _config_validator
    if _config_validator is None:
        _config_validator = ConfigValidator()
    return _config_validator


def validate_config(key: str, value: Any, context: dict[str, Any] | None = None) -> list[ValidationResult]:
    """Konvenience-funktion för att validera konfiguration."""
    return get_config_validator().validate(key, value, context)


def validate_all_config(
    config_dict: dict[str, Any], context: dict[str, Any] | None = None
) -> dict[str, list[ValidationResult]]:
    """Konvenience-funktion för att validera hela konfigurationen."""
    return get_config_validator().validate_all(config_dict, context)
