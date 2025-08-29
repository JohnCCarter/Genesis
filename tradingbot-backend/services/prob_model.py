"""
Probability Model Inference API

Feature-flagged, safe fallback till heuristik om modell saknas.
"""

from __future__ import annotations

import json
from typing import Any

from config.settings import Settings


class ProbabilityModel:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.enabled = bool(self.settings.PROB_MODEL_ENABLED)
        self.model_meta: dict[str, Any] = {}

        self._loaded = False
        if self.enabled:
            self._loaded = self._try_load()

    def _try_load(self) -> bool:
        try:
            path = self.settings.PROB_MODEL_FILE
            if not path:
                return False
            with open(path, encoding="utf-8") as f:
                self.model_meta = json.load(f)
            return True
        except Exception:
            return False

    def reload(self) -> bool:
        """Reload model from configured file path. Returns True on success."""
        try:
            ok = self._try_load()
            self._loaded = ok
            return ok
        except Exception:
            return False

    def predict_proba(self, features: dict[str, float]) -> dict[str, float]:
        """
        Returnerar sannolikheter {buy, sell, hold}.
        Fallback: enkel heuristik om modellen inte är laddad/aktiverad.
        """
        if not (self.enabled and self._loaded):
            # Heuristisk fallback: håll sannolikhet på hold om ingen model
            return {"buy": 0.0, "sell": 0.0, "hold": 1.0}

        try:
            # Om exporterad LR‑modell finns: sigmoid(w·x + b) för buy och sell; hold normaliseras
            schema = self.model_meta.get("schema") or ["ema", "rsi"]
            x = [float(features.get(k, 0.0)) for k in schema]

            def _sigmoid(z: float) -> float:
                import math

                return 1.0 / (1.0 + math.exp(-z))

            def _score(key: str) -> float:
                comp = self.model_meta.get(key)
                if not comp:
                    return 0.0
                w = comp.get("w") or []
                b = float(comp.get("b") or 0.0)
                z = sum(float(w[i]) * x[i] for i in range(min(len(w), len(x)))) + b
                calib = comp.get("calib") or {}
                a = float(calib.get("a", 1.0))
                bb = float(calib.get("b", 0.0))
                return _sigmoid(a * z + bb)

            p_buy_raw = _score("buy")
            p_sell_raw = _score("sell")
            # Normalisera med hold som rest
            p_hold = max(0.0, 1.0 - (p_buy_raw + p_sell_raw))
            total = p_buy_raw + p_sell_raw + p_hold
            if total <= 0:
                return {"buy": 0.0, "sell": 0.0, "hold": 1.0}
            p_buy = p_buy_raw / total
            p_sell = p_sell_raw / total
            p_hold = p_hold / total
            return {"buy": p_buy, "sell": p_sell, "hold": p_hold}
        except Exception:
            return {"buy": 0.0, "sell": 0.0, "hold": 1.0}


prob_model = ProbabilityModel()
