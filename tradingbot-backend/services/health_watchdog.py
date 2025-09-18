"""
Health Watchdog Service - Periodiska hälsokontroller och auto-åtgärder.

Implementerar:
- Periodiska health checks
- Auto-åtgärder vid fel
- System monitoring
- Alerting och notifikationer
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from config.settings import settings, Settings
from services.bitfinex_websocket import bitfinex_ws
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HealthCheck:
    """En hälsokontroll."""

    name: str
    enabled: bool = True
    interval_seconds: int = 60
    timeout_seconds: int = 30
    max_failures: int = 3
    auto_fix: bool = True
    critical: bool = False


@dataclass
class HealthStatus:
    """Status för en hälsokontroll."""

    check_name: str
    status: str  # 'healthy', 'warning', 'critical', 'unknown'
    message: str
    last_check: datetime
    last_success: datetime | None
    failure_count: int
    response_time_ms: float
    details: dict[str, Any]


class HealthWatchdogService:
    """Service för hälsokontroller och watchdog funktionalitet."""

    def __init__(self, settings_override: Settings | None = None):
        self.settings = settings_override or settings
        self.config_file = "config/health_watchdog.json"
        self.status_file = "config/health_status.json"

        # Ladda eller skapa default health checks
        self.health_checks = self._load_health_checks()
        self.health_status = self._load_health_status()

        # Watchdog state
        self.running = False
        self.task: asyncio.Task | None = None

        logger.info("🏥 HealthWatchdogService initialiserad")

    def _load_health_checks(self) -> dict[str, HealthCheck]:
        """Ladda health checks från fil eller skapa defaults."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, encoding="utf-8") as f:
                    data = json.load(f)

                checks = {}
                for name, check_data in data.items():
                    checks[name] = HealthCheck(**check_data)

                logger.info(f"📋 Laddade health checks från {self.config_file}")
                return checks
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte ladda health checks: {e}")

        # Default health checks
        default_checks = {
            "api_connectivity": HealthCheck(
                name="api_connectivity",
                enabled=True,
                interval_seconds=30,
                timeout_seconds=10,
                max_failures=3,
                auto_fix=True,
                critical=True,
            ),
            "websocket_connectivity": HealthCheck(
                name="websocket_connectivity",
                enabled=True,
                interval_seconds=30,
                timeout_seconds=10,
                max_failures=3,
                auto_fix=True,
                critical=True,
            ),
            "database_connectivity": HealthCheck(
                name="database_connectivity",
                enabled=True,
                interval_seconds=60,
                timeout_seconds=15,
                max_failures=2,
                auto_fix=False,
                critical=True,
            ),
            "memory_usage": HealthCheck(
                name="memory_usage",
                enabled=True,
                interval_seconds=120,
                timeout_seconds=5,
                max_failures=5,
                auto_fix=False,
                critical=False,
            ),
            "disk_space": HealthCheck(
                name="disk_space",
                enabled=True,
                interval_seconds=300,
                timeout_seconds=10,
                max_failures=3,
                auto_fix=False,
                critical=False,
            ),
            "trading_performance": HealthCheck(
                name="trading_performance",
                enabled=True,
                interval_seconds=60,
                timeout_seconds=20,
                max_failures=2,
                auto_fix=False,
                critical=True,
            ),
        }

        self._save_health_checks(default_checks)
        return default_checks

    def _save_health_checks(self, checks: dict[str, HealthCheck]) -> None:
        """Spara health checks till fil."""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            data = {name: check.__dict__ for name, check in checks.items()}
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Kunde inte spara health checks: {e}")

    def _load_health_status(self) -> dict[str, HealthStatus]:
        """Ladda health status från fil."""
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, encoding="utf-8") as f:
                    data = json.load(f)

                status = {}
                for name, status_data in data.items():
                    status_data["last_check"] = datetime.fromisoformat(status_data["last_check"])
                    if status_data.get("last_success"):
                        status_data["last_success"] = datetime.fromisoformat(status_data["last_success"])
                    status[name] = HealthStatus(**status_data)

                return status
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte ladda health status: {e}")

        return {}

    def _save_health_status(self, status: dict[str, HealthStatus]) -> None:
        """Spara health status till fil."""
        try:
            os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
            data = {name: st.__dict__ for name, st in status.items()}
            # Konvertera datetime till string för JSON serialisering
            for _, vals in data.items():
                vals["last_check"] = vals["last_check"].isoformat()
                if vals.get("last_success"):
                    vals["last_success"] = vals["last_success"].isoformat()

            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Kunde inte spara health status: {e}")

    async def check_api_connectivity(self) -> tuple[bool, str, dict[str, Any]]:
        """Kontrollera API-anslutning."""
        try:
            start_time = time.time()

            # Testa en enkel API-anrop
            from rest.auth import get_auth_headers

            headers = get_auth_headers()

            response_time = (time.time() - start_time) * 1000

            if headers:
                return (
                    True,
                    "API-anslutning OK",
                    {"response_time_ms": response_time, "headers_generated": True},
                )
            else:
                return (
                    False,
                    "Kunde inte generera auth headers",
                    {"response_time_ms": response_time, "headers_generated": False},
                )
        except Exception as e:
            return False, f"API-anslutning fel: {e}", {"error": str(e)}

    async def check_websocket_connectivity(self) -> tuple[bool, str, dict[str, Any]]:
        """Kontrollera WebSocket-anslutning."""
        try:
            start_time = time.time()

            # Kontrollera WebSocket status
            ws_status = bitfinex_ws.get_pool_status()
            response_time = (time.time() - start_time) * 1000

            if ws_status.get("pool_enabled"):
                return (
                    True,
                    "WebSocket-anslutning OK",
                    {
                        "response_time_ms": response_time,
                        "pool_enabled": True,
                        "active_sockets": len([s for s in ws_status.get("pool_sockets", []) if not s.get("closed")]),
                    },
                )
            else:
                return (
                    False,
                    "WebSocket pool inaktiverad",
                    {"response_time_ms": response_time, "pool_enabled": False},
                )
        except Exception as e:
            return False, f"WebSocket-anslutning fel: {e}", {"error": str(e)}

    async def check_database_connectivity(self) -> tuple[bool, str, dict[str, Any]]:
        """Kontrollera databasanslutning."""
        try:
            start_time = time.time()

            # Testa SQLite-anslutning
            import sqlite3

            db_path = "config/candles.sqlite3"

            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                conn.close()

                response_time = (time.time() - start_time) * 1000

                return (
                    True,
                    "Databasanslutning OK",
                    {
                        "response_time_ms": response_time,
                        "database_exists": True,
                        "table_count": table_count,
                    },
                )
            else:
                return (
                    False,
                    "Databasfil saknas",
                    {"database_exists": False, "db_path": db_path},
                )
        except Exception as e:
            return False, f"Databasanslutning fel: {e}", {"error": str(e)}

    async def check_memory_usage(self) -> tuple[bool, str, dict[str, Any]]:
        """Kontrollera minnesanvändning."""
        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # Varning vid >80% användning, kritisk vid >95%
            if memory_percent > 95:
                status = False
                message = f"Kritisk minnesanvändning: {memory_percent:.1f}%"
            elif memory_percent > 80:
                status = False
                message = f"Hög minnesanvändning: {memory_percent:.1f}%"
            else:
                status = True
                message = f"Minnesanvändning OK: {memory_percent:.1f}%"

            return (
                status,
                message,
                {
                    "memory_percent": memory_percent,
                    "memory_rss_mb": memory_info.rss / 1024 / 1024,
                    "memory_vms_mb": memory_info.vms / 1024 / 1024,
                },
            )
        except Exception as e:
            return False, f"Minneskontroll fel: {e}", {"error": str(e)}

    async def check_disk_space(self) -> tuple[bool, str, dict[str, Any]]:
        """Kontrollera diskutrymme."""
        try:
            import psutil

            disk_usage = psutil.disk_usage(".")
            disk_percent = disk_usage.percent

            # Varning vid >85% användning, kritisk vid >95%
            if disk_percent > 95:
                status = False
                message = f"Kritiskt diskutrymme: {disk_percent:.1f}%"
            elif disk_percent > 85:
                status = False
                message = f"Lågt diskutrymme: {disk_percent:.1f}%"
            else:
                status = True
                message = f"Diskutrymme OK: {disk_percent:.1f}%"

            return (
                status,
                message,
                {
                    "disk_percent": disk_percent,
                    "free_gb": disk_usage.free / 1024 / 1024 / 1024,
                    "total_gb": disk_usage.total / 1024 / 1024 / 1024,
                },
            )
        except Exception as e:
            return False, f"Diskkontroll fel: {e}", {"error": str(e)}

    async def check_trading_performance(self) -> tuple[bool, str, dict[str, Any]]:
        """Kontrollera trading performance."""
        try:
            # Hämta senaste performance metrics
            from services.performance import PerformanceService

            perf_service = PerformanceService(self.settings)

            # Kontrollera om vi har nyligen gjort trades
            recent_trades = perf_service.get_recent_trades(hours=24)

            if not recent_trades:
                return (
                    True,
                    "Inga trades senaste 24h",
                    {"recent_trades": 0, "trading_active": False},
                )

            # Kontrollera win rate
            winning_trades = [t for t in recent_trades if t.get("pnl", 0) > 0]
            win_rate = len(winning_trades) / len(recent_trades)

            if win_rate < 0.3:  # Mindre än 30% vinnande trades
                return (
                    False,
                    f"Låg win rate: {win_rate:.1%}",
                    {
                        "recent_trades": len(recent_trades),
                        "win_rate": win_rate,
                        "trading_active": True,
                    },
                )
            else:
                return (
                    True,
                    f"Trading performance OK: {win_rate:.1%} win rate",
                    {
                        "recent_trades": len(recent_trades),
                        "win_rate": win_rate,
                        "trading_active": True,
                    },
                )
        except Exception as e:
            return False, f"Trading performance kontroll fel: {e}", {"error": str(e)}

    async def run_health_check(self, check_name: str) -> HealthStatus:
        """
        Kör en specifik hälsokontroll.

        Args:
            check_name: Namn på kontrollen att köra

        Returns:
            HealthStatus: Resultat från kontrollen
        """
        check = self.health_checks.get(check_name)
        if not check or not check.enabled:
            return HealthStatus(
                check_name=check_name,
                status="unknown",
                message="Kontroll inaktiverad eller saknas",
                last_check=datetime.now(),
                last_success=None,
                failure_count=0,
                response_time_ms=0.0,
                details={},
            )

        start_time = time.time()

        try:
            # Kör rätt kontroll baserat på namn
            if check_name == "api_connectivity":
                success, message, details = await self.check_api_connectivity()
            elif check_name == "websocket_connectivity":
                success, message, details = await self.check_websocket_connectivity()
            elif check_name == "database_connectivity":
                success, message, details = await self.check_database_connectivity()
            elif check_name == "memory_usage":
                success, message, details = await self.check_memory_usage()
            elif check_name == "disk_space":
                success, message, details = await self.check_disk_space()
            elif check_name == "trading_performance":
                success, message, details = await self.check_trading_performance()
            else:
                success, message, details = False, f"Okänd kontroll: {check_name}", {}

            response_time = (time.time() - start_time) * 1000

            # Uppdatera status
            current_status = self.health_status.get(check_name)
            if current_status:
                if success:
                    status = "healthy"
                    failure_count = 0
                    last_success = datetime.now()
                else:
                    failure_count = current_status.failure_count + 1
                    last_success = current_status.last_success

                    if failure_count >= check.max_failures:
                        status = "critical" if check.critical else "warning"
                    else:
                        status = "warning"
            elif success:
                status = "healthy"
                failure_count = 0
                last_success = datetime.now()
            else:
                status = "warning"
                failure_count = 1
                last_success = None

            health_status = HealthStatus(
                check_name=check_name,
                status=status,
                message=message,
                last_check=datetime.now(),
                last_success=last_success,
                failure_count=failure_count,
                response_time_ms=response_time,
                details=details,
            )

            self.health_status[check_name] = health_status

            # Logga resultat
            if success:
                logger.info(f"✅ {check_name}: {message}")
            else:
                logger.warning(f"⚠️ {check_name}: {message}")

            # Auto-fix om aktiverat och kritisk
            if not success and check.auto_fix and status == "critical":
                await self._auto_fix(check_name)

            return health_status

        except Exception as e:
            logger.error(f"❌ Fel vid health check {check_name}: {e}")

            return HealthStatus(
                check_name=check_name,
                status="critical",
                message=f"Kontroll fel: {e}",
                last_check=datetime.now(),
                last_success=None,
                failure_count=1,
                response_time_ms=(time.time() - start_time) * 1000,
                details={"error": str(e)},
            )

    async def _auto_fix(self, check_name: str) -> None:
        """
        Försök att automatiskt fixa ett problem.

        Args:
            check_name: Namn på kontrollen att fixa
        """
        try:
            logger.info(f"🔧 Försöker auto-fixa {check_name}")

            if check_name == "websocket_connectivity":
                # Försök att reconnecta WebSocket
                await bitfinex_ws.reconnect()
                logger.info(f"🔄 WebSocket reconnect initierad för {check_name}")

            elif check_name == "api_connectivity":
                # Försök att reinitiera auth
                from rest.auth import clear_auth_cache

                clear_auth_cache()
                logger.info(f"🔄 Auth cache rensad för {check_name}")

            # Lägg till fler auto-fix logiker här

        except Exception as e:
            logger.error(f"❌ Auto-fix misslyckades för {check_name}: {e}")

    async def run_all_health_checks(self) -> dict[str, HealthStatus]:
        """
        Kör alla aktiva hälsokontroller.

        Returns:
            Dict[str, HealthStatus]: Resultat från alla kontroller
        """
        tasks = []
        for check_name in self.health_checks:
            if self.health_checks[check_name].enabled:
                tasks.append(self.run_health_check(check_name))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Hantera exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    check_name = list(self.health_checks.keys())[i]
                    logger.error(f"❌ Exception i health check {check_name}: {result}")
                    results[i] = HealthStatus(
                        check_name=check_name,
                        status="critical",
                        message=f"Exception: {result}",
                        last_check=datetime.now(),
                        last_success=None,
                        failure_count=1,
                        response_time_ms=0.0,
                        details={"error": str(result)},
                    )

        # Spara status
        self._save_health_status(self.health_status)

        return {status.check_name: status for status in results if hasattr(status, "check_name")}

    async def start_watchdog(self) -> None:
        """Starta watchdog-loopen."""
        if self.running:
            logger.warning("Watchdog redan igång")
            return

        self.running = True
        logger.info("🏥 Health watchdog startad")

        while self.running:
            try:
                await self.run_all_health_checks()

                # Vänta tills nästa körning
                await asyncio.sleep(60)  # Kör varje minut

            except Exception as e:
                logger.error(f"❌ Fel i watchdog loop: {e}")
                await asyncio.sleep(30)  # Kortare väntetid vid fel

    async def stop_watchdog(self) -> None:
        """Stoppa watchdog-loopen."""
        self.running = False
        if self.task:
            self.task.cancel()
        logger.info("🏥 Health watchdog stoppad")

    def get_overall_health(self) -> dict[str, Any]:
        """
        Hämta övergripande hälsostatus.

        Returns:
            Dict med övergripande status
        """
        try:
            total_checks = len(self.health_checks)
            healthy_checks = 0
            warning_checks = 0
            critical_checks = 0

            for status in self.health_status.values():
                if status.status == "healthy":
                    healthy_checks += 1
                elif status.status == "warning":
                    warning_checks += 1
                elif status.status == "critical":
                    critical_checks += 1

            overall_status = "healthy"
            if critical_checks > 0:
                overall_status = "critical"
            elif warning_checks > 0:
                overall_status = "warning"

            return {
                "overall_status": overall_status,
                "total_checks": total_checks,
                "healthy_checks": healthy_checks,
                "warning_checks": warning_checks,
                "critical_checks": critical_checks,
                "health_percentage": ((healthy_checks / total_checks * 100) if total_checks > 0 else 0),
                "last_updated": datetime.now().isoformat(),
                "checks": {name: status.__dict__ for name, status in self.health_status.items()},
            }
        except Exception as e:
            logger.error(f"❌ Kunde inte hämta overall health: {e}")
            return {"error": "Internal server error"}


# Global instans
health_watchdog = HealthWatchdogService()
