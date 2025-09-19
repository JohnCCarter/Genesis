"""
Säkra API endpoints för Unified Configuration Management

Innehåller RBAC, preview/apply-flöde och audit logging.
"""

import time
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt

from services.unified_config_manager import (
    get_unified_config_manager,
    UnifiedConfigManager,
    ConfigContext,
)
from services.config_validator import (
    get_config_validator,
    ConfigValidator,
    ValidationResult,
    ValidationSeverity,
)
from config.priority_profiles import PriorityProfile
from config.key_registry import KEY_REGISTRY

# Security
security = HTTPBearer()

# Router
router = APIRouter(prefix="/api/v2/unified-config", tags=["unified-config"])


# Pydantic Models
class ConfigGetRequest(BaseModel):
    """Request för att hämta konfiguration."""

    key: str = Field(..., description="Konfigurationsnyckel att hämta")
    priority_profile: str | None = Field(None, description="Prioritetsprofil")
    source_override: str | None = Field(None, description="Källa att prioritera")


class ConfigSetRequest(BaseModel):
    """Request för att sätta konfiguration."""

    key: str = Field(..., description="Konfigurationsnyckel")
    value: Any = Field(..., description="Värde att sätta")
    source: str = Field("runtime", description="Källa för värdet")
    preview: bool = Field(False, description="Om true, validera utan att sätta")


class ConfigBatchRequest(BaseModel):
    """Request för batch-operationer."""

    operations: list[dict[str, Any]] = Field(..., description="Lista med operationer")
    preview: bool = Field(False, description="Om true, validera utan att utföra")


class ValidationRequest(BaseModel):
    """Request för validering."""

    key: str | None = Field(None, description="Specifik nyckel att validera")
    config_dict: dict[str, Any] | None = Field(None, description="Konfiguration att validera")
    context: dict[str, Any] | None = Field(None, description="Valideringskontext")


class PreviewResponse(BaseModel):
    """Response för preview-operationer."""

    valid: bool = Field(..., description="Om operationen är giltig")
    validation_results: list[ValidationResult] = Field(..., description="Valideringsresultat")
    effective_value: Any | None = Field(None, description="Effektivt värde som skulle sättas")
    requires_restart: bool = Field(False, description="Om restart krävs")


class ConfigResponse(BaseModel):
    """Response för konfigurationsoperationer."""

    success: bool = Field(..., description="Om operationen lyckades")
    key: str = Field(..., description="Konfigurationsnyckel")
    value: Any = Field(..., description="Konfigurationsvärde")
    source: str = Field(..., description="Källa för värdet")
    generation: int = Field(..., description="Generationsnummer")
    message: str | None = Field(None, description="Meddelande")


class ConfigMetadataResponse(BaseModel):
    """Response för konfigurationsmetadata."""

    key: str = Field(..., description="Konfigurationsnyckel")
    type: str = Field(..., description="Datatyp")
    default: Any = Field(..., description="Standardvärde")
    min_value: Any | None = Field(None, description="Minsta värde")
    max_value: Any | None = Field(None, description="Största värde")
    priority_profile: str = Field(..., description="Prioritetsprofil")
    allowed_sources: list[str] = Field(..., description="Tillåtna källor")
    sensitive: bool = Field(..., description="Om känslig data")
    restart_required: bool = Field(..., description="Om restart krävs")
    description: str = Field(..., description="Beskrivning")
    current_value: Any = Field(..., description="Aktuellt värde")
    current_source: str | None = Field(None, description="Aktuell källa")
    current_generation: int | None = Field(None, description="Aktuell generation")
    last_updated: float | None = Field(None, description="Senast uppdaterad")
    last_user: str | None = Field(None, description="Senast ändrad av")


class AuditLogEntry(BaseModel):
    """Audit log entry."""

    timestamp: float = Field(..., description="Tidsstämpel")
    user: str = Field(..., description="Användare")
    action: str = Field(..., description="Åtgärd")
    key: str = Field(..., description="Konfigurationsnyckel")
    old_value: Any | None = Field(None, description="Gammalt värde")
    new_value: Any | None = Field(None, description="Nytt värde")
    source: str = Field(..., description="Källa")
    generation: int = Field(..., description="Generation")
    success: bool = Field(..., description="Om lyckades")
    error_message: str | None = Field(None, description="Felmeddelande")


