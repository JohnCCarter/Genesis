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
    def recommend(regime: str | None, confidence: float, probability: float) -> str:  # noqa: ARG004
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
        prob_h = self.calc_probability(regime, conf)

        # Modellprob om aktiv
        model_prob_pct: float | None = None
        if prob_model.enabled:
            feats = {"ema": float(ema_z_value or 0.0), "rsi": float(adx_value or 0.0)}
            p = prob_model.predict_proba(feats)
            # Ta 100 * max(buy, sell) som probability
            model_prob_pct = max(float(p.get("buy", 0.0)), float(p.get("sell", 0.0))) * 100.0

        # Kombinera
        if model_prob_pct is not None:
            probability = round(0.6 * model_prob_pct + 0.4 * prob_h, 1)
            source: Literal["deterministic", "probabilistic", "hybrid"] = "hybrid"
        else:
            probability = prob_h
            source = "deterministic"

        rec = self.recommend(regime, conf, probability)
        return SignalScore(
            recommendation=rec,
            confidence=conf,
            probability=probability,
            features=features or {"adx_value": adx_value, "ema_z_value": ema_z_value, "regime": regime},
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
from services.bitfinex_websocket import BitfinexWebSocketService
from services.enhanced_auto_trader import EnhancedAutoTrader
from services.signal_generator import SignalGeneratorService
from utils.logger import get_logger

logger = get_logger(__name__)


class UnifiedSignalService:
    """
    Enhetlig service för all signal-generering i systemet.

    Konsoliderar:
    - Standard signal-generering
    - Realtids-signaler (WebSocket)
    - Enhanced signaler med confidence scores
    """

    def __init__(self):
        self._signal_generator = SignalGeneratorService()
        self._enhanced_trader = EnhancedAutoTrader()
        self._ws_service: BitfinexWebSocketService | None = None

        # Enhetlig cache för alla signaler
        self._signal_cache: dict[str, SignalResponse] = {}
        self._cache_ttl = timedelta(minutes=10)
        self._last_update: dict[str, datetime] = {}

        logger.info("🚀 SignalService initialiserad - enhetlig signal-hantering")

    def set_websocket_service(self, ws_service: BitfinexWebSocketService):
        """Sätt WebSocket service för realtids-signaler"""
        self._ws_service = ws_service
        logger.info("🔗 WebSocket service kopplad till SignalService")

    async def generate_signals(self, symbols: list[str], mode: str = "standard") -> LiveSignalsResponse:
        """
        Enhetlig signal-generering för alla moduler.

        Args:
            symbols: Lista med symboler att generera signaler för
            mode: "standard", "enhanced", eller "realtime"

        Returns:
            LiveSignalsResponse med alla signaler
        """
        logger.info(f"⚡ Genererar {mode}-signaler för {len(symbols)} symboler")

        if mode == "enhanced":
            return await self._generate_enhanced_signals(symbols)
        elif mode == "realtime":
            return await self._generate_realtime_signals(symbols)
        else:
            return await self._generate_standard_signals(symbols)

    async def _generate_standard_signals(self, symbols: list[str]) -> LiveSignalsResponse:
        """Standard signal-generering via SignalGeneratorService"""
        return await self._signal_generator.generate_live_signals(symbols)

    async def _generate_enhanced_signals(self, symbols: list[str]) -> LiveSignalsResponse:
        """Enhanced signaler med confidence scores"""
        signals = []

        for symbol in symbols:
            try:
                signal = await self._enhanced_trader._get_enhanced_signal(symbol)
                if signal:
                    signals.append(signal)
                    self._signal_cache[symbol] = signal
                    self._last_update[symbol] = datetime.now()
                    logger.info(f"✅ Enhanced signal för {symbol}: {signal.signal_type}")
            except Exception as e:
                logger.error(f"❌ Kunde inte generera enhanced signal för {symbol}: {e}")

        return LiveSignalsResponse(
            success=True,
            signals=signals,
            timestamp=datetime.now(),
            total_signals=len(signals),
        )

    async def _generate_realtime_signals(self, symbols: list[str]) -> LiveSignalsResponse:
        """Realtids-signaler via WebSocket (om tillgängligt)"""
        if not self._ws_service:
            logger.warning("⚠️ WebSocket service inte tillgänglig, fallback till standard")
            return await self._generate_standard_signals(symbols)

        signals = []
        for symbol in symbols:
            try:
                # Hämta senaste WebSocket-data
                latest_data = self._ws_service.latest_prices.get(symbol)
                if latest_data:
                    # Generera realtids-signal baserat på WebSocket-data
                    signal = await self._generate_realtime_signal_for_symbol(symbol, latest_data)
                    if signal:
                        signals.append(signal)
                        self._signal_cache[symbol] = signal
                        self._last_update[symbol] = datetime.now()
            except Exception as e:
                logger.error(f"❌ Kunde inte generera realtids-signal för {symbol}: {e}")

        return LiveSignalsResponse(
            success=True,
            signals=signals,
            timestamp=datetime.now(),
            total_signals=len(signals),
        )

    async def _generate_realtime_signal_for_symbol(self, symbol: str, price_data: float) -> SignalResponse | None:
        """Generera realtids-signal för en symbol baserat på WebSocket-data"""
        try:
            # Använd standard signal-generering men med realtids-pris
            signal = await self._signal_generator._generate_signal_for_symbol(symbol)
            if signal:
                # Markera som realtids-signal
                signal.metadata = signal.metadata or {}
                signal.metadata["source"] = "websocket_realtime"
                signal.metadata["price_data"] = price_data
                return signal
        except Exception as e:
            logger.error(f"❌ Fel vid realtids-signal för {symbol}: {e}")

        return None

    def get_cached_signal(self, symbol: str) -> SignalResponse | None:
        """Hämta cached signal för en symbol"""
        if symbol in self._signal_cache:
            last_update = self._last_update.get(symbol)
            if last_update and (datetime.now() - last_update) < self._cache_ttl:
                return self._signal_cache[symbol]
            else:
                # Ta bort utgången cache
                del self._signal_cache[symbol]
                if symbol in self._last_update:
                    del self._last_update[symbol]

        return None

    def clear_cache(self, symbol: str | None = None):
        """Rensa cache för specifik symbol eller alla"""
        if symbol:
            self._signal_cache.pop(symbol, None)
            self._last_update.pop(symbol, None)
            logger.info(f"🗑️ Cache rensad för {symbol}")
        else:
            self._signal_cache.clear()
            self._last_update.clear()
            logger.info("🗑️ All cache rensad")

    def get_cache_stats(self) -> dict[str, _Any]:
        """Hämta cache-statistik"""
        return {
            "total_cached": len(self._signal_cache),
            "cache_ttl_minutes": self._cache_ttl.total_seconds() / 60,
            "oldest_entry": (min(self._last_update.values()) if self._last_update else None),
            "newest_entry": (max(self._last_update.values()) if self._last_update else None),
        }


# Global instans för enhetlig åtkomst
unified_signal_service = UnifiedSignalService()
# Backwards compatibility alias for existing imports
signal_service = unified_signal_service
