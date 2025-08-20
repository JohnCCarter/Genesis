import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from models.signal_models import (
    LiveSignalsResponse,
    SignalHistory,
    SignalResponse,
    SignalStrength,
    SignalThresholds,
)
from services.bitfinex_data import BitfinexDataService
from services.symbols import SymbolService
from utils.logger import get_logger

logger = get_logger(__name__)


class SignalGeneratorService:
    """Service för att generera live trading signals"""

    def __init__(self):
        self.data_service = BitfinexDataService()
        self.symbol_service = SymbolService()

        # Signal cache och historik
        self._signal_cache: dict[str, SignalResponse] = {}
        self._signal_history: list[SignalHistory] = []
        self._last_generation = None

        # Konfiguration
        self.thresholds = SignalThresholds()
        self.strength_weights = SignalStrength()

        # Cache TTL (Time To Live)
        self.cache_ttl = timedelta(minutes=1)  # 1 minut cache

        logger.info("🎯 SignalGeneratorService initialiserad")

    async def generate_live_signals(
        self, symbols: list[str] | None = None, force_refresh: bool = False
    ) -> LiveSignalsResponse:
        """Generera live signals för alla aktiva symboler"""
        try:
            logger.info("🚀 Genererar live signals...")

            # Hämta aktiva symboler om inte specificerade
            if not symbols:
                symbols = await self._get_active_symbols()

            logger.info(f"📋 Använder symboler: {symbols}")

            # Kontrollera cache om inte force refresh
            if not force_refresh and self._is_cache_valid():
                logger.info("📋 Använder cached signals")
                return self._get_cached_response()

            # Generera nya signals
            signals = []
            for symbol in symbols:
                try:
                    signal = await self._generate_signal_for_symbol(symbol)
                    if signal:
                        signals.append(signal)
                        self._signal_cache[symbol] = signal
                        logger.info(f"✅ Genererade signal för {symbol}: {signal.signal_type}")
                    else:
                        logger.warning(f"⚠️ Ingen signal genererad för {symbol}")
                except Exception as e:
                    logger.error(f"❌ Kunde inte generera signal för {symbol}: {e}")
                    continue

            # Uppdatera cache timestamp
            self._last_generation = datetime.now()

            # Skapa response
            response = LiveSignalsResponse(
                timestamp=self._last_generation,
                total_signals=len(signals),
                active_signals=len([s for s in signals if s.signal_type != "HOLD"]),
                signals=signals,
                summary=self._generate_summary(signals),
            )

            logger.info(f"✅ Genererade {len(signals)} signals")
            return response

        except Exception as e:
            logger.error(f"❌ Fel vid signal generation: {e}")
            raise

    async def _generate_signal_for_symbol(self, symbol: str) -> SignalResponse | None:
        """Generera signal för enskild symbol"""
        try:
            # Hämta regime data
            regime_data = await self._get_regime_data(symbol)
            if not regime_data:
                return None

            # Hämta aktuellt pris
            current_price = await self._get_current_price(symbol)

            # Beräkna signal typ
            signal_type = self._determine_signal_type(regime_data)

            # Beräkna signal styrka
            strength = self._evaluate_signal_strength(regime_data)

            # Generera anledning
            reason = self._generate_signal_reason(regime_data, signal_type)

            # Skapa signal response
            signal = SignalResponse(
                symbol=symbol,
                signal_type=signal_type,
                confidence_score=regime_data.get('confidence_score', 0),
                trading_probability=regime_data.get('trading_probability', 0),
                recommendation=regime_data.get('recommendation', 'LOW_CONFIDENCE'),
                timestamp=datetime.now(),
                strength=strength,
                reason=reason,
                current_price=current_price,
                adx_value=regime_data.get('adx_value'),
                ema_z_value=regime_data.get('ema_z_value'),
                regime=regime_data.get('regime'),
            )

            # Spara till historik
            self._save_to_history(signal)

            return signal

        except Exception as e:
            logger.error(f"❌ Fel vid signal generation för {symbol}: {e}")
            return None

    async def _get_regime_data(self, symbol: str) -> dict | None:
        """Hämta regime data för symbol"""
        try:
            # Använd befintlig regime endpoint
            from rest.routes import get_strategy_regime

            regime_data = await get_strategy_regime(symbol, None)

            if regime_data and 'regime' in regime_data:
                # Lägg till confidence scores om de saknas
                confidence = self._calculate_confidence_score(
                    regime_data.get('adx_value'), regime_data.get('ema_z_value')
                )
                trading_prob = self._calculate_trading_probability(
                    regime_data.get('regime'), confidence
                )
                recommendation = self._get_recommendation(
                    regime_data.get('regime'), confidence, trading_prob
                )

                regime_data.update(
                    {
                        'confidence_score': confidence,
                        'trading_probability': trading_prob,
                        'recommendation': recommendation,
                    }
                )
                return regime_data
            return None

        except Exception as e:
            logger.error(f"❌ Kunde inte hämta regime data för {symbol}: {e}")
            return None

    def _calculate_confidence_score(self, adx_value, ema_z_value):
        """Beräknar confidence score baserat på ADX och EMA Z"""
        if not adx_value or not ema_z_value:
            return 50.0  # Default 50% om data saknas

        # ADX-baserad confidence (0-50%)
        adx_confidence = min(adx_value / 50.0, 1.0) * 50

        # EMA Z-baserad confidence (0-50%)
        ema_confidence = min(abs(ema_z_value) / 2.0, 1.0) * 50

        return round(adx_confidence + ema_confidence, 1)

    def _calculate_trading_probability(self, regime, confidence):
        """Beräknar trading probability baserat på regim och confidence"""
        base_probabilities = {
            'trend': 0.85,  # 85% chans att trade trend
            'balanced': 0.60,  # 60% chans att trade balanced
            'range': 0.25,  # 25% chans att trade range
        }

        # Justera baserat på confidence
        confidence_multiplier = confidence / 100.0
        base_prob = base_probabilities.get(regime, 0.5)

        return round(base_prob * confidence_multiplier * 100, 1)

    def _get_recommendation(self, regime, confidence, trading_prob):
        """Ger rekommendation baserat på regim och confidence"""
        if confidence < 30:
            return "LOW_CONFIDENCE"
        elif trading_prob > 70:
            return "STRONG_BUY" if regime == 'trend' else "BUY"
        elif trading_prob > 40:
            return "WEAK_BUY"
        elif trading_prob > 20:
            return "HOLD"
        else:
            return "AVOID"

    async def _get_current_price(self, symbol: str) -> float | None:
        """Hämta aktuellt pris för symbol"""
        try:
            # Använd befintlig data service
            candles = await self.data_service.get_candles(symbol, "1m", limit=1)
            if candles and len(candles) > 0:
                return float(candles[0]['close'])
            return None

        except Exception as e:
            logger.error(f"❌ Kunde inte hämta pris för {symbol}: {e}")
            return None

    def _determine_signal_type(self, regime_data: dict) -> str:
        """Bestäm signal typ baserat på regime data och pris"""
        try:
            # Enkel logik baserat på confidence och probability
            confidence = regime_data.get("confidence_score", 0)
            probability = regime_data.get("trading_probability", 0)

            # Hög confidence + probability = BUY
            if confidence > 70 and probability > 70:
                return "BUY"
            # Låg confidence + probability = SELL
            elif confidence < 30 and probability < 30:
                return "SELL"
            # Annars HOLD
            else:
                return "HOLD"

        except Exception as e:
            logger.error(f"Fel vid signal typ bestämning: {e}")
            return "HOLD"

    def _evaluate_signal_strength(self, regime_data: dict) -> str:
        """Utvärdera signal styrka baserat på confidence och probability"""
        try:
            confidence = regime_data.get('confidence_score', 0)
            trading_prob = regime_data.get('trading_probability', 0)

            # Beräkna kombinerad styrka
            combined_score = (
                confidence * self.strength_weights.confidence_weight
                + trading_prob * self.strength_weights.probability_weight
            )

            # Bestäm styrka baserat på trösklar
            if combined_score >= self.thresholds.strong_signal_min:
                return "STRONG"
            elif combined_score >= self.thresholds.medium_signal_min:
                return "MEDIUM"
            elif combined_score >= self.thresholds.weak_signal_min:
                return "WEAK"
            else:
                return "WEAK"

        except Exception as e:
            logger.error(f"❌ Fel vid signal strength evaluation: {e}")
            return "WEAK"

    def _generate_signal_reason(self, regime_data: dict, signal_type: str) -> str:
        """Generera anledning för signalen"""
        try:
            confidence = regime_data.get("confidence_score", 0)
            probability = regime_data.get("trading_probability", 0)
            regime = regime_data.get("regime", "unknown")

            if signal_type == "BUY":
                return f"Confidence: {confidence:.1f}%, Probability: {probability:.1f}%, Regime: {regime}"
            elif signal_type == "SELL":
                return f"Low confidence: {confidence:.1f}%, Low probability: {probability:.1f}%, Regime: {regime}"
            else:
                return f"Neutral: Confidence: {confidence:.1f}%, Probability: {probability:.1f}%, Regime: {regime}"

        except Exception as e:
            logger.error(f"Fel vid signal reason generation: {e}")
            return "Signal reason unavailable"

    async def _get_active_symbols(self) -> list[str]:
        """Hämta lista av aktiva symboler"""
        try:
            # Använd befintlig symbol service
            symbols = self.symbol_service.get_symbols(test_only=True, fmt="v2")
            logger.info(f"📋 Hämtade {len(symbols)} symboler: {symbols[:5]}...")
            return symbols[:10]  # Begränsa till första 10 för prestanda

        except Exception as e:
            logger.error(f"❌ Kunde inte hämta aktiva symboler: {e}")
            # Returnera statiska test-symboler
            return [
                "TESTBTC:TESTUSD",
                "TESTETH:TESTUSD",
                "TESTADA:TESTUSD",
                "TESTSOL:TESTUSD",
                "TESTDOT:TESTUSD",
            ]

    def _is_cache_valid(self) -> bool:
        """Kontrollera om cache är giltig"""
        if not self._last_generation:
            return False

        return datetime.now() - self._last_generation < self.cache_ttl

    def _get_cached_response(self) -> LiveSignalsResponse:
        """Hämta cached response"""
        signals = list(self._signal_cache.values())
        return LiveSignalsResponse(
            timestamp=self._last_generation,
            total_signals=len(signals),
            active_signals=len([s for s in signals if s.signal_type != "HOLD"]),
            signals=signals,
            summary=self._generate_summary(signals),
        )

    def _generate_summary(self, signals: list[SignalResponse]) -> dict:
        """Generera sammanfattning av signals"""
        try:
            buy_signals = [s for s in signals if s.signal_type == "BUY"]
            sell_signals = [s for s in signals if s.signal_type == "SELL"]
            hold_signals = [s for s in signals if s.signal_type == "HOLD"]

            strong_signals = [s for s in signals if s.strength == "STRONG"]
            medium_signals = [s for s in signals if s.strength == "MEDIUM"]
            weak_signals = [s for s in signals if s.strength == "WEAK"]

            avg_confidence = (
                sum(s.confidence_score for s in signals) / len(signals) if signals else 0
            )
            avg_probability = (
                sum(s.trading_probability for s in signals) / len(signals) if signals else 0
            )

            return {
                "buy_signals": len(buy_signals),
                "sell_signals": len(sell_signals),
                "hold_signals": len(hold_signals),
                "strong_signals": len(strong_signals),
                "medium_signals": len(medium_signals),
                "weak_signals": len(weak_signals),
                "avg_confidence": round(avg_confidence, 1),
                "avg_trading_probability": round(avg_probability, 1),
            }

        except Exception as e:
            logger.error(f"❌ Fel vid summary generation: {e}")
            return {}

    def _save_to_history(self, signal: SignalResponse):
        """Spara signal till historik"""
        try:
            history_entry = SignalHistory(
                signal_id=str(uuid.uuid4()),
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                confidence_score=signal.confidence_score,
                trading_probability=signal.trading_probability,
                timestamp=signal.timestamp,
                status="ACTIVE",
            )

            self._signal_history.append(history_entry)

            # Begränsa historik till senaste 1000 signals
            if len(self._signal_history) > 1000:
                self._signal_history = self._signal_history[-1000:]

        except Exception as e:
            logger.error(f"❌ Fel vid history save: {e}")

    def get_signal_history(self, symbol: str | None = None, limit: int = 50) -> list[SignalHistory]:
        """Hämta signal-historik"""
        try:
            history = self._signal_history

            if symbol:
                history = [h for h in history if h.symbol == symbol]

            # Sortera efter timestamp (nyaste först)
            history.sort(key=lambda x: x.timestamp, reverse=True)

            return history[:limit]

        except Exception as e:
            logger.error(f"❌ Fel vid history retrieval: {e}")
            return []

    def should_generate_signal(self, symbol: str) -> bool:
        """Kontrollera om signal ska genereras för symbol"""
        try:
            # Kontrollera om vi redan har en recent signal
            if symbol in self._signal_cache:
                last_signal = self._signal_cache[symbol]
                time_diff = datetime.now() - last_signal.timestamp

                # Generera ny signal var 5:e minut
                if time_diff < timedelta(minutes=5):
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ Fel vid signal generation check: {e}")
            return True
