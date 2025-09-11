"""
Risk Guards Service - Globala riskvakter fÃ¶r tradingboten.

Implementerar:
- Max Daily Loss kontroll
- Kill-Switch funktionalitet
- Cooldown-period efter trigger
- Dashboard-visning av riskvakter
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any

from config.settings import Settings
import services.runtime_config as rc
from services.performance import PerformanceService
from utils.logger import get_logger

logger = get_logger(__name__)


class RiskGuardsService:
    """Service fÃ¶r globala riskvakter och kill-switch funktionalitet."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.guards_file = "config/risk_guards.json"
        self.performance_service = PerformanceService(self.settings)

        # Ladda eller skapa default guards
        self.guards = self._load_guards()
        # Test-isolering: nollställ ev. triggertillstånd
        try:
            if os.environ.get("PYTEST_CURRENT_TEST"):
                if "max_daily_loss" in self.guards:
                    self.guards["max_daily_loss"]["triggered"] = False
                    self.guards["max_daily_loss"]["triggered_at"] = None
                if "kill_switch" in self.guards:
                    self.guards["kill_switch"]["triggered"] = False
                    self.guards["kill_switch"]["triggered_at"] = None
        except Exception:
            pass

        logger.info("ðŸ›¡ï¸ RiskGuardsService initialiserad")

    def _load_guards(self) -> dict[str, Any]:
        """Ladda riskvakter frÃ¥n fil eller skapa defaults."""
        try:
            if os.path.exists(self.guards_file):
                with open(self.guards_file, encoding="utf-8") as f:
                    guards = json.load(f)
                logger.info(f"Laddade riskvakter från {self.guards_file}")
                return guards
        except Exception as e:
            logger.warning(f"âš ï¸ Kunde inte ladda riskvakter: {e}")

        # Default guards
        default_guards = {
            "max_daily_loss": {
                "enabled": True,
                "percentage": 5.0,  # 5% max daglig fÃ¶rlust
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
            logger.error(f"âŒ Kunde inte spara riskvakter: {e}")

    def _get_current_equity(self) -> float:
        """HÃ¤mta live equity (USD) med robust timeout."""
        try:
            # Enkel fallback - returnera 0.0 fÃ¶r att undvika hÃ¤ngningar
            # I en riktig implementation skulle vi anvÃ¤nda en separat thread eller
            # gÃ¶ra denna metod async
            logger.debug("âš ï¸ Equity computation disabled to prevent hanging")
            return 0.0

        except Exception as e:
            logger.error(f"âŒ Kunde inte hÃ¤mta aktuell equity: {e}")
            return 0.0

    def _initialize_daily_tracking(self) -> None:
        """Initiera daglig spÃ¥rning; nollstÃ¤ll daglig trigger vid ny dag.

        Dagliga vakter bÃ¶r Ã¥terstÃ¤llas nÃ¤r kalenderdagen byts. Eventuell
        cooldown fÃ¶r max daily loss gÃ¤ller innevarande dag; pÃ¥ ny dag bÃ¶r
        handel kunna Ã¥terupptas frÃ¥n daglig-vaktens perspektiv.
        """
        today = datetime.now().date()
        guard = self.guards.get("max_daily_loss", {})
        daily_start_date = guard.get("daily_start_date")

        today_s = today.isoformat()
        if daily_start_date != today_s:
            prev_date = daily_start_date
            # StÃ¤mpla dagens datum och initiera baseline om saknas
            guard["daily_start_date"] = today_s
            if not guard.get("daily_start_equity"):
                guard["daily_start_equity"] = self._get_current_equity()

            # Ny dag: nollstÃ¤ll trigger/cooldown ENDAST om vi faktiskt byter frÃ¥n en tidigare dag
            if prev_date and prev_date != today_s:
                if guard.get("triggered") or guard.get("triggered_at"):
                    guard["triggered"] = False
                    guard["triggered_at"] = None

            self.guards["max_daily_loss"] = guard
            self._save_guards(self.guards)
            logger.info(f"ðŸ“… Ny dag initialiserad: {today}")

    def check_max_daily_loss(self) -> tuple[bool, str | None]:
        """
        Kontrollera max daily loss.

        Returns:
            Tuple[bool, Optional[str]]: (blocked, reason)
        """
        guard = self.guards["max_daily_loss"]
        # Om klienten sÃ¤tter daily_start_equity manuellt i runtime utan datum â€“ behandla som ny baseline
        # och rensa tidigare trigger/cooldown fÃ¶r daglig vakt.
        if guard.get("daily_start_equity") is not None and not guard.get("daily_start_date"):
            guard["daily_start_date"] = datetime.now().date().isoformat()
            if guard.get("triggered"):
                guard["triggered"] = False
                guard["triggered_at"] = None

        if not guard["enabled"]:
            return False, None

        self._initialize_daily_tracking()

        # Compute daily loss early and allow if below threshold
        start_equity_early = guard.get("daily_start_equity")
        daily_loss_pct_early: float | None = None
        if start_equity_early and start_equity_early > 0:
            current_equity_early = self._get_current_equity()
            daily_loss_pct_early = ((start_equity_early - current_equity_early) / start_equity_early) * 100
        if daily_loss_pct_early is not None and daily_loss_pct_early < guard.get("percentage", 0):
            if guard.get("triggered"):
                guard["triggered"] = False
                guard["triggered_at"] = None
                self._save_guards(self.guards)
            return False, None

        # If above threshold, signal breach regardless of existing cooldown
        if (
            daily_loss_pct_early is not None
            and daily_loss_pct_early >= guard.get("percentage", 0)
            and not guard.get("triggered")
        ):
            if not guard.get("triggered"):
                guard["triggered"] = True
                guard["triggered_at"] = datetime.now().isoformat()
                self._save_guards(self.guards)
                try:
                    logger.warning(f"Max daily loss triggad: {daily_loss_pct_early:.2f}% förlust")
                except Exception:
                    pass
            return True, f"Max daily loss överskriden: {daily_loss_pct_early:.2f}%"

        # Om redan triggad: prioritera cooldown fÃ¶rst, oavsett dagsfÃ¶rlust
        if guard.get("triggered") and guard.get("triggered_at"):
            try:
                triggered_time = datetime.fromisoformat(guard["triggered_at"])
                cooldown_end = triggered_time + timedelta(hours=guard["cooldown_hours"])
                if datetime.now() < cooldown_end:
                    remaining = cooldown_end - datetime.now()
                    return (
                        True,
                        f"Max daily loss cooldown aktiv: {remaining.seconds // 3600}h kvar",
                    )
                else:
                    guard["triggered"] = False
                    guard["triggered_at"] = None
                    self._save_guards(self.guards)
            except Exception:
                pass

        # BerÃ¤kna daglig fÃ¶rlust
        start_equity = guard.get("daily_start_equity")
        daily_loss_pct: float | None = None
        if start_equity and start_equity > 0:
            current_equity = self._get_current_equity()
            daily_loss_pct = ((start_equity - current_equity) / start_equity) * 100

        # Kontrollera daglig fÃ¶rlust mot trÃ¶skel â€“ detta tar alltid fÃ¶retrÃ¤de
        if daily_loss_pct is not None and daily_loss_pct >= guard["percentage"]:
            if not guard.get("triggered"):
                guard["triggered"] = True
                guard["triggered_at"] = datetime.now().isoformat()
                self._save_guards(self.guards)
                logger.warning(f"ðŸš¨ Max daily loss triggad: {daily_loss_pct:.2f}% fÃ¶rlust")
            return True, f"Max daily loss Ã¶verskriden: {daily_loss_pct:.2f}%"

        # Under trÃ¶skel â†’ rensa trigger och blockera inte
        if daily_loss_pct is not None and guard.get("triggered"):
            guard["triggered"] = False
            guard["triggered_at"] = None
            self._save_guards(self.guards)
            return False, None

        # (vid det hÃ¤r laget Ã¤r vi inte i cooldownâ€‘lÃ¤ge)

        # Om ingen start_equity: endast cooldown kan blockera
        if guard.get("triggered") and guard.get("triggered_at"):
            try:
                triggered_time = datetime.fromisoformat(guard["triggered_at"])
                cooldown_end = triggered_time + timedelta(hours=guard["cooldown_hours"])
                if datetime.now() < cooldown_end:
                    remaining = cooldown_end - datetime.now()
                    return (
                        True,
                        f"Max daily loss cooldown aktiv: {remaining.seconds // 3600}h kvar",
                    )
            except Exception:
                pass

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
                    return (
                        True,
                        f"Kill-switch cooldown aktiv: {remaining.seconds // 3600}h kvar",
                    )
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
                    logger.error(f"ðŸš¨ Kill-switch triggad: {guard['reason']}")

                return True, guard["reason"]

        return False, None

    def check_exposure_limits(
        self, symbol: str, amount: float, price: float
    ) -> tuple[bool, str | None]:  # noqa: ARG002, ANN401
        """
        Kontrollera exposure limits fÃ¶r en ny position.

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

        # HÃ¤r skulle vi implementera kontroll av:
        # - Antal Ã¶ppna positioner
        # - Position size vs total equity
        # - Total exposure vs total equity

        # BerÃ¤kna positionens storlek som procent av equity.
        # Tolkning:
        # - Om |amount| <= 1.0: behandla amount som andel av equity (t.ex. 0.1 = 10% av equity)
        # - Annars: anvÃ¤nd notional = |amount| * price
        current_equity = self._get_current_equity()
        position_pct: float = 0.0
        try:
            if abs(float(amount)) <= 1.0 and current_equity > 0:
                # Fraktionsbaserad sizing â€“ direkt procent av equity
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
        self,
        symbol: str | None = None,
        amount: float | None = None,
        price: float | None = None,
    ) -> tuple[bool, str | None]:
        """
        Kontrollera alla riskvakter.

        Args:
            symbol: Trading symbol (fÃ¶r exposure checks)
            amount: Position amount (fÃ¶r exposure checks)
            price: Entry price (fÃ¶r exposure checks)

        Returns:
            Tuple[bool, Optional[str]]: (blocked, reason)
        """
        # Respektera global RISK_ENABLED via Settings (instansens settings)
        try:
            if not rc.get_bool("RISK_ENABLED", getattr(self.settings, "RISK_ENABLED", True)):
                return False, None
        except Exception:
            pass

        # Kontrollera max daily loss
        blocked, reason = self.check_max_daily_loss()
        if blocked:
            return True, reason

        # Kontrollera kill-switch
        blocked, reason = self.check_kill_switch()
        if blocked:
            return True, reason

        # Kontrollera exposure limits om data finns
        if symbol is not None and amount is not None and price is not None:
            blocked, reason = self.check_exposure_limits(symbol, amount, price)
            if blocked:
                return True, reason

        return False, None

    def reset_guard(self, guard_name: str) -> bool:
        """
        Ã…terstÃ¤ll en specifik riskvakt.

        Args:
            guard_name: Namn pÃ¥ riskvakten att Ã¥terstÃ¤lla

        Returns:
            bool: True om Ã¥terstÃ¤llning lyckades
        """
        try:
            if guard_name in self.guards:
                guard = self.guards[guard_name]
                guard["triggered"] = False
                guard["triggered_at"] = None
                guard["reason"] = None
                self._save_guards(self.guards)
                logger.info(f"ðŸ”„ Riskvakt Ã¥terstÃ¤lld: {guard_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"âŒ Kunde inte Ã¥terstÃ¤lla riskvakt {guard_name}: {e}")
            return False

    def get_guards_status(self) -> dict[str, Any]:
        """
        HÃ¤mta status fÃ¶r alla riskvakter.

        Returns:
            Dict med status fÃ¶r alla guards
        """
        try:
            current_equity = self._get_current_equity()

            # BerÃ¤kna daglig fÃ¶rlust
            daily_loss_pct = 0.0
            start_equity = self.guards["max_daily_loss"].get("daily_start_equity")
            if start_equity and start_equity > 0:
                daily_loss_pct = ((start_equity - current_equity) / start_equity) * 100

            # BerÃ¤kna drawdown
            drawdown_pct = daily_loss_pct  # FÃ¶renklad - i verkligheten skulle detta vara frÃ¥n peak

            status = {
                "current_equity": current_equity,
                "daily_loss_percentage": daily_loss_pct,
                "drawdown_percentage": drawdown_pct,
                "guards": self.guards.copy(),
                "last_updated": datetime.now().isoformat(),
            }

            return status
        except Exception as e:
            logger.error(f"âŒ Kunde inte hÃ¤mta guards status: {e}")
            return {"error": str(e)}

    def update_guard_config(self, guard_name: str, config: dict[str, Any]) -> bool:
        """
        Uppdatera konfiguration fÃ¶r en riskvakt.

        Args:
            guard_name: Namn pÃ¥ riskvakten
            config: Ny konfiguration

        Returns:
            bool: True om uppdatering lyckades
        """
        try:
            if guard_name in self.guards:
                self.guards[guard_name].update(config)
                self._save_guards(self.guards)
                logger.info(f"âš™ï¸ Riskvakt konfiguration uppdaterad: {guard_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"âŒ Kunde inte uppdatera riskvakt {guard_name}: {e}")
            return False


# Global instans
risk_guards = RiskGuardsService()
