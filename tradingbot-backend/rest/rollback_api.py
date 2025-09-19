"""
Rollback API endpoints för konfigurationshantering

Ger endpoints för snapshots, rollback-operationer och staged rollout.
"""

import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from services.rollback_service import (
    get_rollback_service,
    RollbackService,
    SnapshotType,
    RollbackStatus,
    StagedRolloutStatus,
    Snapshot,
    RollbackOperation,
    StagedRollout,
)
from rest.unified_config_api import get_user_from_token

# Router
router = APIRouter(prefix="/api/v2/rollback", tags=["rollback"])


# Pydantic Models
class CreateSnapshotRequest(BaseModel):
    """Request för att skapa snapshot."""

    name: str = Field(..., description="Snapshot namn")
    description: str = Field("", description="Beskrivning av snapshot")
    snapshot_type: str = Field("manual", description="Typ av snapshot")
    tags: List[str] = Field([], description="Taggar för snapshot")


class SnapshotResponse(BaseModel):
    """Response för snapshot."""

    id: str = Field(..., description="Snapshot ID")
    name: str = Field(..., description="Snapshot namn")
    description: str = Field(..., description="Beskrivning")
    snapshot_type: str = Field(..., description="Typ av snapshot")
    created_at: float = Field(..., description="Skapad timestamp")
    created_by: str = Field(..., description="Skapad av")
    generation: int = Field(..., description="Generationsnummer")
    configuration: Dict[str, Any] = Field(..., description="Konfiguration")
    metadata: Dict[str, Any] = Field(..., description="Metadata")
    tags: List[str] = Field(..., description="Taggar")


class RollbackRequest(BaseModel):
    """Request för rollback."""

    snapshot_id: str = Field(..., description="Snapshot ID att återställa till")


class RollbackResponse(BaseModel):
    """Response för rollback operation."""

    id: str = Field(..., description="Rollback operation ID")
    snapshot_id: str = Field(..., description="Snapshot ID")
    target_generation: int = Field(..., description="Målgeneration")
    status: str = Field(..., description="Status")
    created_at: float = Field(..., description="Skapad timestamp")
    created_by: str = Field(..., description="Initierad av")
    started_at: Optional[float] = Field(None, description="Startad timestamp")
    completed_at: Optional[float] = Field(None, description="Slutförd timestamp")
    error_message: Optional[str] = Field(None, description="Felmeddelande")
    affected_keys: List[str] = Field([], description="Påverkade nycklar")
    metadata: Dict[str, Any] = Field({}, description="Metadata")


class CreateStagedRolloutRequest(BaseModel):
    """Request för att skapa staged rollout."""

    name: str = Field(..., description="Rollout namn")
    description: str = Field("", description="Beskrivning")
    target_keys: List[str] = Field(..., description="Målnycklar")
    rollout_plan: Dict[str, Any] = Field(..., description="Rollout plan")
    success_criteria: Dict[str, Any] = Field({}, description="Framgångskriterier")


class StagedRolloutResponse(BaseModel):
    """Response för staged rollout."""

    id: str = Field(..., description="Rollout ID")
    name: str = Field(..., description="Rollout namn")
    description: str = Field(..., description="Beskrivning")
    target_keys: List[str] = Field(..., description="Målnycklar")
    rollout_plan: Dict[str, Any] = Field(..., description="Rollout plan")
    status: str = Field(..., description="Status")
    created_at: float = Field(..., description="Skapad timestamp")
    created_by: str = Field(..., description="Skapad av")
    started_at: Optional[float] = Field(None, description="Startad timestamp")
    completed_at: Optional[float] = Field(None, description="Slutförd timestamp")
    current_stage: int = Field(..., description="Aktuellt steg")
    total_stages: int = Field(..., description="Totalt antal steg")
    success_criteria: Dict[str, Any] = Field({}, description="Framgångskriterier")
    rollback_snapshot_id: Optional[str] = Field(None, description="Rollback snapshot ID")
    metadata: Dict[str, Any] = Field({}, description="Metadata")


