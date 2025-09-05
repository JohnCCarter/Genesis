import pytest

from services.risk_policy_engine import RiskPolicyEngine


class _StubRes:
    def __init__(self, allowed: bool, reason: str | None = None, details: dict | None = None):
        self.allowed = allowed
        self.reason = reason
        self.details = details or {}


@pytest.mark.asyncio
async def test_risk_policy_blocks_on_guards(monkeypatch):
    import services.risk_policy_engine as rpe

    monkeypatch.setattr(rpe.risk_guards, "check_all_guards", lambda *args, **kwargs: (True, "max_daily_loss"))

    eng = RiskPolicyEngine()
    res = eng.evaluate(symbol="tBTCUSD")
    assert not res.allowed
    assert res.reason.startswith("risk_guard_blocked:")


def test_risk_policy_blocks_on_constraints(monkeypatch):
    eng = RiskPolicyEngine()
    monkeypatch.setattr(eng.constraints, "check", lambda **kwargs: _StubRes(False, "trading_paused"))

    res = eng.evaluate(symbol="tBTCUSD")
    assert not res.allowed
    assert res.reason == "trading_paused"


def test_risk_policy_allows_when_ok(monkeypatch):
    eng = RiskPolicyEngine()
    monkeypatch.setattr(eng.constraints, "check", lambda **kwargs: _StubRes(True))
    # ensure guards do not block
    import services.risk_policy_engine as rpe

    monkeypatch.setattr(rpe.risk_guards, "check_all_guards", lambda *args, **kwargs: (False, None))

    res = eng.evaluate(symbol="tBTCUSD")
    assert res.allowed


def test_risk_policy_record_trade_delegates(monkeypatch):
    eng = RiskPolicyEngine()
    called = {}

    def _rec(symbol: str | None = None):  # noqa: ANN001
        called["sym"] = symbol

    monkeypatch.setattr(eng.constraints, "record_trade", _rec)
    eng.record_trade(symbol="tETHUSD")
    assert called.get("sym") == "tETHUSD"
