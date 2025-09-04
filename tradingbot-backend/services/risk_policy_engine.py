"""
Risk Policy Engine - central policy-källa som samlar RiskGuards och TradeConstraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.settings import Settings
from services.risk_guards import risk_guards
from services.trade_constraints import TradeConstraintsService


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str | None = None
    details: dict[str, Any] | None = None


class RiskPolicyEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.constraints = TradeConstraintsService(self.settings)

    def evaluate(
        self, *, symbol: str | None = None, amount: float | None = None, price: float | None = None
    ) -> PolicyDecision:
        # 1) Globala RiskGuards
        blocked, reason = risk_guards.check_all_guards(symbol, amount, price)
        if blocked:
            return PolicyDecision(False, f"risk_guard_blocked:{reason}")

        # 2) Trade constraints (time window + caps + cooldown)
        res = self.constraints.check(symbol=symbol)
        if not res.allowed:
            return PolicyDecision(False, res.reason, res.details)

        return PolicyDecision(True)

    def record_trade(self, *, symbol: str | None = None) -> None:
        self.constraints.record_trade(symbol=symbol)

    def status(self) -> dict[str, Any]:
        s = self.constraints.status()
        s["guards"] = risk_guards.get_guards_status()
        return s
