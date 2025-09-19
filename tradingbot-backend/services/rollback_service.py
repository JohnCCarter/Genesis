"""
Rollback Service för konfigurationshantering

Hanterar snapshots, rollback-operationer och staged rollout för risknycklar.
"""

import json
import time
import threading
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3
import logging
from pathlib import Path

from services.config_store import ConfigStore, ConfigValue
from services.unified_config_manager import UnifiedConfigManager, ConfigContext
from config.priority_profiles import PriorityProfile

logger = logging.getLogger(__name__)


class SnapshotType(Enum):
    """Typer av snapshots."""

    MANUAL = "manual"  # Manuellt skapad snapshot
    AUTOMATIC = "automatic"  # Automatisk snapshot (pre-risk-change)
    SCHEDULED = "scheduled"  # Schemalagd snapshot
    EMERGENCY = "emergency"  # Nödsnapshot


class RollbackStatus(Enum):
    """Status för rollback-operationer."""

    PENDING = "pending"  # Väntar på godkännande
    IN_PROGRESS = "in_progress"  # Pågående rollback
    COMPLETED = "completed"  # Rollback slutförd
    FAILED = "failed"  # Rollback misslyckades
    CANCELLED = "cancelled"  # Rollback avbruten


class StagedRolloutStatus(Enum):
    """Status för staged rollout."""

    PENDING = "pending"  # Väntar på start
    ACTIVE = "active"  # Aktiv staged rollout
    COMPLETED = "completed"  # Slutförd
    ROLLED_BACK = "rolled_back"  # Återkallad
    PAUSED = "paused"  # Pausad


@dataclass
class Snapshot:
    """En konfigurationssnapshot."""

    id: str
    name: str
    description: str
    snapshot_type: SnapshotType
    created_at: float
    created_by: str
    generation: int
    configuration: Dict[str, Any]
    metadata: Dict[str, Any]
    tags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Konvertera till dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Snapshot':
        """Skapa från dictionary."""
        data['snapshot_type'] = SnapshotType(data['snapshot_type'])
        return cls(**data)


@dataclass
class RollbackOperation:
    """En rollback-operation."""

    id: str
    snapshot_id: str
    target_generation: int
    status: RollbackStatus
    created_at: float
    created_by: str
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    affected_keys: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.affected_keys is None:
            self.affected_keys = []
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Konvertera till dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RollbackOperation':
        """Skapa från dictionary."""
        data['status'] = RollbackStatus(data['status'])
        return cls(**data)


@dataclass
class StagedRollout:
    """En staged rollout för risknycklar."""

    id: str
    name: str
    description: str
    target_keys: List[str]
    rollout_plan: Dict[str, Any]  # Staged rollout plan
    status: StagedRolloutStatus
    created_at: float
    created_by: str
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    current_stage: int = 0
    total_stages: int = 0
    success_criteria: Dict[str, Any] = None
    rollback_snapshot_id: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.success_criteria is None:
            self.success_criteria = {}
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Konvertera till dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StagedRollout':
        """Skapa från dictionary."""
        data['status'] = StagedRolloutStatus(data['status'])
        return cls(**data)


