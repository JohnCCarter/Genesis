"""
Unified Risk Service - Enhetlig riskhantering för alla paneler.

Konsoliderar:
- RiskManager (tidsfönster, daglig trade-limit, cooldown)
- RiskGuardsService (max daily loss, kill-switch, exposure limits)
- RiskPolicyEngine (policy evaluation)
- Circuit Breaker functionality

Löser problem med:
- Duplicerad risk-logik mellan paneler
- Inkonsistenta risk-kontroller
- Svår att debugga risk-problem
- Olika refresh-intervall för risk-data
"""

from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime, timedelta
from typing import Any

from config.settings import settings, Settings
from services.performance import PerformanceService
from services.trade_constraints import TradeConstraintsService
from utils.logger import get_logger

logger = get_logger(__name__)


class RiskDecision:
    """Resultat från risk-evaluering."""

    def __init__(
        self,
        allowed: bool,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.allowed = allowed
        self.reason = reason
        self.details = details or {}


class CircuitBreakerState:
    """Circuit Breaker tillstånd."""

    def __init__(self):
        self.error_events = deque()
        self.opened_at: datetime | None = None
        self.error_threshold = 5  # Antal fel innan circuit breaker öppnas
        self.timeout_minutes = 5  # Minuter innan circuit breaker stängs


class UnifiedRiskService:
    """
    Enhetlig service för all riskhantering i systemet.

    Konsoliderar:
    - Trading windows och cooldowns
    - Dagliga trade-limits
    - Max daily loss kontroll
    - Kill-switch funktionalitet
    - Exposure limits
    - Circuit breaker
    """

    def __init__(self, settings_override: Settings | None = None):
        self.settings = settings_override or settings
        self.performance_service = PerformanceService(self.settings)
        self.trade_constraints = TradeConstraintsService(self.settings)
        self.circuit_breaker = CircuitBreakerState()

        # Risk guards konfiguration
        self.guards_file = "config/risk_guards.json"
        self.guards = self._load_guards()

        logger.info("🛡️ UnifiedRiskService initialiserad - enhetlig riskhantering")

    def _load_guards(self) -> dict[str, Any]:
        """Ladda riskvakter från fil eller skapa defaults."""
        try:
            if os.path.exists(self.guards_file):
                with open(self.guards_file) as f:
                    guards = json.load(f)
                logger.info(f"📋 Riskvakter laddade från {self.guards_file}")
                return guards
            else:
                # Skapa default guards
                default_guards = {
                    "max_daily_loss": {
                        "enabled": True,
                        "max_loss_usd": 1000.0,
                        "triggered": False,
                        "triggered_at": None,
                        "reason": None,
                    },
                    "kill_switch": {
                        "enabled": False,
                        "triggered": False,
                        "triggered_at": None,
                        "reason": None,
                    },
                    "exposure_limits": {
                        "enabled": True,
                        "max_position_size_percentage": 10.0,
                        "max_total_exposure_percentage": 50.0,
                        "triggered": False,
                        "triggered_at": None,
                        "reason": None,
                    },
                }
                self._save_guards(default_guards)
                logger.info(f"📋 Default riskvakter skapade i {self.guards_file}")
                return default_guards
        except Exception as e:
            logger.error(f"❌ Fel vid laddning av riskvakter: {e}")
            return {}

    def _save_guards(self, guards: dict[str, Any]) -> None:
        """Spara riskvakter till fil."""
        try:
            os.makedirs(os.path.dirname(self.guards_file), exist_ok=True)
            with open(self.guards_file, "w") as f:
                json.dump(guards, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Fel vid sparande av riskvakter: {e}")

    def evaluate_risk(
        self,
        symbol: str | None = None,
        amount: float | None = None,
        price: float | None = None,
    ) -> RiskDecision:
        """
        Utför komplett risk-evaluering för en trade.

        Args:
            symbol: Trading symbol
            amount: Position amount
            price: Entry price

        Returns:
            RiskDecision med resultat
        """
        try:
            # 1. Kontrollera circuit breaker
            if self._is_circuit_breaker_open():
                return RiskDecision(
                    False,
                    "circuit_breaker_open",
                    {
                        "opened_at": (
                            self.circuit_breaker.opened_at.isoformat() if self.circuit_breaker.opened_at else None
                        )
                    },
                )

            # 2. Kontrollera max daily loss
            blocked, reason = self._check_max_daily_loss()
            if blocked:
                return RiskDecision(False, f"max_daily_loss:{reason}")

            # 3. Kontrollera kill-switch
            blocked, reason = self._check_kill_switch()
            if blocked:
                return RiskDecision(False, f"kill_switch:{reason}")

            # 4. Kontrollera exposure limits
            if symbol and amount and price:
                blocked, reason = self._check_exposure_limits(symbol, amount, price)
                if blocked:
                    return RiskDecision(False, f"exposure_limits:{reason}")

            # 5. Kontrollera trade constraints (trading windows, cooldowns, limits)
            constraint_result = self.trade_constraints.check(symbol=symbol)
            if not constraint_result.allowed:
                return RiskDecision(
                    False,
                    f"trade_constraints:{constraint_result.reason}",
                    constraint_result.details,
                )

            return RiskDecision(True)

        except Exception as e:
            logger.error(f"❌ Fel vid risk-evaluering: {e}", exc_info=True)
            return RiskDecision(False, "evaluation_error")

    def record_trade(self, symbol: str | None = None) -> None:
        """Registrera en genomförd trade."""
        try:
            self.trade_constraints.record_trade(symbol=symbol)
            logger.debug(f"📊 Trade registrerad för {symbol or 'unknown'}")
        except Exception as e:
            logger.error(f"❌ Fel vid registrering av trade: {e}")

    def record_error(self) -> None:
        """Registrera ett fel för circuit breaker."""
        try:
            now = datetime.now()
            self.circuit_breaker.error_events.append(now)

            # Behåll endast fel från senaste timmen
            cutoff = now - timedelta(hours=1)
            while self.circuit_breaker.error_events and self.circuit_breaker.error_events[0] < cutoff:
                self.circuit_breaker.error_events.popleft()

            # Kontrollera om circuit breaker ska öppnas
            if len(self.circuit_breaker.error_events) >= self.circuit_breaker.error_threshold:
                if not self.circuit_breaker.opened_at:
                    self.circuit_breaker.opened_at = now
                    logger.warning(f"🚨 Circuit breaker öppnad efter {len(self.circuit_breaker.error_events)} fel")

            logger.debug(f"📊 Fel registrerat. Totalt: {len(self.circuit_breaker.error_events)}")
        except Exception as e:
            logger.error(f"❌ Fel vid registrering av error: {e}")

    def _is_circuit_breaker_open(self) -> bool:
        """Kontrollera om circuit breaker är öppen."""
        if not self.circuit_breaker.opened_at:
            return False

        # Stäng circuit breaker efter timeout
        timeout = timedelta(minutes=self.circuit_breaker.timeout_minutes)
        if datetime.now() - self.circuit_breaker.opened_at > timeout:
            self.circuit_breaker.opened_at = None
            logger.info("✅ Circuit breaker stängd efter timeout")
            return False

        return True

    def _check_max_daily_loss(self) -> tuple[bool, str | None]:
        """Kontrollera max daily loss."""
        try:
            guard = self.guards.get("max_daily_loss", {})
            if not guard.get("enabled", False):
                return False, None

            if guard.get("triggered", False):
                return (
                    True,
                    f"Max daily loss redan triggad: {guard.get('reason', 'Okänd anledning')}",
                )

            # Hämta dagens PnL
            daily_pnl = self._get_daily_pnl()
            max_loss = guard.get("max_loss_usd", 1000.0)

            if daily_pnl <= -max_loss:
                # Trigga max daily loss
                guard["triggered"] = True
                guard["triggered_at"] = datetime.now().isoformat()
                guard["reason"] = f"Daglig förlust {daily_pnl:.2f} USD överstiger limit {max_loss:.2f} USD"
                self._save_guards(self.guards)

                logger.warning(f"🚨 Max daily loss triggad: {guard['reason']}")
                return True, guard["reason"]

            return False, None

        except Exception as e:
            logger.error(f"❌ Fel vid kontroll av max daily loss: {e}")
            return True, f"Fel vid kontroll: {e!s}"

    def _check_kill_switch(self) -> tuple[bool, str | None]:
        """Kontrollera kill-switch."""
        try:
            guard = self.guards.get("kill_switch", {})
            if not guard.get("enabled", False):
                return False, None

            if guard.get("triggered", False):
                return (
                    True,
                    f"Kill-switch aktiv: {guard.get('reason', 'Okänd anledning')}",
                )

            return False, None

        except Exception as e:
            logger.error(f"❌ Fel vid kontroll av kill-switch: {e}")
            return True, f"Fel vid kontroll: {e!s}"

    def _check_exposure_limits(self, symbol: str, amount: float, price: float) -> tuple[bool, str | None]:
        """Kontrollera exposure limits."""
        try:
            _ = symbol  # parameter finns för framtida användning (etiketter/limits per symbol)
            guard = self.guards.get("exposure_limits", {})
            if not guard.get("enabled", False):
                return False, None

            if guard.get("triggered", False):
                return (
                    True,
                    f"Exposure limits redan triggade: {guard.get('reason', 'Okänd anledning')}",
                )

            # Hämta aktuell equity
            equity = self._get_current_equity()
            if equity <= 0:
                return True, "Kan inte kontrollera exposure - ingen equity data"

            # Beräkna position value
            position_value = abs(amount * price)
            position_percentage = (position_value / equity) * 100

            max_position_percentage = guard.get("max_position_size_percentage", 10.0)

            if position_percentage > max_position_percentage:
                reason = f"Position {position_percentage:.1f}% överstiger limit {max_position_percentage}%"
                guard["triggered"] = True
                guard["triggered_at"] = datetime.now().isoformat()
                guard["reason"] = reason
                self._save_guards(self.guards)

                logger.warning(f"🚨 Exposure limit triggad: {reason}")
                return True, reason

            return False, None

        except Exception as e:
            logger.error(f"❌ Fel vid kontroll av exposure limits: {e}")
            return True, f"Fel vid kontroll: {e!s}"

    def _get_daily_pnl(self) -> float:
        """Hämta dagens PnL."""
        try:
            # Enkel fallback - returnera 0 för att undvika hängningar
            # I en riktig implementation skulle vi använda PerformanceService
            logger.debug("⚠️ Daily PnL computation disabled to prevent hanging")
            return 0.0
        except Exception as e:
            logger.error(f"❌ Kunde inte hämta dagens PnL: {e}")
            return 0.0

    def _get_current_equity(self) -> float:
        """Hämta aktuell equity från Bitfinex."""
        try:
            import asyncio
            from services.performance import PerformanceService

            # Använd PerformanceService för att hämta verklig equity
            async def _get_equity_async():
                try:
                    perf_service = PerformanceService()
                    equity_data = await perf_service.compute_current_equity()
                    return equity_data.get("total_usd", 0.0)
                except Exception as e:
                    logger.warning(f"⚠️ Kunde inte hämta equity från PerformanceService: {e}")
                    return 0.0

            # Kör async funktion med timeout
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _get_equity_async())
                        return future.result(timeout=5.0)
                else:
                    return asyncio.run(_get_equity_async())
            except Exception as e:
                logger.warning(f"⚠️ Timeout eller fel vid equity-hämtning: {e}")
                return 0.0

        except Exception as e:
            logger.error(f"❌ Kunde inte hämta aktuell equity: {e}")
            return 0.0

    def reset_guard(self, guard_name: str) -> bool:
        """Återställ en specifik riskvakt."""
        try:
            if guard_name in self.guards:
                guard = self.guards[guard_name]
                guard["triggered"] = False
                guard["triggered_at"] = None
                guard["reason"] = None
                self._save_guards(self.guards)
                logger.info(f"🔄 Riskvakt återställd: {guard_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Kunde inte återställa riskvakt {guard_name}: {e}")
            return False

    def reset_circuit_breaker(self) -> bool:
        """Återställ circuit breaker."""
        try:
            self.circuit_breaker.opened_at = None
            self.circuit_breaker.error_events.clear()
            logger.info("🔄 Circuit breaker återställd")
            return True
        except Exception as e:
            logger.error(f"❌ Kunde inte återställa circuit breaker: {e}")
            return False

    def get_risk_status(self) -> dict[str, Any]:
        """Hämta komplett risk-status."""
        try:
            # Hämta trade constraints status
            constraints_status = self.trade_constraints.status()

            # Hämta circuit breaker status
            circuit_breaker_status = {
                "open": self._is_circuit_breaker_open(),
                "opened_at": (self.circuit_breaker.opened_at.isoformat() if self.circuit_breaker.opened_at else None),
                "error_count": len(self.circuit_breaker.error_events),
                "error_threshold": self.circuit_breaker.error_threshold,
            }

            # Hämta guards status från RiskGuardsService för komplett data
            try:
                from services.risk_guards import risk_guards

                guards_full_status = risk_guards.get_guards_status()

                # Extrahera equity och loss data
                current_equity = guards_full_status.get("current_equity", 0)
                daily_loss_percentage = guards_full_status.get("daily_loss_percentage", 0)
                drawdown_percentage = guards_full_status.get("drawdown_percentage", 0)
                guards_full_data = guards_full_status.get("guards", {})

            except Exception as e:
                logger.warning(f"⚠️ Kunde inte hämta full guards status: {e}")
                current_equity = 0
                daily_loss_percentage = 0
                drawdown_percentage = 0
                guards_full_data = {}

            # Hämta guards status (enkel version)
            guards_status = {}
            for guard_name, guard_data in self.guards.items():
                guards_status[guard_name] = {
                    "enabled": guard_data.get("enabled", False),
                    "triggered": guard_data.get("triggered", False),
                    "triggered_at": guard_data.get("triggered_at"),
                    "reason": guard_data.get("reason"),
                }

            return {
                "timestamp": datetime.now().isoformat(),
                "current_equity": current_equity,
                "daily_loss_percentage": daily_loss_percentage,
                "drawdown_percentage": drawdown_percentage,
                "trade_constraints": constraints_status,
                "circuit_breaker": circuit_breaker_status,
                "guards": guards_status,
                "guards_full": guards_full_data,  # Komplett guards data
                "overall_status": ("healthy" if not self._is_circuit_breaker_open() else "degraded"),
            }

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av risk-status: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
        alert-autofix-58
                "error": "Internal server error",
        main
                "overall_status": "error",
            }

    def update_guard_config(self, guard_name: str, config: dict[str, Any]) -> bool:
        """Uppdatera konfiguration för en riskvakt."""
        try:
            if guard_name in self.guards:
                self.guards[guard_name].update(config)
                self._save_guards(self.guards)
                logger.info(f"📝 Riskvakt konfiguration uppdaterad: {guard_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Fel vid uppdatering av riskvakt konfiguration: {e}")
            return False


# Global instans för enhetlig åtkomst
unified_risk_service = UnifiedRiskService(settings)
