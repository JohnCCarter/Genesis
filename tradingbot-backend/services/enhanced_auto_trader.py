from datetime import datetime, timedelta
from typing import Callable

from models.signal_models import SignalResponse, SignalThresholds
from indicators.regime import detect_regime, ema_z
from indicators.adx import adx as adx_series
from services.market_data_facade import get_market_data
from services.signal_service import SignalService as _StdSignalService
from services.performance_tracker import get_performance_tracker
from services.realtime_strategy import RealtimeStrategyService
# from services.signal_generator import SignalGeneratorService  # Cirkulär import - inte använd
from services.trading_integration import TradingIntegrationService
from utils.logger import get_logger

logger = get_logger(__name__)

# Singleton instance
_enhanced_trader_instance = None


class EnhancedAutoTrader:
    """Enhanced auto-trader som kombinerar live signals med befintligt auto-trading"""

    def __init__(self):
        # Använd standardiserad SignalService (SignalScore) som primär källa
        # SignalGeneratorService används enbart som transport/aggregation om behövs
        self.signal_service = _StdSignalService()
        self.trading_integration = TradingIntegrationService()
        self.realtime_strategy = RealtimeStrategyService()
        self.performance_tracker = get_performance_tracker()

        # Konfiguration
        self.thresholds = SignalThresholds()

        # Aktiva symboler och deras status
        self.active_symbols: dict[str, dict] = {}

        # Signal cache för att undvika duplicerade trades
        self._last_signals: dict[str, SignalResponse] = {}
        self._last_trade_time: dict[str, datetime] = {}

        # Minsta tid mellan trades (5 minuter)
        self.min_trade_interval = timedelta(minutes=5)

        logger.info("🚀 EnhancedAutoTrader initialiserad")

    @classmethod
    def get_instance(cls) -> "EnhancedAutoTrader":
        """Hämta singleton instance"""
        global _enhanced_trader_instance
        if _enhanced_trader_instance is None:
            _enhanced_trader_instance = cls()
        return _enhanced_trader_instance

    async def start_enhanced_trading(self, symbol: str, callback: Callable | None = None):
        """Starta enhanced auto-trading för en symbol"""
        try:
            if symbol in self.active_symbols:
                logger.warning(f"⚠️ {symbol} handlas redan med enhanced trading")
                return

            # Spara callback
            if callback:
                self.active_symbols[symbol] = {"callback": callback}
            else:
                self.active_symbols[symbol] = {}

            # Starta realtidsövervakning för snabb execution
            await self.realtime_strategy.start_monitoring(symbol, self._handle_realtime_signal)

            # Hämta initial signal
            await self._get_enhanced_signal(symbol)

            logger.info(f"🤖 Startade enhanced auto-trading för {symbol}")

        except Exception as e:
            logger.error(f"❌ Fel vid start av enhanced trading för {symbol}: {e}")

    async def stop_enhanced_trading(self, symbol: str):
        """Stoppa enhanced auto-trading för en symbol"""
        try:
            if symbol in self.active_symbols:
                del self.active_symbols[symbol]

                # Stoppa realtidsövervakning
                await self.realtime_strategy.stop_monitoring(symbol)

                logger.info(f"🛑 Stoppade enhanced auto-trading för {symbol}")
            else:
                logger.warning(f"⚠️ {symbol} handlades inte med enhanced trading")

        except Exception as e:
            logger.error(f"❌ Fel vid stopp av enhanced trading för {symbol}: {e}")

    async def _handle_realtime_signal(self, result: dict):
        """Hantera realtids signal från befintligt system"""
        try:
            symbol = result.get("symbol")
            if not symbol or symbol not in self.active_symbols:
                return

            # Kontrollera om vi redan handlat nyligen
            if not self._can_trade_now(symbol):
                return

            # Hämta enhanced signal med confidence scores
            enhanced_signal = await self._get_enhanced_signal(symbol)
            if not enhanced_signal:
                return

            # Beslut baserat på enhanced signal
            should_trade = self._should_execute_trade(enhanced_signal)
            if not should_trade:
                logger.info(
                    f"⏸️ Ingen trade för {symbol}: {enhanced_signal.signal_type} (confidence: {enhanced_signal.confidence_score}%)"
                )
                return

            # Använd befintligt trading system för execution
            await self._execute_enhanced_trade(symbol, enhanced_signal, result)

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av realtids signal: {e}")

    async def _get_enhanced_signal(self, symbol: str) -> SignalResponse | None:
        """Hämta enhanced signal med confidence scores"""
        try:
            # Hämta regim + indikatorer lokalt (undvik beroende på REST-routes)
            regime_data = await self._get_regime_data_local(symbol)
            if not regime_data or "regime" not in regime_data:
                return None

            sc = self.signal_service.score(
                regime=regime_data.get("regime"),
                adx_value=regime_data.get("adx_value"),
                ema_z_value=regime_data.get("ema_z_value"),
                features={"symbol": symbol},
            )

            # Mappa SignalScore -> SignalResponse (befintlig modell)
            signal = SignalResponse(
                symbol=symbol,
                signal_type=(
                    "BUY" if sc.recommendation == "buy" else ("SELL" if sc.recommendation == "sell" else "HOLD")
                ),
                confidence_score=sc.confidence,
                trading_probability=sc.probability,
                recommendation=(
                    "STRONG_BUY"
                    if sc.recommendation == "buy" and sc.probability > 70
                    else ("BUY" if sc.recommendation == "buy" else ("HOLD" if sc.recommendation == "hold" else "AVOID"))
                ),
                timestamp=datetime.now(),
                strength=(
                    "STRONG"
                    if sc.confidence >= self.thresholds.strong_signal_min
                    else ("MEDIUM" if sc.confidence >= self.thresholds.medium_signal_min else "WEAK")
                ),
                reason=f"Confidence: {sc.confidence:.1f}%, Probability: {sc.probability:.1f}%, Source: {sc.source}",
                current_price=None,
                adx_value=regime_data.get("adx_value"),
                ema_z_value=regime_data.get("ema_z_value"),
                regime=regime_data.get("regime"),
            )

            self._last_signals[symbol] = signal
            return signal

            return None

        except Exception as e:
            logger.error(f"❌ Kunde inte hämta enhanced signal för {symbol}: {e}")
            return None

    def _should_execute_trade(self, signal: SignalResponse) -> bool:
        """Beslut om trade ska utföras baserat på enhanced signal"""
        try:
            # För låg confidence = ingen trade
            if signal.confidence_score < self.thresholds.manual_confirm_min:
                return False

            # Endast BUY signals för nu (kan utökas till SELL)
            if signal.signal_type != "BUY":
                return False

            # Automatisk trade för höga confidence scores
            if signal.confidence_score >= self.thresholds.auto_execute_min:
                return True

            # Manuell bekräftelse för medium confidence
            if signal.confidence_score >= self.thresholds.manual_confirm_min:
                # Här kan vi lägga till manuell bekräftelse logik
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Fel vid trade beslut: {e}")
            return False

    async def _execute_enhanced_trade(self, symbol: str, signal: SignalResponse, realtime_result: dict):
        """Utför trade med enhanced signal men befintligt execution system"""
        try:
            # Beräkna position storlek baserat på confidence
            position_size = self._calculate_enhanced_position_size(signal)

            # Använd befintligt trading integration för execution
            trade_result = await self.trading_integration.execute_trading_signal(
                symbol,
                {
                    **realtime_result,
                    "enhanced_signal": signal.dict(),
                    "position_size": position_size,
                    "confidence_score": signal.confidence_score,
                    "trading_probability": signal.trading_probability,
                },
            )

            # Uppdatera trade timestamp
            self._last_trade_time[symbol] = datetime.now()

            # Registrera trade i performance tracker
            trade_id = self.performance_tracker.record_trade(symbol, signal, trade_result, datetime.now())

            # Logga resultat
            logger.info(
                f"✅ Enhanced trade utförd för {symbol}: {signal.signal_type} "
                f"(confidence: {signal.confidence_score}%, size: {position_size}, trade_id: {trade_id})"
            )

            # Anropa callback om det finns
            if symbol in self.active_symbols and "callback" in self.active_symbols[symbol]:
                callback = self.active_symbols[symbol]["callback"]
                if callback:
                    await callback(trade_result)

        except Exception as e:
            logger.error(f"❌ Fel vid enhanced trade execution för {symbol}: {e}")

    def _calculate_enhanced_position_size(self, signal: SignalResponse) -> float:
        """Beräkna position storlek baserat på confidence score"""
        try:
            # Bas position storlek (0.001 BTC)
            base_size = 0.001

            # Justera baserat på confidence score
            confidence_multiplier = signal.confidence_score / 100.0

            # Justera baserat på signal styrka
            strength_multiplier = {"STRONG": 1.5, "MEDIUM": 1.0, "WEAK": 0.5}.get(signal.strength, 1.0)

            # Justera baserat på trading probability
            probability_multiplier = signal.trading_probability / 100.0

            # Kombinera alla faktorer
            final_size = base_size * confidence_multiplier * strength_multiplier * probability_multiplier

            # Begränsa till rimliga gränser
            final_size = max(0.0001, min(0.01, final_size))

            return round(final_size, 6)

        except Exception as e:
            logger.error(f"❌ Fel vid position size beräkning: {e}")
            return 0.001  # Fallback

    def _can_trade_now(self, symbol: str) -> bool:
        """Kontrollera om vi kan handla nu för symbolen"""
        try:
            if symbol not in self._last_trade_time:
                return True

            time_since_last_trade = datetime.now() - self._last_trade_time[symbol]
            return time_since_last_trade >= self.min_trade_interval

        except Exception as e:
            logger.error(f"❌ Fel vid trade timing check: {e}")
            return True

    async def get_enhanced_status(self) -> dict:
        """Hämta status för enhanced auto-trading"""
        try:
            status = {
                "active_symbols": list(self.active_symbols.keys()),
                "last_signals": {},
                "last_trades": {},
            }

            # Lägg till senaste signals
            for symbol, signal in self._last_signals.items():
                status["last_signals"][symbol] = {
                    "signal_type": signal.signal_type,
                    "confidence_score": signal.confidence_score,
                    "trading_probability": signal.trading_probability,
                    "strength": signal.strength,
                    "timestamp": signal.timestamp.isoformat(),
                }

            # Lägg till senaste trades
            for symbol, trade_time in self._last_trade_time.items():
                status["last_trades"][symbol] = trade_time.isoformat()

            return status

        except Exception as e:
            logger.error(f"❌ Fel vid status hämtning: {e}")
            return {"error": "An internal error occurred, please try again later."}

    async def _get_regime_data_local(self, symbol: str) -> dict | None:
        """Beräkna regim och indikatorvärden utan REST-beroende (för att undvika cirkulär import).

        Hämtar candles via MarketDataFacade (WS-first, REST-fallback), beräknar ADX och EMA-Z,
        och returnerar struktur som matchar REST-endpointens schema.
        """
        try:
            data = get_market_data()
            candles = await data.get_candles(symbol, timeframe="1m", limit=100)
            if not candles or len(candles) < 20:
                return None

            highs = [float(c[3]) for c in candles if len(c) >= 4]
            lows = [float(c[4]) for c in candles if len(c) >= 5]
            closes = [float(c[2]) for c in candles if len(c) >= 3]
            if len(highs) < 20 or len(lows) < 20 or len(closes) < 20:
                return None

            cfg = {
                "ADX_PERIOD": 14,
                "ADX_HIGH": 30,
                "ADX_LOW": 15,
                "SLOPE_Z_HIGH": 1.0,
                "SLOPE_Z_LOW": 0.5,
            }
            regime = detect_regime(highs, lows, closes, cfg)

            # Beräkna indikatorvärden som REST brukar returnera
            adx_vals = adx_series(highs, lows, closes, period=cfg["ADX_PERIOD"])
            adx_value = float(adx_vals[-1]) if adx_vals else None
            ez_vals = ema_z(closes, fast=3, slow=7, z_win=200)
            ema_z_value = float(ez_vals[-1]) if ez_vals else None

            return {
                "symbol": symbol,
                "regime": regime,
                "adx_value": adx_value,
                "ema_z_value": ema_z_value,
            }
        except Exception as e:
            logger.error(f"❌ Fel vid lokal regim-beräkning för {symbol}: {e}")
            return None

    async def stop_all_enhanced_trading(self):
        """Stoppa all enhanced auto-trading"""
        try:
            symbols_to_stop = list(self.active_symbols.keys())
            for symbol in symbols_to_stop:
                await self.stop_enhanced_trading(symbol)

            logger.info(f"🛑 Stoppade all enhanced auto-trading ({len(symbols_to_stop)} symboler)")

        except Exception as e:
            logger.error(f"❌ Fel vid stopp av all enhanced trading: {e}")