# API Endpoints
@router.post("/snapshots", response_model=SnapshotResponse)
async def create_snapshot(request: CreateSnapshotRequest, user: dict[str, Any] = Depends(get_user_from_token)):
    """Skapa en ny snapshot."""
    try:
        snapshot_type = SnapshotType(request.snapshot_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid snapshot type: {request.snapshot_type}")

    rollback_service = get_rollback_service()

    try:
        snapshot = rollback_service.create_snapshot(
            name=request.name,
            description=request.description,
            snapshot_type=snapshot_type,
            created_by=user.get("user_id", "unknown"),
            tags=request.tags,
        )

        return SnapshotResponse(
            id=snapshot.id,
            name=snapshot.name,
            description=snapshot.description,
            snapshot_type=snapshot.snapshot_type.value,
            created_at=snapshot.created_at,
            created_by=snapshot.created_by,
            generation=snapshot.generation,
            configuration=snapshot.configuration,
            metadata=snapshot.metadata,
            tags=snapshot.tags,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create snapshot: {e}")


@router.get("/snapshots", response_model=List[SnapshotResponse])
async def list_snapshots(
    limit: int = Query(100, description="Maximum number of snapshots"),
    snapshot_type: Optional[str] = Query(None, description="Filter by snapshot type"),
    user: dict[str, Any] = Depends(get_user_from_token),
):
    """Lista snapshots."""
    rollback_service = get_rollback_service()

    snapshot_type_enum = None
    if snapshot_type:
        try:
            snapshot_type_enum = SnapshotType(snapshot_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid snapshot type: {snapshot_type}")

    snapshots = rollback_service.list_snapshots(limit=limit, snapshot_type=snapshot_type_enum)

    return [
        SnapshotResponse(
            id=snapshot.id,
            name=snapshot.name,
            description=snapshot.description,
            snapshot_type=snapshot.snapshot_type.value,
            created_at=snapshot.created_at,
            created_by=snapshot.created_by,
            generation=snapshot.generation,
            configuration=snapshot.configuration,
            metadata=snapshot.metadata,
            tags=snapshot.tags,
        )
        for snapshot in snapshots
    ]


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(snapshot_id: str, user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta specifik snapshot."""
    rollback_service = get_rollback_service()
    snapshot = rollback_service.get_snapshot(snapshot_id)

    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")

    return SnapshotResponse(
        id=snapshot.id,
        name=snapshot.name,
        description=snapshot.description,
        snapshot_type=snapshot.snapshot_type.value,
        created_at=snapshot.created_at,
        created_by=snapshot.created_by,
        generation=snapshot.generation,
        configuration=snapshot.configuration,
        metadata=snapshot.metadata,
        tags=snapshot.tags,
    )


@router.post("/rollback", response_model=RollbackResponse)
async def execute_rollback(request: RollbackRequest, user: dict[str, Any] = Depends(get_user_from_token)):
    """Utför rollback till en snapshot."""
    rollback_service = get_rollback_service()

    try:
        operation = rollback_service.rollback_to_snapshot(
            snapshot_id=request.snapshot_id, created_by=user.get("user_id", "unknown")
        )

        return RollbackResponse(
            id=operation.id,
            snapshot_id=operation.snapshot_id,
            target_generation=operation.target_generation,
            status=operation.status.value,
            created_at=operation.created_at,
            created_by=operation.created_by,
            started_at=operation.started_at,
            completed_at=operation.completed_at,
            error_message=operation.error_message,
            affected_keys=operation.affected_keys,
            metadata=operation.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {e}")


@router.post("/staged-rollouts", response_model=StagedRolloutResponse)
async def create_staged_rollout(
    request: CreateStagedRolloutRequest, user: dict[str, Any] = Depends(get_user_from_token)
):
    """Skapa staged rollout för risknycklar."""
    rollback_service = get_rollback_service()

    try:
        rollout = rollback_service.create_staged_rollout(
            name=request.name,
            target_keys=request.target_keys,
            rollout_plan=request.rollout_plan,
            created_by=user.get("user_id", "unknown"),
            description=request.description,
            success_criteria=request.success_criteria,
        )

        return StagedRolloutResponse(
            id=rollout.id,
            name=rollout.name,
            description=rollout.description,
            target_keys=rollout.target_keys,
            rollout_plan=rollout.rollout_plan,
            status=rollout.status.value,
            created_at=rollout.created_at,
            created_by=rollout.created_by,
            started_at=rollout.started_at,
            completed_at=rollout.completed_at,
            current_stage=rollout.current_stage,
            total_stages=rollout.total_stages,
            success_criteria=rollout.success_criteria,
            rollback_snapshot_id=rollout.rollback_snapshot_id,
            metadata=rollout.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create staged rollout: {e}")


@router.post("/staged-rollouts/{rollout_id}/start", response_model=StagedRolloutResponse)
async def start_staged_rollout(rollout_id: str, user: dict[str, Any] = Depends(get_user_from_token)):
    """Starta staged rollout."""
    rollback_service = get_rollback_service()

    try:
        rollout = rollback_service.start_staged_rollout(rollout_id)

        return StagedRolloutResponse(
            id=rollout.id,
            name=rollout.name,
            description=rollout.description,
            target_keys=rollout.target_keys,
            rollout_plan=rollout.rollout_plan,
            status=rollout.status.value,
            created_at=rollout.created_at,
            created_by=rollout.created_by,
            started_at=rollout.started_at,
            completed_at=rollout.completed_at,
            current_stage=rollout.current_stage,
            total_stages=rollout.total_stages,
            success_criteria=rollout.success_criteria,
            rollback_snapshot_id=rollout.rollback_snapshot_id,
            metadata=rollout.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start staged rollout: {e}")


@router.get("/staged-rollouts", response_model=List[StagedRolloutResponse])
async def list_staged_rollouts(
    status: Optional[str] = Query(None, description="Filter by status"),
    user: dict[str, Any] = Depends(get_user_from_token),
):
    """Lista staged rollouts."""
    # Detta skulle kräva en list_staged_rollouts metod i RollbackService
    # För nu returnerar vi tom lista
    return []


@router.get("/staged-rollouts/{rollout_id}", response_model=StagedRolloutResponse)
async def get_staged_rollout(rollout_id: str, user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta specifik staged rollout."""
    rollback_service = get_rollback_service()
    rollout = rollback_service._get_staged_rollout(rollout_id)

    if not rollout:
        raise HTTPException(status_code=404, detail=f"Staged rollout {rollout_id} not found")

    return StagedRolloutResponse(
        id=rollout.id,
        name=rollout.name,
        description=rollout.description,
        target_keys=rollout.target_keys,
        rollout_plan=rollout.rollout_plan,
        status=rollout.status.value,
        created_at=rollout.created_at,
        created_by=rollout.created_by,
        started_at=rollout.started_at,
        completed_at=rollout.completed_at,
        current_stage=rollout.current_stage,
        total_stages=rollout.total_stages,
        success_criteria=rollout.success_criteria,
        rollback_snapshot_id=rollout.rollback_snapshot_id,
        metadata=rollout.metadata,
    )


@router.get("/stats")
async def get_rollback_stats(user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta statistik för rollback service."""
    rollback_service = get_rollback_service()
    stats = rollback_service.get_rollback_service_stats()

    return {"rollback_service_stats": stats, "timestamp": time.time()}


@router.post("/emergency-snapshot")
async def create_emergency_snapshot(
    name: str = "Emergency Snapshot",
    description: str = "Emergency snapshot created via API",
    user: dict[str, Any] = Depends(get_user_from_token),
):
    """Skapa nödsnapshot."""
    rollback_service = get_rollback_service()

    try:
        snapshot = rollback_service.create_snapshot(
            name=name,
            description=description,
            snapshot_type=SnapshotType.EMERGENCY,
            created_by=user.get("user_id", "unknown"),
            tags=["emergency", "api-created"],
        )

        return {
            "success": True,
            "snapshot_id": snapshot.id,
            "message": f"Emergency snapshot {snapshot.id} created successfully",
            "generation": snapshot.generation,
            "keys_captured": len(snapshot.configuration),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create emergency snapshot: {e}")


@router.post("/snapshots/{snapshot_id}/restore")
async def restore_from_snapshot(snapshot_id: str, user: dict[str, Any] = Depends(get_user_from_token)):
    """Återställ från snapshot (alias för rollback)."""
    rollback_service = get_rollback_service()

    try:
        operation = rollback_service.rollback_to_snapshot(
            snapshot_id=snapshot_id, created_by=user.get("user_id", "unknown")
        )

        return {
            "success": True,
            "operation_id": operation.id,
            "message": f"Restore operation {operation.id} initiated",
            "target_generation": operation.target_generation,
            "status": operation.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}")


@router.get("/health")
async def get_rollback_health(user: dict[str, Any] = Depends(get_user_from_token)):
    """Hämta hälsostatus för rollback service."""
    rollback_service = get_rollback_service()

    try:
        # Testa grundläggande funktionalitet
        stats = rollback_service.get_rollback_service_stats()

        return {
            "healthy": True,
            "timestamp": time.time(),
            "stats": stats,
            "database_accessible": True,
            "service_operational": True,
        }
    except Exception as e:
        return {
            "healthy": False,
            "timestamp": time.time(),
            "error": str(e),
            "database_accessible": False,
            "service_operational": False,
        }
