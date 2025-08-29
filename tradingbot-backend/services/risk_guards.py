"""
Risk Guards Service - Globala riskvakter för tradingboten.

Implementerar:
- Max Daily Loss kontroll
- Kill-Switch funktionalitet
- Cooldown-period efter trigger
- Dashboard-visning av riskvakter
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from utils.logger import get_logger

from config.settings import Settings
from services.performance import PerformanceService

logger = get_logger(__name__)


class RiskGuardsService:
    """Service för globala riskvakter och kill-switch funktionalitet."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.guards_file = "config/risk_guards.json"
        self.performance_service = PerformanceService(self.settings)

        # Ladda eller skapa default guards
        self.guards = self._load_guards()

        logger.info("🛡️ RiskGuardsService initialiserad")

    def _load_guards(self) -> dict[str, Any]:
        """Ladda riskvakter från fil eller skapa defaults."""
        try:
            if os.path.exists(self.guards_file):
                with open(self.guards_file, encoding="utf-8") as f:
                    guards = json.load(f)
                logger.info(f"📋 Laddade riskvakter från {self.guards_file}")
                return guards
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte ladda riskvakter: {e}")

        # Default guards
        default_guards = {
            "max_daily_loss": {
                "enabled": True,
                "percentage": 5.0,  # 5% max daglig förlust
                "triggered": False,
                "triggered_at": None,
                "daily_start_equity": None,
                "cooldown_hours": 24,  # 24 timmar cooldown
            },
            "kill_switch": {
                "enabled": True,
                "max_consecutive_losses": 3,
                "max_drawdown_percentage": 10.0,  # 10% max drawdown
                "triggered": False,
                "triggered_at": None,
                "reason": None,
                "cooldown_hours": 48,  # 48 timmar cooldown
            },
            "exposure_limits": {
                "enabled": True,
                "max_open_positions": 5,
                "max_position_size_percentage": 20.0,  # 20% per position
                "max_total_exposure_percentage": 50.0,  # 50% total exposure
            },
            "volatility_guards": {
                "enabled": True,
                "max_daily_volatility": 15.0,  # 15% daglig volatilitet
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
            logger.error(f"❌ Kunde inte spara riskvakter: {e}")

    def _get_current_equity(self) -> float:
        """Hämta aktuell equity från performance service."""
        try:
            # Använd performance service för att beräkna aktuell equity
            # Detta är en förenklad implementation - i verkligheten skulle vi
            # använda PerformanceService för att beräkna total equity
            return 10000.0  # Placeholder - ersätt med riktig equity-beräkning
        except Exception as e:
            logger.error(f"❌ Kunde inte hämta aktuell equity: {e}")
            return 0.0

    def _initialize_daily_tracking(self) -> None:
        """Initiera daglig spårning om det är ny dag."""
        today = datetime.now().date()
        daily_start = self.guards["max_daily_loss"].get("daily_start_date")

        if daily_start != today.isoformat():
            self.guards["max_daily_loss"]["daily_start_date"] = today.isoformat()
            self.guards["max_daily_loss"]["daily_start_equity"] = self._get_current_equity()
            self.guards["max_daily_loss"]["triggered"] = False
            self.guards["max_daily_loss"]["triggered_at"] = None
            self._save_guards(self.guards)
            logger.info(f"📅 Ny dag initialiserad: {today}")

    def check_max_daily_loss(self) -> tuple[bool, str | None]:
        """
        Kontrollera max daily loss.

        Returns:
            Tuple[bool, Optional[str]]: (blocked, reason)
        """
        guard = self.guards["max_daily_loss"]

        if not guard["enabled"]:
            return False, None

        self._initialize_daily_tracking()

        # Kontrollera cooldown
        if guard["triggered"] and guard["triggered_at"]:
            try:
                triggered_time = datetime.fromisoformat(guard["triggered_at"])
                cooldown_end = triggered_time + timedelta(hours=guard["cooldown_hours"])

                if datetime.now() < cooldown_end:
                    remaining = cooldown_end - datetime.now()
                    return True, f"Max daily loss cooldown aktiv: {remaining.seconds // 3600}h kvar"
            except Exception:
                pass

        # Kontrollera daglig förlust
        start_equity = guard.get("daily_start_equity")
        if start_equity and start_equity > 0:
            current_equity = self._get_current_equity()
            daily_loss_pct = ((start_equity - current_equity) / start_equity) * 100

            if daily_loss_pct >= guard["percentage"]:
                if not guard["triggered"]:
                    guard["triggered"] = True
                    guard["triggered_at"] = datetime.now().isoformat()
                    self._save_guards(self.guards)
                    logger.warning(f"🚨 Max daily loss triggad: {daily_loss_pct:.2f}% förlust")

                return True, f"Max daily loss överskriden: {daily_loss_pct:.2f}%"

        return False, None

    def check_kill_switch(self) -> tuple[bool, str | None]:
        """
        Kontrollera kill-switch villkor.

        Returns:
            Tuple[bool, Optional[str]]: (blocked, reason)
        """
        guard = self.guards["kill_switch"]

        if not guard["enabled"]:
            return False, None

        # Kontrollera cooldown
        if guard["triggered"] and guard["triggered_at"]:
            try:
                triggered_time = datetime.fromisoformat(guard["triggered_at"])
                cooldown_end = triggered_time + timedelta(hours=guard["cooldown_hours"])

                if datetime.now() < cooldown_end:
                    remaining = cooldown_end - datetime.now()
                    return True, f"Kill-switch cooldown aktiv: {remaining.seconds // 3600}h kvar"
            except Exception:
                pass

        # Kontrollera drawdown
        start_equity = self.guards["max_daily_loss"].get("daily_start_equity")
        if start_equity and start_equity > 0:
            current_equity = self._get_current_equity()
            drawdown_pct = ((start_equity - current_equity) / start_equity) * 100

            if drawdown_pct >= guard["max_drawdown_percentage"]:
                if not guard["triggered"]:
                    guard["triggered"] = True
                    guard["triggered_at"] = datetime.now().isoformat()
                    guard["reason"] = f"Max drawdown överskriden: {drawdown_pct:.2f}%"
                    self._save_guards(self.guards)
                    logger.error(f"🚨 Kill-switch triggad: {guard['reason']}")

                return True, guard["reason"]

        return False, None

    def check_exposure_limits(self, symbol: str, amount: float, price: float) -> tuple[bool, str | None]:
        """
        Kontrollera exposure limits för en ny position.

        Args:
            symbol: Trading symbol
            amount: Position amount
            price: Entry price

        Returns:
            Tuple[bool, Optional[str]]: (blocked, reason)
        """
        guard = self.guards["exposure_limits"]

        if not guard["enabled"]:
            return False, None

        # Här skulle vi implementera kontroll av:
        # - Antal öppna positioner
        # - Position size vs total equity
        # - Total exposure vs total equity

        # Beräkna positionens storlek som procent av equity.
        # Tolkning:
        # - Om |amount| <= 1.0: behandla amount som andel av equity (t.ex. 0.1 = 10% av equity)
        # - Annars: använd notional = |amount| * price
        current_equity = self._get_current_equity()
        position_pct: float = 0.0
        try:
            if abs(float(amount)) <= 1.0 and current_equity > 0:
                # Fraktionsbaserad sizing – direkt procent av equity
                position_pct = abs(float(amount)) * 100.0
            else:
                notional = abs(float(amount)) * float(price)
                if current_equity > 0:
                    position_pct = (notional / current_equity) * 100.0
        except Exception:
            position_pct = 0.0

        if position_pct > guard["max_position_size_percentage"]:
            return True, (f"Position size för stor: {position_pct:.2f}% > {guard['max_position_size_percentage']}%")

        return False, None

    def check_all_guards(
        self, symbol: str = None, amount: float = None, price: float = None
    ) -> tuple[bool, str | None]:
        """
        Kontrollera alla riskvakter.

        Args:
            symbol: Trading symbol (för exposure checks)
            amount: Position amount (för exposure checks)
            price: Entry price (för exposure checks)

        Returns:
            Tuple[bool, Optional[str]]: (blocked, reason)
        """
        # Kontrollera max daily loss
        blocked, reason = self.check_max_daily_loss()
        if blocked:
            return True, reason

        # Kontrollera kill-switch
        blocked, reason = self.check_kill_switch()
        if blocked:
            return True, reason

        # Kontrollera exposure limits om data finns
        if symbol and amount and price:
            blocked, reason = self.check_exposure_limits(symbol, amount, price)
            if blocked:
                return True, reason

        return False, None

    def reset_guard(self, guard_name: str) -> bool:
        """
        Återställ en specifik riskvakt.

        Args:
            guard_name: Namn på riskvakten att återställa

        Returns:
            bool: True om återställning lyckades
        """
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

    def get_guards_status(self) -> dict[str, Any]:
        """
        Hämta status för alla riskvakter.

        Returns:
            Dict med status för alla guards
        """
        try:
            current_equity = self._get_current_equity()

            # Beräkna daglig förlust
            daily_loss_pct = 0.0
            start_equity = self.guards["max_daily_loss"].get("daily_start_equity")
            if start_equity and start_equity > 0:
                daily_loss_pct = ((start_equity - current_equity) / start_equity) * 100

            # Beräkna drawdown
            drawdown_pct = daily_loss_pct  # Förenklad - i verkligheten skulle detta vara från peak

            status = {
                "current_equity": current_equity,
                "daily_loss_percentage": daily_loss_pct,
                "drawdown_percentage": drawdown_pct,
                "guards": self.guards.copy(),
                "last_updated": datetime.now().isoformat(),
            }

            return status
        except Exception as e:
            logger.error(f"❌ Kunde inte hämta guards status: {e}")
            return {"error": str(e)}

    def update_guard_config(self, guard_name: str, config: dict[str, Any]) -> bool:
        """
        Uppdatera konfiguration för en riskvakt.

        Args:
            guard_name: Namn på riskvakten
            config: Ny konfiguration

        Returns:
            bool: True om uppdatering lyckades
        """
        try:
            if guard_name in self.guards:
                self.guards[guard_name].update(config)
                self._save_guards(self.guards)
                logger.info(f"⚙️ Riskvakt konfiguration uppdaterad: {guard_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Kunde inte uppdatera riskvakt {guard_name}: {e}")
            return False


# Global instans
risk_guards = RiskGuardsService()