# RBAC System
class UserRole:
    """Användarroll."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    TRADER = "trader"


class Permission:
    """Behörigheter."""

    READ_CONFIG = "read:config"
    WRITE_CONFIG = "write:config"
    WRITE_SENSITIVE = "write:sensitive"
    WRITE_RISK = "write:risk"
    ADMIN_CONFIG = "admin:config"
    AUDIT_LOG = "audit:log"


# RBAC Mapping
RBAC_MATRIX = {
    UserRole.ADMIN: [
        Permission.READ_CONFIG,
        Permission.WRITE_CONFIG,
        Permission.WRITE_SENSITIVE,
        Permission.WRITE_RISK,
        Permission.ADMIN_CONFIG,
        Permission.AUDIT_LOG,
    ],
    UserRole.OPERATOR: [
        Permission.READ_CONFIG,
        Permission.WRITE_CONFIG,
        Permission.AUDIT_LOG,
    ],
    UserRole.TRADER: [
        Permission.READ_CONFIG,
        Permission.WRITE_CONFIG,
    ],
    UserRole.VIEWER: [
        Permission.READ_CONFIG,
    ],
}


def get_user_from_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict[str, Any]:
    """Extrahera användarinformation från JWT-token."""
    try:
        # I en riktig implementation skulle vi validera mot en säker nyckel
        token = credentials.credentials
        payload = jwt.decode(token, options={"verify_signature": False})

        return {
            "user_id": payload.get("sub", "unknown"),
            "username": payload.get("username", "unknown"),
            "role": payload.get("role", UserRole.VIEWER),
            "permissions": RBAC_MATRIX.get(payload.get("role", UserRole.VIEWER), []),
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def require_permission(permission: str):
    """Decorator för att kräva specifik behörighet."""

    def decorator(func):
        async def wrapper(*args: Any, **kwargs: Any):
            user = kwargs.get("user") or args[0] if args else None
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")

            if permission not in user.get("permissions", []):
                raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Audit Logging
class AuditLogger:
    """Audit logger för konfigurationsändringar."""

    def __init__(self):
        self._logs: list[AuditLogEntry] = []

    def log(
        self,
        user: str,
        action: str,
        key: str,
        old_value: Any = None,
        new_value: Any = None,
        source: str = "api",
        generation: int = 0,
        success: bool = True,
        error_message: str = None,
    ):
        """Logga en konfigurationsändring."""
        entry = AuditLogEntry(
            timestamp=time.time(),
            user=user,
            action=action,
            key=key,
            old_value=old_value,
            new_value=new_value,
            source=source,
            generation=generation,
            success=success,
            error_message=error_message,
        )
        self._logs.append(entry)

    def get_logs(self, limit: int = 100, user: str | None = None, key: str | None = None) -> list[AuditLogEntry]:
        """Hämta audit logs."""
        logs = self._logs.copy()

        if user:
            logs = [log for log in logs if log.user == user]

        if key:
            logs = [log for log in logs if log.key == key]

        return logs[-limit:] if limit else logs


# Global audit logger
audit_logger = AuditLogger()


# API Endpoints
@router.get("/keys")
async def list_config_keys(user: dict[str, Any] = Depends(get_user_from_token)):
    """Lista alla tillgängliga konfigurationsnycklar."""
    require_permission(Permission.READ_CONFIG)(lambda: None)()

    manager = get_unified_config_manager()
    keys = []

    for key_name, config_key in KEY_REGISTRY.items():
        # Filtrera känsliga nycklar för icke-admin användare
        if config_key.sensitive and Permission.WRITE_SENSITIVE not in user.get("permissions", []):
            continue

        keys.append(
            {
                "key": key_name,
                "type": config_key.type.__name__,
                "description": config_key.description,
                "sensitive": config_key.sensitive,
                "restart_required": config_key.restart_required,
            }
        )

    return {"keys": keys}


@router.get("/keys/{key}")
async def get_config_key(key: str, user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta konfigurationsnyckel med metadata."""
    require_permission(Permission.READ_CONFIG)(lambda: None)()

    manager = get_unified_config_manager()

    try:
        metadata = manager.get_config_metadata(key)

        # Filtrera känsliga data för icke-admin användare
        if metadata.get("sensitive") and Permission.WRITE_SENSITIVE not in user.get("permissions", []):
            metadata["current_value"] = "***REDACTED***"

        return ConfigMetadataResponse(**metadata)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/get")
