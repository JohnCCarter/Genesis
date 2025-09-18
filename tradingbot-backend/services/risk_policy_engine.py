"""
Risk Policy Engine - central policy-källa som samlar RiskGuards och TradeConstraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.settings import Settings
from services.risk_guards import risk_guards
from services.trade_constraints import TradeConstraintsService
import services.runtime_config as rc


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str | None = None
    details: dict[str, Any] | None = None


class RiskPolicyEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        if settings is None:
            from config.settings import settings as _settings

            self.settings = _settings
        else:
            self.settings = settings
        self.constraints = TradeConstraintsService(self.settings)

    def evaluate(
        self,
        *,
        symbol: str | None = None,
        amount: float | None = None,
        price: float | None = None,
        include_guards: bool = True,
    ) -> PolicyDecision:
        # Avbryt alla riskkontroller om risk är avstängd
        if not rc.get_bool("RISK_ENABLED", getattr(self.settings, "RISK_ENABLED", True)):
            return PolicyDecision(True)
        # 1) Utvärdera båda källorna och prioritera tydliga driftstopp (paused/fönster) före guards.
        guard_blocked = False
        guard_reason: str | None = None
        if include_guards:
            guard_blocked, guard_reason = risk_guards.check_all_guards(
                symbol=symbol or None,
                amount=(float(amount) if amount is not None else None),
                price=(float(price) if price is not None else None),
            )

        res = self.constraints.check(symbol=symbol)

        # Paus/fönster har högsta prioritet
        if not res.allowed and res.reason in (
            "trading_paused",
            "outside_trading_window",
        ):
            return PolicyDecision(False, res.reason, res.details)

        # Om guards blockerar, rapportera det
        if include_guards and guard_blocked:
            return PolicyDecision(False, f"risk_guard_blocked:{guard_reason}")

        # Annars returnera constraints-resultat
        if not res.allowed:
            return PolicyDecision(False, res.reason, res.details)

        return PolicyDecision(True)

    def record_trade(self, *, symbol: str | None = None) -> None:
        self.constraints.record_trade(symbol=symbol)

    def status(self) -> dict[str, Any]:
        s = self.constraints.status()
        s["guards"] = risk_guards.get_guards_status()
        return s
