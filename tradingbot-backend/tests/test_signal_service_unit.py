import pytest

from services.signal_service import SignalService


@pytest.mark.asyncio
async def test_signal_service_deterministic_no_model(monkeypatch):
    # Disable model to force deterministic path
    from services import prob_model as pm_mod  # type: ignore

    try:
        monkeypatch.setattr(pm_mod.prob_model, "enabled", False, raising=False)
    except Exception:
        pass

    svc = SignalService()
    sc = svc.score(regime="trend", adx_value=25.0, ema_z_value=1.0)
    # Confidence = 25 (ADX) + 25 (EMA_Z) = 50.0
    assert round(sc.confidence, 1) == 50.0
    # Probability = base(0.85) * 0.5 * 100 = 42.5
    assert round(sc.probability, 1) == 42.5
    # Recommendation should be BUY for probability > 40
    assert sc.recommendation in ("buy", "hold")
    assert sc.recommendation == "buy"
