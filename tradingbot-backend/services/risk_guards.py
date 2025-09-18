"""
Risk Guards Service - TradingBot Backend

Denna fil innehåller RiskGuardsService med korrekt equity-hämtning från Bitfinex.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any

from config.settings import settings
from utils.logger import get_logger
import services.runtime_config as rc

logger = get_logger(__name__)


class RiskGuardsService:
    """
    Service för riskvakter som skyddar mot överdriven förlust.

    Konsoliderar:
    - Max daily loss kontroll
    - Kill switch funktionalitet
    - Exposure limits
    - Volatility guards
    """

    def __init__(self, settings_override=None):
        self.settings = settings_override or settings
        self.guards_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "risk_guards.json")
        self.guards = self._load_guards()

    def _load_guards(self) -> dict[str, Any]:
        """Ladda riskvakter från fil."""
        try:
            if os.path.exists(self.guards_file):
                with open(self.guards_file, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Kunde inte ladda riskvakter: {e}")

        # Default riskvakter
        default_guards = {
            "max_daily_loss": {
                "enabled": True,
                "percentage": 5.0,
                "triggered": False,
                "triggered_at": None,
                "daily_start_equity": 10000.0,
                "daily_start_date": None,
                "cooldown_hours": 24,
                "reason": None,
            },
            "kill_switch": {
                "enabled": True,
                "max_consecutive_losses": 3,
                "max_drawdown_percentage": 10.0,
                "triggered": False,
                "triggered_at": None,
                "cooldown_hours": 48,
                "reason": None,
            },
            "exposure_limits": {
                "enabled": True,
                "max_open_positions": 5,
                "max_position_size_percentage": 20.0,
                "max_total_exposure_percentage": 50.0,
            },
            "volatility_guards": {
                "enabled": True,
                "max_daily_volatility": 15.0,
                "pause_on_high_volatility": True,
            },
        }

        self._save_guards(default_guards)
        return default_guards

    def _save_guards(self, guards: dict[str, Any]) -> None:
        """Spara riskvakter till fil."""
        try:
            os.makedirs(os.path.dirname(self.guards_file), exist_ok=True)
            with open(self.guards_file, "w", encoding="utf-8") as f:
                json.dump(guards, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Kunde inte spara riskvakter: {e}")

    def _get_current_equity(self) -> float:
        """Hämta live equity (USD) från Bitfinex med robust timeout."""
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
                    # Om vi redan är i en event loop, skapa en ny task
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _get_equity_async())
                        return future.result(timeout=5.0)
                else:
                    # Om ingen event loop körs, kör direkt
                    return asyncio.run(_get_equity_async())
            except Exception as e:
                logger.warning(f"⚠️ Timeout eller fel vid equity-hämtning: {e}")
                return 0.0

        except Exception as e:
            logger.error(f"❌ Kunde inte hämta aktuell equity: {e}")
            return 0.0

    def _initialize_daily_tracking(self) -> None:
        """Initiera daglig spårning; nollställ daglig trigger vid ny dag."""
        today = datetime.now().date().isoformat()
        guard = self.guards["max_daily_loss"]

        if guard.get("daily_start_date") != today:
            guard["daily_start_date"] = today
            guard["daily_start_equity"] = self._get_current_equity()
            guard["triggered"] = False
            guard["triggered_at"] = None
            guard["reason"] = None
            self._save_guards(self.guards)

            logger.info(f"📅 Ny dag initialiserad: {today}")

    def check_max_daily_loss(self) -> tuple[bool, str | None]:
        """Kontrollera max daily loss."""
        try:
            if not rc.get_bool("RISK_ENABLED", getattr(self.settings, "RISK_ENABLED", True)):
                return False, None
        except Exception:
            pass

        guard = self.guards["max_daily_loss"]

        if guard.get("daily_start_equity") is not None and not guard.get("daily_start_date"):
            guard["daily_start_date"] = datetime.now().date().isoformat()
            if guard.get("triggered"):
                guard["triggered"] = False
                guard["triggered_at"] = None

        if not guard["enabled"]:
            return False, None

        self._initialize_daily_tracking()

        # Compute daily loss early och hantera cooldown
        start_equity_early = guard.get("daily_start_equity")
        daily_loss_pct_early: float | None = None
        if start_equity_early and start_equity_early > 0:
            current_equity_early = self._get_current_equity()
            daily_loss_pct_early = ((start_equity_early - current_equity_early) / start_equity_early) * 100
        # Om triggad tidigare: respektera cooldown
        if guard.get("triggered") and guard.get("triggered_at"):
            try:
                ts = datetime.fromisoformat(str(guard.get("triggered_at")))
                cooldown_h = float(guard.get("cooldown_hours", 0) or 0)
                if cooldown_h > 0 and datetime.now() < ts + timedelta(hours=cooldown_h):
                    return True, "Max daily loss överskriden – cooldown aktiv"
            except Exception:
                pass
        if daily_loss_pct_early is not None and daily_loss_pct_early < guard.get("percentage", 0):
            if guard.get("triggered"):
                guard["triggered"] = False
                guard["triggered_at"] = None
                self._save_guards(self.guards)
            return False, None

        # If above threshold, signal breach regardless of existing cooldown
        if daily_loss_pct_early is not None and daily_loss_pct_early >= guard.get("percentage", 0):
            if not guard.get("triggered"):
                guard["triggered"] = True
                guard["triggered_at"] = datetime.now().isoformat()
                guard["reason"] = "Max daily loss överskriden"
                self._save_guards(self.guards)
                logger.warning(f"🚨 Max daily loss aktiverat: {guard['reason']}")
            return True, guard["reason"]

        return False, None

    def check_kill_switch(self) -> tuple[bool, str | None]:
        """Kontrollera kill switch."""
        try:
            if not rc.get_bool("RISK_ENABLED", getattr(self.settings, "RISK_ENABLED", True)):
                return False, None
        except Exception:
            pass

        guard = self.guards["kill_switch"]
        if not guard["enabled"]:
            return False, None

        # Kontrollera drawdown
        start_equity = self.guards["max_daily_loss"].get("daily_start_equity", 10000.0)
        current_equity = self._get_current_equity()
        drawdown_pct = ((start_equity - current_equity) / start_equity) * 100

        if drawdown_pct >= guard.get("max_drawdown_percentage", 0):
            if not guard.get("triggered"):
                guard["triggered"] = True
                guard["triggered_at"] = datetime.now().isoformat()
                guard["reason"] = "Max drawdown överskriden"
                self._save_guards(self.guards)
                logger.warning(f"🚨 Kill switch aktiverat: {guard['reason']}")
            return True, guard["reason"]

        return False, None

    def check_exposure_limits(self, symbol: str, amount: float, price: float) -> tuple[bool, str | None]:
        _ = symbol  # markerar användning för lint
        """Kontrollera exposure limits."""
        try:
            if not rc.get_bool("RISK_ENABLED", getattr(self.settings, "RISK_ENABLED", True)):
                return False, None
        except Exception:
            pass

        guard = self.guards["exposure_limits"]
        if not guard["enabled"]:
            return False, None

        # Enkel kontroll - i verkligheten skulle vi kontrollera öppna positioner
        current_equity = self._get_current_equity()

        position_pct: float = 0.0
        try:
            amt = float(amount)
            prc = float(price)
            if abs(amt) <= 1.0 and current_equity > 0:
                # Fraktionsbaserad sizing: 0.1 => 10% av equity
                position_pct = abs(amt) * 100.0
            else:
                notional = abs(amt) * prc
                if current_equity > 0:
                    position_pct = (notional / current_equity) * 100.0
        except Exception:
            position_pct = 0.0

        # strikt > för block, <= är ok
        if position_pct > float(guard.get("max_position_size_percentage", 0) or 0):
            return True, "Position size för stor"

        return False, None

    def check_volatility_guards(self, symbol: str) -> tuple[bool, str | None]:
        _ = symbol  # markerar användning för lint
        """Kontrollera volatility guards."""
        try:
            if not rc.get_bool("RISK_ENABLED", getattr(self.settings, "RISK_ENABLED", True)):
                return False, None
        except Exception:
            pass

        guard = self.guards["volatility_guards"]
        if not guard["enabled"]:
            return False, None

        # Enkel kontroll - i verkligheten skulle vi beräkna volatilitet
        return False, None

    def check_all_guards(
        self,
        symbol: str | None = None,
        amount: float | None = None,
        price: float | None = None,
    ) -> tuple[bool, str | None]:
        """Kontrollera alla riskvakter."""
        try:
            # Max daily loss
            blocked, reason = self.check_max_daily_loss()
            if blocked:
                return True, reason

            # Kill switch
            blocked, reason = self.check_kill_switch()
            if blocked:
                return True, reason

            # Exposure limits
            if amount is not None and price is not None:
                blocked, reason = self.check_exposure_limits(symbol or "", amount, price)
                if blocked:
                    return True, reason

            # Volatility guards
            if symbol:
                blocked, reason = self.check_volatility_guards(symbol)
                if blocked:
                    return True, reason

            return False, None

        except Exception as e:
            logger.error(f"Fel vid kontroll av riskvakter: {e}")
            return True, f"Fel vid kontroll: {e}"

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
            logger.error(f"Kunde inte återställa riskvakt {guard_name}: {e}")
            return False

    def get_guards_status(self) -> dict[str, Any]:
        """Hämta status för alla riskvakter."""
        try:
            current_equity = self._get_current_equity()

            # Beräkna daglig förlust – skydda mot start_equity<=0 samt equity=0 (visa 0% istället för 100%)
            daily_loss_pct = 0.0
            start_equity = self.guards["max_daily_loss"].get("daily_start_equity")
            if start_equity and start_equity > 0:
                try:
                    raw = ((start_equity - current_equity) / start_equity) * 100
                    # Om equity saknas (0.0) ska vi inte visa 100% – behandla som okänd→0%
                    daily_loss_pct = 0.0 if current_equity <= 0 else raw
                except Exception:
                    daily_loss_pct = 0.0

            # Beräkna drawdown – samma skydd
            drawdown_pct = daily_loss_pct  # Förenklad – i verkligheten från peak

            status = {
                "current_equity": current_equity,
                "daily_loss_percentage": daily_loss_pct,
                "drawdown_percentage": drawdown_pct,
                "guards": self.guards.copy(),
                "last_updated": datetime.now().isoformat(),
            }

            return status
        except Exception as e:
            logger.error(f"Kunde inte hämta guards status: {e}")
            return {"error": "internal_error"}

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
            logger.error(f"Kunde inte uppdatera riskvakt {guard_name}: {e}")
            return False


# Global instans
risk_guards = RiskGuardsService()