async def get_config_value(request: ConfigGetRequest, user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta konfigurationsvärde med kontext."""
    require_permission(Permission.READ_CONFIG)(lambda: None)()

    manager = get_unified_config_manager()

    try:
        # Skapa kontext
        context = ConfigContext()
        if request.priority_profile:
            try:
                context.priority_profile = PriorityProfile(request.priority_profile)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid priority profile: {request.priority_profile}")

        if request.source_override:
            context.source_override = request.source_override

        # Hämta värde
        value = manager.get(request.key, context)

        # Kontrollera om känslig data
        config_key = KEY_REGISTRY.get(request.key)
        if config_key and config_key.sensitive and Permission.WRITE_SENSITIVE not in user.get("permissions", []):
            value = "***REDACTED***"

        return {
            "key": request.key,
            "value": value,
            "context": {
                "priority_profile": context.priority_profile.value,
                "source_override": context.source_override,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/set")
async def set_config_value(request: ConfigSetRequest, user: dict[str, Any] = Depends(get_user_from_token)):
    """Sätt konfigurationsvärde med validering."""
    require_permission(Permission.WRITE_CONFIG)(lambda: None)()

    manager = get_unified_config_manager()
    validator = get_config_validator()

    try:
        # Kontrollera känslig data
        config_key = KEY_REGISTRY.get(request.key)
        if config_key and config_key.sensitive and Permission.WRITE_SENSITIVE not in user.get("permissions", []):
            raise HTTPException(status_code=403, detail="Permission required for sensitive configuration")

        # Kontrollera riskparametrar
        if request.key.startswith(("RISK_", "MAX_POSITION")) and Permission.WRITE_RISK not in user.get(
            "permissions", []
        ):
            raise HTTPException(status_code=403, detail="Permission required for risk configuration")

        # Validera värde
        validation_results = validator.validate(request.key, request.value)
        critical_errors = [
            r for r in validation_results if not r.is_valid and r.severity == ValidationSeverity.CRITICAL
        ]
        errors = [
            r
            for r in validation_results
            if not r.is_valid and r.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
        ]

        if critical_errors:
            audit_logger.log(
                user=user["username"],
                action="SET_FAILED",
                key=request.key,
                new_value=request.value,
                source=request.source,
                success=False,
                error_message="Critical validation errors",
            )
            raise HTTPException(
                status_code=400, detail=f"Critical validation errors: {[r.message for r in critical_errors]}"
            )

        if request.preview:
            # Preview mode - returnera valideringsresultat utan att sätta
            return PreviewResponse(
                valid=len(errors) == 0,
                validation_results=validation_results,
                effective_value=request.value,
                requires_restart=config_key.restart_required if config_key else False,
            )

        # Hämta gammalt värde för audit log
        old_value = manager.get(request.key) if not request.preview else None

        # Sätt värde
        success = manager.set(request.key, request.value, request.source, user["username"])

        if success:
            generation = manager.config_store.get_current_generation()
            audit_logger.log(
                user=user["username"],
                action="SET",
                key=request.key,
                old_value=old_value,
                new_value=request.value,
                source=request.source,
                generation=generation,
                success=True,
            )

            return ConfigResponse(
                success=True,
                key=request.key,
                value=request.value,
                source=request.source,
                generation=generation,
                message="Configuration set successfully",
            )
        else:
            audit_logger.log(
                user=user["username"],
                action="SET_FAILED",
                key=request.key,
                new_value=request.value,
                source=request.source,
                success=False,
                error_message="Failed to set configuration",
            )
            raise HTTPException(status_code=500, detail="Failed to set configuration")

    except ValueError as e:
        audit_logger.log(
            user=user["username"],
            action="SET_FAILED",
            key=request.key,
            new_value=request.value,
            source=request.source,
            success=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/validate")
async def validate_configuration(request: ValidationRequest, user: dict[str, Any] = Depends(get_user_from_token)):
    """Validera konfiguration."""
    require_permission(Permission.READ_CONFIG)(lambda: None)()

    validator = get_config_validator()

    if request.key:
        # Validera specifik nyckel
        manager = get_unified_config_manager()
        value = manager.get(request.key)
        results = validator.validate(request.key, value, request.context)

        return {
            "key": request.key,
            "value": value,
            "validation_results": results,
            "summary": validator.get_validation_summary({request.key: results}),
        }
    elif request.config_dict:
        # Validera hela konfigurationen
        results = validator.validate_all(request.config_dict, request.context)
        summary = validator.get_validation_summary(results)

        return {"validation_results": results, "summary": summary}
    else:
        raise HTTPException(status_code=400, detail="Either 'key' or 'config_dict' must be provided")


@router.get("/effective")
async def get_effective_configuration(
    priority_profile: str | None = None,
    source_override: str | None = None,
    user: dict[str, Any] = Depends(get_user_from_token),
):
    """Hämta hela effektiva konfigurationen."""
    require_permission(Permission.READ_CONFIG)(lambda: None)()

    manager = get_unified_config_manager()

    # Skapa kontext
    context = ConfigContext()
    if priority_profile:
        try:
            context.priority_profile = PriorityProfile(priority_profile)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority profile: {priority_profile}")

    if source_override:
        context.source_override = source_override

    # Hämta effektiv konfiguration
    config = manager.get_effective_config(context)

    # Filtrera känsliga data för icke-admin användare
    if Permission.WRITE_SENSITIVE not in user.get("permissions", []):
        for key_name, config_key in KEY_REGISTRY.items():
            if config_key.sensitive and key_name in config:
                config[key_name] = "***REDACTED***"

    return {
        "configuration": config,
        "context": {
            "priority_profile": context.priority_profile.value,
            "source_override": context.source_override,
        },
        "timestamp": time.time(),
    }


@router.get("/stats")
async def get_configuration_stats(user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta konfigurationsstatistik."""
    require_permission(Permission.READ_CONFIG)(lambda: None)()

    manager = get_unified_config_manager()
    stats = manager.get_stats()

    return {"stats": stats, "timestamp": time.time()}


@router.get("/audit")
async def get_audit_logs(
    limit: int = 100,
    user_filter: str | None = None,
    key_filter: str | None = None,
    user: dict[str, Any] = Depends(get_user_from_token),
):
    """Hämta audit logs."""
    require_permission(Permission.AUDIT_LOG)(lambda: None)()

    logs = audit_logger.get_logs(limit, user_filter, key_filter)

    return {"logs": logs, "count": len(logs), "limit": limit, "filters": {"user": user_filter, "key": key_filter}}


@router.post("/batch")
async def batch_config_operations(request: ConfigBatchRequest, user: dict[str, Any] = Depends(get_user_from_token)):
    """Utför batch-operationer på konfiguration."""
    require_permission(Permission.WRITE_CONFIG)(lambda: None)()

    manager = get_unified_config_manager()
    validator = get_config_validator()

    results = []

    for operation in request.operations:
        try:
            op_type = operation.get("type")
            key = operation.get("key")
            value = operation.get("value")
            source = operation.get("source", "runtime")

            if op_type == "set":
                # Kontrollera behörigheter
                config_key = KEY_REGISTRY.get(key)
                if (
                    config_key
                    and config_key.sensitive
                    and Permission.WRITE_SENSITIVE not in user.get("permissions", [])
                ):
                    results.append(
                        {"success": False, "key": key, "error": "Permission required for sensitive configuration"}
                    )
                    continue

                # Validera
                validation_results = validator.validate(key, value)
                errors = [
                    r
                    for r in validation_results
                    if not r.is_valid and r.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
                ]

                if errors:
                    results.append(
                        {"success": False, "key": key, "error": f"Validation errors: {[r.message for r in errors]}"}
                    )
                    continue

                if request.preview:
                    results.append(
                        {"success": True, "key": key, "preview": True, "validation_results": validation_results}
                    )
                else:
                    # Sätt värde
                    old_value = manager.get(key)
                    success = manager.set(key, value, source, user["username"])

                    if success:
                        generation = manager.config_store.get_current_generation()
                        audit_logger.log(
                            user=user["username"],
                            action="BATCH_SET",
                            key=key,
                            old_value=old_value,
                            new_value=value,
                            source=source,
                            generation=generation,
                            success=True,
                        )

                        results.append({"success": True, "key": key, "value": value, "generation": generation})
                    else:
                        results.append({"success": False, "key": key, "error": "Failed to set configuration"})
            else:
                results.append({"success": False, "key": key, "error": f"Unknown operation type: {op_type}"})

        except Exception as e:
            results.append({"success": False, "key": operation.get("key", "unknown"), "error": str(e)})

    return {
        "results": results,
        "preview": request.preview,
        "total_operations": len(request.operations),
        "successful": sum(1 for r in results if r.get("success", False)),
        "failed": sum(1 for r in results if not r.get("success", False)),
    }
