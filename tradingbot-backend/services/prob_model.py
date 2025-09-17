"""
Probability Model Inference API

Feature-flagged, safe fallback till heuristik om modell saknas.
"""

from __future__ import annotations

import json
from typing import Any, Tuple
import os

from config.settings import settings, Settings


class ProbabilityModel:
    def __init__(self, settings_override: Settings | None = None) -> None:
        self.settings = settings_override or settings
        self.enabled = bool(self.settings.PROB_MODEL_ENABLED)
        self.model_meta: dict[str, Any] = {}

        self._loaded = False
        if self.enabled:
            self._loaded = self._try_load()
        # Meta-cache: {(SYMBOL, TF): (meta, mtime)}
        self._meta_cache: dict[tuple[str, str], tuple[dict[str, Any], float]] = {}

    def _try_load(self) -> bool:
        try:
            # Läs modellfil från runtime_config (POST /prob/config kan uppdatera) med fallback till Settings
            try:
                import services.runtime_config as rc  # lazy import to avoid cycles

                path = rc.get_str("PROB_MODEL_FILE", getattr(self.settings, "PROB_MODEL_FILE", None))
            except Exception:
                path = getattr(self.settings, "PROB_MODEL_FILE", None)
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


## NOTE: instance is created at the end of the file after extended methods are defined


def _normalize_symbol(sym: str | None) -> str | None:
    if not sym:
        return None
    s = sym.strip()
    if s.startswith("t"):
        s = s[1:]
    # Remove any test prefixes like TESTBTC:TESTUSD → BTCUSD
    try:
        import re as _re

        s = _re.sub(r"[^A-Za-z0-9]", "", s)
    except Exception:
        s = s.replace(":", "").replace("_", "")
    return s or None


class ProbabilityModel(ProbabilityModel):  # type: ignore[misc]
    def _predict_with_meta(self, meta: dict[str, Any] | None, features: dict[str, float]) -> dict[str, float]:
        if not (self.enabled and meta):
            return {"buy": 0.0, "sell": 0.0, "hold": 1.0}
        try:
            schema = meta.get("schema") or ["ema", "rsi"]
            x = [float(features.get(k, 0.0)) for k in schema]

            def _sigmoid(z: float) -> float:
                import math

                return 1.0 / (1.0 + math.exp(-z))

            def _score(comp_key: str) -> float:
                comp = meta.get(comp_key)
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
            p_hold = max(0.0, 1.0 - (p_buy_raw + p_sell_raw))
            total = p_buy_raw + p_sell_raw + p_hold
            if total <= 0:
                return {"buy": 0.0, "sell": 0.0, "hold": 1.0}
            return {
                "buy": p_buy_raw / total,
                "sell": p_sell_raw / total,
                "hold": p_hold / total,
            }
        except Exception:
            return {"buy": 0.0, "sell": 0.0, "hold": 1.0}

    def _candidate_model_path(self, symbol: str | None, timeframe: str | None) -> str | None:
        """Return a per-symbol/timeframe model path if it exists.

        Tries both cwd-relative and module-relative paths:
        - config/models/<SYMBOL>_<TF>.json
        - <this_dir>/../config/models/<SYMBOL>_<TF>.json
        """
        sym = _normalize_symbol(symbol)
        tf = (timeframe or "").strip()
        if not sym or not tf:
            return None
        fname = f"{sym}_{tf}.json"
        candidates = [
            os.path.join("config", "models", fname),
            os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config", "models", fname)),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return None

    def _load_meta_from_file(self, path: str) -> dict[str, Any] | None:
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _get_cached_meta(self, path: str) -> dict[str, Any] | None:
        try:
            stat = os.stat(path)
            mtime = float(stat.st_mtime)
            key = (
                os.path.basename(path).split("_")[0],
                os.path.basename(path).split("_")[1].split(".")[0],
            )
            cached = self._meta_cache.get(key)
            if cached and abs(cached[1] - mtime) < 1e-6:
                return cached[0]
            meta = self._load_meta_from_file(path)
            if meta:
                self._meta_cache[key] = (meta, mtime)
            return meta
        except Exception:
            return self._load_meta_from_file(path)

    def get_meta_for(self, symbol: str | None, timeframe: str | None) -> dict[str, Any] | None:
        """Get best-available meta for the given symbol/timeframe or fallback to default loaded meta."""
        # Prefer per-symbol/timeframe model if present
        candidate = self._candidate_model_path(symbol, timeframe)
        if candidate:
            meta = self._get_cached_meta(candidate)
            if meta:
                return meta
        # Fallback to globally loaded model
        if self.enabled and self._loaded and self.model_meta:
            return self.model_meta
        return None

    def predict_proba_for(
        self,
        symbol: str | None,
        timeframe: str | None,
        features: dict[str, float],
    ) -> tuple[dict[str, float], dict[str, Any] | None]:
        """Predict probabilities using a per-symbol/timeframe model if available, otherwise fallback.

        Returns (probs, meta_used). When meta_used is None, heuristic fallback was used.
        """
        meta = self.get_meta_for(symbol, timeframe)
        probs = self._predict_with_meta(meta, features)
        return probs, meta


# Create global instance after extended methods are available
prob_model = ProbabilityModel()