class RollbackService:
    """
    Service för rollback-operationer och staged rollout.
    """

    def __init__(self, config_store: ConfigStore, config_manager: UnifiedConfigManager):
        """Initiera rollback service."""
        self.config_store = config_store
        self.config_manager = config_manager
        self._lock = threading.RLock()
        self._db_path = "rollback_service.db"

        # Initiera databas
        self._init_database()

        # Aktiva staged rollouts
        self._active_rollouts: Dict[str, StagedRollout] = {}

        # Starta bakgrundstrådar
        self._start_background_tasks()

    def _init_database(self):
        """Initiera SQLite-databas för rollback data."""
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self._db_path) as conn:
            # Snapshots tabell
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    snapshot_type TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    created_by TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    configuration TEXT NOT NULL,
                    metadata TEXT,
                    tags TEXT
                )
            """
            )

            # Rollback operations tabell
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rollback_operations (
                    id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    target_generation INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    created_by TEXT NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    error_message TEXT,
                    affected_keys TEXT,
                    metadata TEXT,
                    FOREIGN KEY (snapshot_id) REFERENCES snapshots (id)
                )
            """
            )

            # Staged rollouts tabell
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS staged_rollouts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    target_keys TEXT NOT NULL,
                    rollout_plan TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    created_by TEXT NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    current_stage INTEGER DEFAULT 0,
                    total_stages INTEGER DEFAULT 0,
                    success_criteria TEXT,
                    rollback_snapshot_id TEXT,
                    metadata TEXT
                )
            """
            )

            # Skapa index
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_generation ON snapshots(generation)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rollback_snapshot ON rollback_operations(snapshot_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rollout_status ON staged_rollouts(status)")

            conn.commit()

    def _start_background_tasks(self):
        """Starta bakgrundstrådar för staged rollout hantering."""

        def rollout_monitor():
            """Övervaka aktiva staged rollouts."""
            while True:
                try:
                    time.sleep(30)  # Kontrollera var 30:e sekund
                    self._monitor_active_rollouts()
                except Exception as e:
                    logger.error(f"Error in rollout monitor: {e}")

        threading.Thread(target=rollout_monitor, daemon=True).start()

    def create_snapshot(
        self,
        name: str,
        description: str = "",
        snapshot_type: SnapshotType = SnapshotType.MANUAL,
        created_by: str = "system",
        tags: List[str] | None = None,
    ) -> Snapshot:
        """
        Skapa en snapshot av aktuell konfiguration.

        Args:
            name: Snapshot namn
            description: Beskrivning
            snapshot_type: Typ av snapshot
            created_by: Användare som skapade snapshot
            tags: Taggar för snapshot

        Returns:
            Skapad snapshot
        """
        if tags is None:
            tags = []

        snapshot_id = f"snapshot_{int(time.time() * 1000)}"
        current_time = time.time()

        # Hämta aktuell konfiguration
        context = ConfigContext()
        configuration = self.config_manager.get_effective_config(context)
        generation = self.config_store.get_current_generation()

        # Skapa metadata
        metadata = {
            "total_keys": len(configuration),
            "context": {
                "priority_profile": context.priority_profile.value,
                "user": context.user,
                "source_override": context.source_override,
            },
            "system_info": {"python_version": "3.11", "service_version": "1.0.0"},  # Placeholder  # Placeholder
        }

        snapshot = Snapshot(
            id=snapshot_id,
            name=name,
            description=description,
            snapshot_type=snapshot_type,
            created_at=current_time,
            created_by=created_by,
            generation=generation,
            configuration=configuration,
            metadata=metadata,
            tags=tags,
        )

        # Spara i databas
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO snapshots 
                    (id, name, description, snapshot_type, created_at, created_by, 
                     generation, configuration, metadata, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        snapshot.id,
                        snapshot.name,
                        snapshot.description,
                        snapshot.snapshot_type.value,
                        snapshot.created_at,
                        snapshot.created_by,
                        snapshot.generation,
                        json.dumps(snapshot.configuration),
                        json.dumps(snapshot.metadata),
                        json.dumps(snapshot.tags),
                    ),
                )
                conn.commit()

        logger.info(f"Created snapshot {snapshot_id} with {len(configuration)} keys")
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Hämta snapshot med ID."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, name, description, snapshot_type, created_at, created_by,
                       generation, configuration, metadata, tags
                FROM snapshots WHERE id = ?
            """,
                (snapshot_id,),
            )

            row = cursor.fetchone()
            if row:
                return Snapshot.from_dict(
                    {
                        'id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'snapshot_type': row[3],
                        'created_at': row[4],
                        'created_by': row[5],
                        'generation': row[6],
                        'configuration': json.loads(row[7]),
                        'metadata': json.loads(row[8]) if row[8] else {},
                        'tags': json.loads(row[9]) if row[9] else [],
                    }
                )

        return None

    def list_snapshots(self, limit: int = 100, snapshot_type: Optional[SnapshotType] = None) -> List[Snapshot]:
        """Lista snapshots med filtrering."""
        query = """
            SELECT id, name, description, snapshot_type, created_at, created_by,
                   generation, configuration, metadata, tags
            FROM snapshots
        """
        params = []

        if snapshot_type:
            query += " WHERE snapshot_type = ?"
            params.append(snapshot_type.value)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        snapshots = []
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(query, params)

            for row in cursor.fetchall():
                snapshots.append(
                    Snapshot.from_dict(
                        {
                            'id': row[0],
                            'name': row[1],
                            'description': row[2],
                            'snapshot_type': row[3],
                            'created_at': row[4],
                            'created_by': row[5],
                            'generation': row[6],
                            'configuration': json.loads(row[7]),
                            'metadata': json.loads(row[8]) if row[8] else {},
                            'tags': json.loads(row[9]) if row[9] else [],
                        }
                    )
                )

        return snapshots

    def rollback_to_snapshot(self, snapshot_id: str, created_by: str = "system") -> RollbackOperation:
        """
        Utför rollback till en snapshot.

        Args:
            snapshot_id: ID för snapshot att återställa till
            created_by: Användare som initierade rollback

        Returns:
            Rollback operation
        """
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        operation_id = f"rollback_{int(time.time() * 1000)}"
        current_time = time.time()

        # Skapa rollback operation
        operation = RollbackOperation(
            id=operation_id,
            snapshot_id=snapshot_id,
            target_generation=snapshot.generation,
            status=RollbackStatus.PENDING,
            created_at=current_time,
            created_by=created_by,
            metadata={"snapshot_name": snapshot.name, "snapshot_description": snapshot.description},
        )

        # Spara operation i databas
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO rollback_operations 
                    (id, snapshot_id, target_generation, status, created_at, created_by,
                     started_at, completed_at, error_message, affected_keys, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        operation.id,
                        operation.snapshot_id,
                        operation.target_generation,
                        operation.status.value,
                        operation.created_at,
                        operation.created_by,
                        operation.started_at,
                        operation.completed_at,
                        operation.error_message,
                        json.dumps(operation.affected_keys),
                        json.dumps(operation.metadata),
                    ),
                )
                conn.commit()

        # Utför rollback
        try:
            self._execute_rollback(operation, snapshot)
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            operation.status = RollbackStatus.FAILED
            operation.error_message = str(e)
            self._update_rollback_operation(operation)
            raise

        return operation

    def _execute_rollback(self, operation: RollbackOperation, snapshot: Snapshot):
        """Utför faktisk rollback-operation."""
        operation.status = RollbackStatus.IN_PROGRESS
        operation.started_at = time.time()
        self._update_rollback_operation(operation)

        try:
            affected_keys = []

            # Återställ konfiguration från snapshot
            for key, value in snapshot.configuration.items():
                try:
                    # Sätt värdet via config store
                    self.config_store.set(key, value, "rollback", operation.created_by)
                    affected_keys.append(key)
                except Exception as e:
                    logger.warning(f"Failed to rollback key {key}: {e}")

            # Uppdatera operation
            operation.affected_keys = affected_keys
            operation.status = RollbackStatus.COMPLETED
            operation.completed_at = time.time()
            self._update_rollback_operation(operation)

            logger.info(f"Rollback completed: {len(affected_keys)} keys restored")

        except Exception as e:
            operation.status = RollbackStatus.FAILED
            operation.error_message = str(e)
            operation.completed_at = time.time()
            self._update_rollback_operation(operation)
            raise

    def _update_rollback_operation(self, operation: RollbackOperation):
        """Uppdatera rollback operation i databas."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE rollback_operations SET
                    status = ?, started_at = ?, completed_at = ?, error_message = ?,
                    affected_keys = ?, metadata = ?
                WHERE id = ?
            """,
                (
                    operation.status.value,
                    operation.started_at,
                    operation.completed_at,
                    operation.error_message,
                    json.dumps(operation.affected_keys),
                    json.dumps(operation.metadata),
                    operation.id,
                ),
            )
            conn.commit()

    def create_staged_rollout(
        self,
        name: str,
        target_keys: List[str],
        rollout_plan: Dict[str, Any],
        created_by: str = "system",
        description: str = "",
        success_criteria: Dict[str, Any] | None = None,
    ) -> StagedRollout:
        """
        Skapa staged rollout för risknycklar.

        Args:
            name: Rollout namn
            target_keys: Nycklar att inkludera i rollout
            rollout_plan: Plan för staged rollout
            created_by: Användare som skapade rollout
            description: Beskrivning
            success_criteria: Kriterier för framgång

        Returns:
            Skapad staged rollout
        """
        if success_criteria is None:
            success_criteria = {}

        rollout_id = f"rollout_{int(time.time() * 1000)}"
        current_time = time.time()

        # Validera target keys
        risk_keys = [key for key in target_keys if self._is_risk_key(key)]
        if not risk_keys:
            raise ValueError("No risk keys found in target keys")

        # Skapa rollback snapshot före rollout
        rollback_snapshot = self.create_snapshot(
            name=f"Pre-rollout snapshot for {name}",
            description=f"Automatic snapshot before staged rollout {name}",
            snapshot_type=SnapshotType.AUTOMATIC,
            created_by=created_by,
            tags=["staged-rollout", "pre-rollout"],
        )

        # Skapa staged rollout
        rollout = StagedRollout(
            id=rollout_id,
            name=name,
            description=description,
            target_keys=risk_keys,
            rollout_plan=rollout_plan,
            status=StagedRolloutStatus.PENDING,
            created_at=current_time,
            created_by=created_by,
            total_stages=rollout_plan.get("total_stages", 1),
            success_criteria=success_criteria,
            rollback_snapshot_id=rollback_snapshot.id,
            metadata={"total_risk_keys": len(risk_keys), "rollout_plan_type": rollout_plan.get("type", "manual")},
        )

        # Spara i databas
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO staged_rollouts 
                    (id, name, description, target_keys, rollout_plan, status, created_at, created_by,
                     started_at, completed_at, current_stage, total_stages, success_criteria, 
                     rollback_snapshot_id, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        rollout.id,
                        rollout.name,
                        rollout.description,
                        json.dumps(rollout.target_keys),
                        json.dumps(rollout.rollout_plan),
                        rollout.status.value,
                        rollout.created_at,
                        rollout.created_by,
                        rollout.started_at,
                        rollout.completed_at,
                        rollout.current_stage,
                        rollout.total_stages,
                        json.dumps(rollout.success_criteria),
                        rollout.rollback_snapshot_id,
                        json.dumps(rollout.metadata),
                    ),
                )
                conn.commit()

        logger.info(f"Created staged rollout {rollout_id} with {len(risk_keys)} risk keys")
        return rollout

    def start_staged_rollout(self, rollout_id: str) -> StagedRollout:
        """Starta staged rollout."""
        rollout = self._get_staged_rollout(rollout_id)
        if not rollout:
            raise ValueError(f"Staged rollout {rollout_id} not found")

        if rollout.status != StagedRolloutStatus.PENDING:
            raise ValueError(f"Rollout {rollout_id} is not in pending status")

        rollout.status = StagedRolloutStatus.ACTIVE
        rollout.started_at = time.time()
        rollout.current_stage = 0

        self._update_staged_rollout(rollout)
        self._active_rollouts[rollout_id] = rollout

        logger.info(f"Started staged rollout {rollout_id}")
        return rollout

    def _is_risk_key(self, key: str) -> bool:
        """Kontrollera om en nyckel är risk-relaterad."""
        risk_patterns = [
            "RISK_",
            "TRADING_",
            "MAX_",
            "LIMIT_",
            "THRESHOLD_",
            "trading_rules.",
            "risk_management.",
            "position_",
        ]

        return any(pattern in key.upper() for pattern in risk_patterns)

    def _get_staged_rollout(self, rollout_id: str) -> Optional[StagedRollout]:
        """Hämta staged rollout med ID."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, name, description, target_keys, rollout_plan, status, created_at, created_by,
                       started_at, completed_at, current_stage, total_stages, success_criteria,
                       rollback_snapshot_id, metadata
                FROM staged_rollouts WHERE id = ?
            """,
                (rollout_id,),
            )

            row = cursor.fetchone()
            if row:
                return StagedRollout.from_dict(
                    {
                        'id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'target_keys': json.loads(row[3]),
                        'rollout_plan': json.loads(row[4]),
                        'status': row[5],
                        'created_at': row[6],
                        'created_by': row[7],
                        'started_at': row[8],
                        'completed_at': row[9],
                        'current_stage': row[10],
                        'total_stages': row[11],
                        'success_criteria': json.loads(row[12]) if row[12] else {},
                        'rollback_snapshot_id': row[13],
                        'metadata': json.loads(row[14]) if row[14] else {},
                    }
                )

        return None

    def _update_staged_rollout(self, rollout: StagedRollout):
        """Uppdatera staged rollout i databas."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE staged_rollouts SET
                    status = ?, started_at = ?, completed_at = ?, current_stage = ?,
                    total_stages = ?, success_criteria = ?, rollback_snapshot_id = ?, metadata = ?
                WHERE id = ?
            """,
                (
                    rollout.status.value,
                    rollout.started_at,
                    rollout.completed_at,
                    rollout.current_stage,
                    rollout.total_stages,
                    json.dumps(rollout.success_criteria),
                    rollout.rollback_snapshot_id,
                    json.dumps(rollout.metadata),
                    rollout.id,
                ),
            )
            conn.commit()

    def _monitor_active_rollouts(self):
        """Övervaka aktiva staged rollouts."""
        with self._lock:
            for rollout_id, rollout in list(self._active_rollouts.items()):
                try:
                    if self._should_advance_stage(rollout):
                        self._advance_rollout_stage(rollout)
                    elif self._should_complete_rollout(rollout):
                        self._complete_rollout(rollout)
                except Exception as e:
                    logger.error(f"Error monitoring rollout {rollout_id}: {e}")

    def _should_advance_stage(self, rollout: StagedRollout) -> bool:
        """Kontrollera om rollout ska gå till nästa steg."""
        # Enkel logik - kan utökas med mer sofistikerade kriterier
        if rollout.current_stage >= rollout.total_stages - 1:
            return False

        # Kontrollera success criteria för aktuellt steg
        stage_duration = rollout.rollout_plan.get("stage_duration_seconds", 300)  # 5 minuter default
        time_since_stage_start = time.time() - (rollout.started_at or rollout.created_at)

        return time_since_stage_start >= stage_duration

    def _should_complete_rollout(self, rollout: StagedRollout) -> bool:
        """Kontrollera om rollout ska slutföras."""
        return rollout.current_stage >= rollout.total_stages - 1

    def _advance_rollout_stage(self, rollout: StagedRollout):
        """Gå till nästa steg i rollout."""
        rollout.current_stage += 1
        self._update_staged_rollout(rollout)

        logger.info(f"Advanced rollout {rollout.id} to stage {rollout.current_stage}")

    def _complete_rollout(self, rollout: StagedRollout):
        """Slutför rollout."""
        rollout.status = StagedRolloutStatus.COMPLETED
        rollout.completed_at = time.time()
        self._update_staged_rollout(rollout)

        # Ta bort från aktiva rollouts
        if rollout.id in self._active_rollouts:
            del self._active_rollouts[rollout.id]

        logger.info(f"Completed staged rollout {rollout.id}")

    def get_rollback_service_stats(self) -> Dict[str, Any]:
        """Hämta statistik för rollback service."""
        with sqlite3.connect(self._db_path) as conn:
            # Snapshot statistik
            cursor = conn.execute("SELECT COUNT(*) FROM snapshots")
            total_snapshots = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM rollback_operations")
            total_rollbacks = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM staged_rollouts")
            total_rollouts = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM staged_rollouts WHERE status = 'active'")
            active_rollouts = cursor.fetchone()[0]

        return {
            "total_snapshots": total_snapshots,
            "total_rollbacks": total_rollbacks,
            "total_staged_rollouts": total_rollouts,
            "active_rollouts": active_rollouts,
            "active_rollouts_in_memory": len(self._active_rollouts),
        }


# Global rollback service instans
_rollback_service: Optional[RollbackService] = None


def get_rollback_service(
    config_store: ConfigStore | None = None, config_manager: UnifiedConfigManager | None = None
) -> RollbackService:
    """Hämta global RollbackService-instans."""
    global _rollback_service
    if _rollback_service is None:
        if config_store is None:
            from services.config_store import get_config_store

            config_store = get_config_store()
        if config_manager is None:
            from services.unified_config_manager import get_unified_config_manager

            config_manager = get_unified_config_manager()

        _rollback_service = RollbackService(config_store, config_manager)

    return _rollback_service
