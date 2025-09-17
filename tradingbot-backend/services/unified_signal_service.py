"""
Unified Signal Service - Enhetlig signal-generering för alla paneler.

Löser problem med:
- Olika signal-beräkningar i olika paneler
- Inkonsistenta confidence scores
- Duplicerad logik mellan MarketPanel, LiveSignalsPanel, EnhancedAutoTradingPanel
- Olika refresh-intervall för samma data
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from models.signal_models import LiveSignalsResponse, SignalResponse
from services.signal_service import SignalScore
from services.market_data_facade import get_market_data
from services.signal_service import SignalService
from services.symbols import SymbolService
from indicators.regime import detect_regime, ema_z
from indicators.adx import adx as adx_series
from utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class UnifiedSignalService:
    """
    Enhetlig service för all signal-generering i systemet.

    Konsoliderar signal-generering från:
    - Market Panel (regime data)
    - Live Signals Panel
    - Enhanced Auto Trading Panel
    - Strategy endpoints

    Alla paneler använder samma SignalService.score() som Single Source of Truth.
    """

    def __init__(self):
        self.signal_service = SignalService()
        self.market_data = get_market_data()
        self.symbol_service = SymbolService()

        # Enhetlig cache för alla signaler
        self._signal_cache: dict[str, SignalResponse] = {}
        self._regime_cache: dict[str, dict[str, Any]] = {}
        self._cache_ttl = timedelta(minutes=2)  # Kortare TTL för realtidsdata
        self._last_update: dict[str, datetime] = {}

        logger.info(
            "🚀 UnifiedSignalService initialiserad - Single Source of Truth för signaler"
        )

    async def get_symbols(self) -> list[str]:
        """Hämta aktiva symboler från samma källa som alla paneler."""
        try:
            # Hämta symboler från samma källa som Live Signals
            raw_symbols = (settings.WS_SUBSCRIBE_SYMBOLS or "").strip()
            if raw_symbols:
                symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
            else:
                symbols = self.symbol_service.get_symbols(test_only=True, fmt="v2")[:5]

            logger.debug(f"📊 Hämtar symboler: {len(symbols)} aktiva")
            return symbols
        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av symboler: {e}")
            return ["tBTCUSD", "tETHUSD"]  # Fallback

    async def get_regime_data(
        self, symbol: str, force_refresh: bool = False
    ) -> dict[str, Any] | None:
        """
        Hämta regime data för en symbol.

        Använder samma logik som alla paneler för konsistens.
        """
        cache_key = f"regime_{symbol}"

        # Kontrollera cache
        if not force_refresh and cache_key in self._regime_cache:
            cached_data = self._regime_cache[cache_key]
            if (datetime.now() - cached_data["timestamp"]) < self._cache_ttl:
                logger.debug(f"📋 Använder cached regime data för {symbol}")
                return cached_data["data"]

        try:
            # Hämta live regime data direkt via MarketDataFacade
            candles = await self.market_data.get_candles(symbol, "1m", limit=50)

            if not candles or len(candles) < 20:
                logger.warning(
                    f"⚠️ Otillräcklig data för {symbol}: {len(candles) if candles else 0} candles"
                )
                return None

            # Extrahera OHLC data
            highs = [float(candle[3]) for candle in candles if len(candle) >= 4]
            lows = [float(candle[4]) for candle in candles if len(candle) >= 5]
            closes = [float(candle[2]) for candle in candles if len(candle) >= 3]

            if len(highs) < 20 or len(lows) < 20 or len(closes) < 20:
                logger.warning(f"⚠️ Otillräcklig OHLC data för {symbol}")
                return None

            # Beräkna regime och indikatorer
            # Default config för regime detection
            regime_cfg = {"ADX_PERIOD": 14, "EMA_FAST": 3, "EMA_SLOW": 7, "Z_WIN": 200}
            regime = detect_regime(highs, lows, closes, regime_cfg)
            adx_vals = adx_series(highs, lows, closes, period=14)
            ez_vals = ema_z(closes, 3, 7, 200)

            regime_data = {
                "symbol": symbol,
                "regime": regime,
                "adx_value": adx_vals[-1] if adx_vals else None,
                "ema_z_value": ez_vals[-1] if ez_vals else None,
                "last_close": closes[-1] if closes else None,
                "timestamp": datetime.now(),
            }

            # Spara i cache
            self._regime_cache[cache_key] = {
                "data": regime_data,
                "timestamp": datetime.now(),
            }

            logger.debug(f"✅ Regime data för {symbol}: {regime}")
            return regime_data

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av regime data för {symbol}: {e}")
            return None

    async def generate_signal(
        self, symbol: str, force_refresh: bool = False
    ) -> SignalResponse | None:
        """
        Generera enhetlig signal för en symbol.

        Använder SignalService.score() som Single Source of Truth.
        """
        cache_key = f"signal_{symbol}"

        # Kontrollera cache
        if not force_refresh and cache_key in self._signal_cache:
            cached_signal = self._signal_cache[cache_key]
            if (datetime.now() - cached_signal.timestamp) < self._cache_ttl:
                logger.debug(f"📋 Använder cached signal för {symbol}")
                return cached_signal

        try:
            # Hämta regime data
            regime_data = await self.get_regime_data(symbol, force_refresh)
            if not regime_data:
                logger.warning(f"⚠️ Ingen regime data för {symbol}")
                return None

            # Använd SignalService.score() som Single Source of Truth
            sc = self.signal_service.score(
                regime=regime_data["regime"],
                adx_value=regime_data["adx_value"],
                ema_z_value=regime_data["ema_z_value"],
            )

            # Skapa SignalResponse med enhetliga värden
            signal = SignalResponse(
                symbol=symbol,
                signal_type=self._determine_signal_type(sc),
                confidence_score=sc.confidence,  # Single Source of Truth
                trading_probability=sc.probability,  # Single Source of Truth
                recommendation=self._get_recommendation(sc),
                timestamp=datetime.now(),
                strength=self._calculate_strength(sc),
                reason=self._generate_reason(sc, regime_data),
                current_price=regime_data["last_close"],
                adx_value=regime_data["adx_value"],
                ema_z_value=regime_data["ema_z_value"],
                regime=regime_data["regime"],
                status="ACTIVE",  # Lägg till status fält
            )

            # Spara i cache
            self._signal_cache[cache_key] = signal
            self._last_update[symbol] = datetime.now()

            logger.debug(
                f"✅ Signal för {symbol}: {signal.signal_type} (confidence: {sc.confidence})"
            )
            return signal

        except Exception as e:
            logger.error(f"❌ Fel vid generering av signal för {symbol}: {e}")
            return None

    async def generate_all_signals(
        self, force_refresh: bool = False
    ) -> LiveSignalsResponse:
        """
        Generera signaler för alla aktiva symboler.

        Används av alla paneler för konsistenta resultat.
        """
        try:
            symbols = await self.get_symbols()
            logger.info(f"⚡ Genererar enhetliga signaler för {len(symbols)} symboler")

            # Generera signaler parallellt för bättre prestanda
            signal_tasks = [
                self.generate_signal(symbol, force_refresh) for symbol in symbols
            ]
            signals = await asyncio.gather(*signal_tasks, return_exceptions=True)

            # Filtrera bort None och exceptions
            valid_signals = []
            for i, signal in enumerate(signals):
                if isinstance(signal, SignalResponse):
                    valid_signals.append(signal)
                elif isinstance(signal, Exception):
                    logger.error(
                        f"❌ Signal generation error för {symbols[i]}: {signal}"
                    )

            # Beräkna active signals och summary
            active_signals = len([s for s in valid_signals if s.status == "ACTIVE"])
            summary = {
                "total_signals": len(valid_signals),
                "active_signals": active_signals,
                "symbols_analyzed": len(symbols),
                "success_rate": len(valid_signals) / len(symbols) if symbols else 0,
            }

            result = LiveSignalsResponse(
                timestamp=datetime.now(),
                total_signals=len(valid_signals),
                active_signals=active_signals,
                signals=valid_signals,
                summary=summary,
            )

            logger.info(f"📊 Genererade {len(valid_signals)} enhetliga signaler")
            return result

        except Exception as e:
            logger.error(f"❌ Fel vid generering av alla signaler: {e}")
            return LiveSignalsResponse(
                timestamp=datetime.now(),
                total_signals=0,
                active_signals=0,
                signals=[],
                summary={
                    "total_signals": 0,
                    "active_signals": 0,
                    "symbols_analyzed": 0,
                    "success_rate": 0,
                    "error": str(e),
                },
            )

    async def get_regime_summary(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Hämta regime sammanfattning för alla symboler.

        Används av Market Panel och Strategy endpoints.
        """
        try:
            symbols = await self.get_symbols()
            logger.info(f"📊 Hämtar regime sammanfattning för {len(symbols)} symboler")

            # Hämta regime data för alla symboler
            regime_tasks = [
                self.get_regime_data(symbol, force_refresh) for symbol in symbols
            ]
            regimes = await asyncio.gather(*regime_tasks, return_exceptions=True)

            # Filtrera bort None och exceptions
            valid_regimes = []
            for i, regime in enumerate(regimes):
                if isinstance(regime, dict):
                    valid_regimes.append(regime)
                elif isinstance(regime, Exception):
                    logger.error(f"❌ Regime error för {symbols[i]}: {regime}")

            # Beräkna enhetliga confidence scores via SignalService
            enhanced_regimes = []
            for regime_data in valid_regimes:
                sc = self.signal_service.score(
                    regime=regime_data["regime"],
                    adx_value=regime_data["adx_value"],
                    ema_z_value=regime_data["ema_z_value"],
                )

                enhanced_regimes.append(
                    {
                        **regime_data,
                        "confidence_score": sc.confidence,  # Single Source of Truth
                        "trading_probability": sc.probability,  # Single Source of Truth
                        "recommendation": self._get_recommendation(sc),
                    }
                )

            # Beräkna sammanfattning
            trend_count = len([r for r in enhanced_regimes if r["regime"] == "trend"])
            balanced_count = len(
                [r for r in enhanced_regimes if r["regime"] == "balanced"]
            )
            range_count = len([r for r in enhanced_regimes if r["regime"] == "range"])
            avg_confidence = (
                sum(r["confidence_score"] for r in enhanced_regimes)
                / len(enhanced_regimes)
                if enhanced_regimes
                else 0
            )
            total_trading_prob = sum(r["trading_probability"] for r in enhanced_regimes)

            result = {
                "timestamp": datetime.now().isoformat(),
                "regimes": enhanced_regimes,
                "summary": {
                    "total_symbols": len(enhanced_regimes),
                    "trend_count": trend_count,
                    "balanced_count": balanced_count,
                    "range_count": range_count,
                    "avg_confidence": round(avg_confidence, 2),
                    "total_trading_probability": round(total_trading_prob, 2),
                },
            }

            logger.info(
                f"📊 Regime sammanfattning: {trend_count} trend, {balanced_count} balanced, {range_count} range"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av regime sammanfattning: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "regimes": [],
                "summary": {
                    "total_symbols": 0,
                    "trend_count": 0,
                    "balanced_count": 0,
                    "range_count": 0,
                    "avg_confidence": 0,
                    "total_trading_probability": 0,
                },
            }

    def _determine_signal_type(self, sc: SignalScore) -> str:
        """Bestäm signal-typ baserat på SignalService.score()."""
        if sc.recommendation == "buy":
            return "BUY" if sc.probability > 70 else "WEAK_BUY"
        elif sc.recommendation == "hold":
            return "HOLD"
        else:
            return "SELL" if sc.probability > 70 else "WEAK_SELL"

    def _get_recommendation(self, sc: SignalScore) -> str:
        """Hämta rekommendation baserat på SignalService.score()."""
        if sc.confidence < 30:
            return "LOW_CONFIDENCE"
        elif sc.recommendation == "buy":
            return "STRONG_BUY" if sc.probability > 70 else "BUY"
        elif sc.recommendation == "hold":
            return "HOLD"
        else:
            return "AVOID"

    def _calculate_strength(self, sc: SignalScore) -> str:
        """Beräkna signal-styrka baserat på SignalService.score()."""
        if sc.confidence >= 80:
            return "VERY_STRONG"
        elif sc.confidence >= 60:
            return "STRONG"
        elif sc.confidence >= 40:
            return "MODERATE"
        else:
            return "WEAK"

    def _generate_reason(self, sc: SignalScore, regime_data: dict[str, Any]) -> str:
        """Generera förklaring baserat på SignalService.score() och regime data."""
        _ = sc  # sc används inte direkt här (informationen hämtas från regime_data)
        regime = regime_data.get("regime", "unknown")
        adx = regime_data.get("adx_value", 0)
        ema_z = regime_data.get("ema_z_value", 0)

        reasons = []

        if regime == "trend":
            reasons.append("Trending market")
        elif regime == "range":
            reasons.append("Range-bound market")
        else:
            reasons.append("Balanced market")

        if adx and adx > 25:
            reasons.append(f"Strong momentum (ADX: {adx:.1f})")

        if ema_z and abs(ema_z) > 0.5:
            direction = "bullish" if ema_z > 0 else "bearish"
            reasons.append(f"{direction.capitalize()} EMA trend")

        return " | ".join(reasons) if reasons else "Market analysis"

    def get_cache_stats(self) -> dict[str, Any]:
        """Hämta cache-statistik."""
        return {
            "signal_cache_size": len(self._signal_cache),
            "regime_cache_size": len(self._regime_cache),
            "last_updates": len(self._last_update),
            "oldest_cache": (
                min(self._last_update.values()) if self._last_update else None
            ),
            "newest_cache": (
                max(self._last_update.values()) if self._last_update else None
            ),
        }

    def clear_cache(self) -> None:
        """Rensa alla caches."""
        self._signal_cache.clear()
        self._regime_cache.clear()
        self._last_update.clear()
        logger.info("🗑️ UnifiedSignalService cache rensad")


# Global instans för enhetlig åtkomst
unified_signal_service = UnifiedSignalService()
