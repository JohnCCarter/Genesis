"""
Signal Service - enhetlig sannolikhet/konfidens och rekommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from services.prob_model import prob_model


@dataclass
class SignalScore:
    recommendation: Literal["buy", "sell", "hold"]
    confidence: float  # 0..100
    probability: float  # 0..100 (modell eller heuristik)
    features: dict[str, Any]
    source: Literal["deterministic", "probabilistic", "hybrid"]


class SignalService:
    @staticmethod
    def calc_confidence(adx_value: float | None, ema_z_value: float | None) -> float:
        if not adx_value or not ema_z_value:
            return 50.0
        adx_conf = min(adx_value / 50.0, 1.0) * 50
        ema_conf = min(abs(ema_z_value) / 2.0, 1.0) * 50
        return round(adx_conf + ema_conf, 1)

    @staticmethod
    def calc_probability(regime: str | None, confidence: float) -> float:
        bases = {"trend": 0.85, "balanced": 0.60, "range": 0.25}
        base = bases.get((regime or "").lower(), 0.5)
        return round(base * (confidence / 100.0) * 100.0, 1)

    @staticmethod
    def recommend(_regime: str | None, confidence: float, probability: float) -> str:
        if confidence < 30:
            return "hold"
        if probability > 70:
            return "buy"
        if probability > 40:
            return "buy"
        return "hold"

    def score(
        self,
        *,
        regime: str | None,
        adx_value: float | None,
        ema_z_value: float | None,
        features: dict[str, Any] | None = None,
    ) -> SignalScore:
        conf = self.calc_confidence(adx_value, ema_z_value)

        # Prob-only: använd endast modellens sannolikhet; fallback till 0 om ej aktiv
        model_prob_pct: float | None = None
        if prob_model.enabled:
            feats = {"ema": float(ema_z_value or 0.0), "rsi": float(adx_value or 0.0)}
            p = prob_model.predict_proba(feats)
            model_prob_pct = (
                max(float(p.get("buy", 0.0)), float(p.get("sell", 0.0))) * 100.0
            )

        # Prob-only (ingen heuristik):
        if model_prob_pct is not None:
            probability = round(model_prob_pct, 1)
            source: Literal["deterministic", "probabilistic", "hybrid"] = (
                "probabilistic"
            )
        else:
            probability = 0.0
            source = "probabilistic"

        rec = self.recommend(regime, conf, probability)
        return SignalScore(
            recommendation=rec,
            confidence=conf,
            probability=probability,
            features=features
            or {"adx_value": adx_value, "ema_z_value": ema_z_value, "regime": regime},
            source=source,
        )


"""
Enhetlig (orkestrerande) Signal-tjänst för Genesis Trading Bot

Konsoliderar signal-generering från olika moduler:
- Standard signal-generering (SignalGeneratorService)
- Realtids-signaler (WebSocket)
- Enhanced signaler (EnhancedAutoTrader)
"""

from datetime import datetime, timedelta
from typing import Any as _Any

from models.signal_models import LiveSignalsResponse, SignalResponse
from services.enhanced_auto_trader import EnhancedAutoTrader
from utils.logger import get_logger

logger = get_logger(__name__)

# OBS: UnifiedSignalService finns i services/unified_signal_service.py och är SoT.
# Behåll endast bakåtkompatibla alias här för att undvika dubbletter.
try:
    from services.unified_signal_service import unified_signal_service as _unified
except Exception:
    _unified = None  # type: ignore

# Backwards compatibility aliases
unified_signal_service = _unified  # type: ignore
signal_service = _unified  # type: ignore
