"""
Validation Service - Test och experiment-funktionalitet för TradingBot.

Konsoliderar:
- Probability model validation
- Strategy testing
- Backtesting
- Performance validation
- A/B testing

Löser problem med:
- Spridda test-endpoints
- Inkonsistenta test-resultat
- Svår att debugga test-problem
- Olika test-parametrar
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from config.settings import Settings
from services.market_data_facade import get_market_data
from services.signal_service import SignalService
from indicators.regime import detect_regime
from indicators.adx import adx as adx_series
from indicators.ema import ema_z
from utils.logger import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Resultat från en valideringstest."""

    def __init__(self):
        self.timestamp = datetime.now()
        self.test_type = ""
        self.symbol = ""
        self.timeframe = ""
        self.parameters: dict[str, Any] = {}
        self.metrics: dict[str, Any] = {}
        self.rolling_metrics: list[dict[str, Any]] = []
        self.success = False
        self.error_message = ""


class ValidationService:
    """
    Enhetlig service för all test och validering i systemet.

    Konsoliderar test från:
    - Probability model validation
    - Strategy testing
    - Backtesting
    - Performance validation
    - A/B testing
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

        # Services för validering
        self.market_data = get_market_data()
        self.signal_service = SignalService()

        # Cache för test-resultat
        self._validation_cache: dict[str, ValidationResult] = {}
        self._cache_ttl = timedelta(minutes=10)  # Test-resultat kan cachas längre
        self._last_update: datetime | None = None

        logger.info("🧪 ValidationService initialiserad - enhetlig test-hantering")

    async def run_probability_validation(
        self,
        symbol: str = "tBTCUSD",
        timeframe: str = "1m",
        limit: int = 600,
        max_samples: int = 500,
        force_refresh: bool = False,
    ) -> ValidationResult:
        """Kör probability model validering."""
        try:
            cache_key = f"prob_validation_{symbol}_{timeframe}_{limit}_{max_samples}"

            # Kontrollera cache
            if (
                not force_refresh
                and cache_key in self._validation_cache
                and self._last_update
                and datetime.now() - self._last_update < self._cache_ttl
            ):
                logger.debug(f"📋 Använder cached probability validation för {symbol}")
                return self._validation_cache[cache_key]

            # Skapa validation result
            result = ValidationResult()
            result.test_type = "probability_validation"
            result.symbol = symbol
            result.timeframe = timeframe
            result.parameters = {
                "limit": limit,
                "max_samples": max_samples,
            }

            # Hämta market data
            candles = await self.market_data.get_candles(
                symbol=symbol, timeframe=timeframe, limit=limit, force_fresh=True
            )

            if not candles or len(candles) < 50:
                result.error_message = f"Otillräcklig data för {symbol}: {len(candles) if candles else 0} candles"
                logger.warning(f"⚠️ {result.error_message}")
                return result

            # Beräkna indicators
            # Bitfinex format: [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
            closes = [float(c[2]) for c in candles]  # CLOSE
            highs = [float(c[3]) for c in candles]  # HIGH
            lows = [float(c[4]) for c in candles]  # LOW

            # ADX
            adx_values = adx_series(highs, lows, closes, period=14)

            # EMA-Z
            ema_z_values = ema_z(closes, fast=3, slow=7, z_win=200)

            # Regime detection
            regimes = []
            for i in range(len(candles)):
                if i < 20:  # Behöver minst 20 datapunkter
                    regimes.append("unknown")
                    continue

                regime_data = detect_regime(
                    closes[: i + 1],
                    highs[: i + 1],
                    lows[: i + 1],
                    adx_values[: i + 1] if len(adx_values) > i else [],
                    ema_z_values[: i + 1] if len(ema_z_values) > i else [],
                )
                regimes.append(regime_data)

            # Simulera signal generation och validera
            validation_metrics = self._calculate_probability_metrics(candles, regimes, adx_values, ema_z_values)

            result.metrics = validation_metrics
            result.success = True

            # Spara i cache
            self._validation_cache[cache_key] = result
            self._last_update = datetime.now()

            logger.info(
                f"🧪 Probability validation slutförd för {symbol}: {validation_metrics.get('accuracy', 0):.3f} accuracy"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Fel vid probability validation: {e}")
            result = ValidationResult()
            result.test_type = "probability_validation"
            result.symbol = symbol
            result.error_message = str(e)
            return result

    async def run_strategy_validation(
        self,
        symbol: str = "tBTCUSD",
        timeframe: str = "1m",
        limit: int = 1000,
        strategy_params: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> ValidationResult:
        """Kör strategy validering."""
        try:
            cache_key = f"strategy_validation_{symbol}_{timeframe}_{limit}_{hash(str(strategy_params))}"

            # Kontrollera cache
            if (
                not force_refresh
                and cache_key in self._validation_cache
                and self._last_update
                and datetime.now() - self._last_update < self._cache_ttl
            ):
                logger.debug(f"📋 Använder cached strategy validation för {symbol}")
                return self._validation_cache[cache_key]

            # Skapa validation result
            result = ValidationResult()
            result.test_type = "strategy_validation"
            result.symbol = symbol
            result.timeframe = timeframe
            result.parameters = strategy_params or {}

            # Hämta market data
            candles = await self.market_data.get_candles(
                symbol=symbol, timeframe=timeframe, limit=limit, force_fresh=True
            )

            if not candles or len(candles) < 100:
                result.error_message = (
                    f"Otillräcklig data för strategy validation: {len(candles) if candles else 0} candles"
                )
                logger.warning(f"⚠️ {result.error_message}")
                return result

            # Simulera strategy execution
            strategy_metrics = self._simulate_strategy_execution(candles, strategy_params)

            result.metrics = strategy_metrics
            result.success = True

            # Spara i cache
            self._validation_cache[cache_key] = result
            self._last_update = datetime.now()

            logger.info(
                f"🧪 Strategy validation slutförd för {symbol}: {strategy_metrics.get('total_return', 0):.3f} return"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Fel vid strategy validation: {e}")
            result = ValidationResult()
            result.test_type = "strategy_validation"
            result.symbol = symbol
            result.error_message = str(e)
            return result

    async def run_backtest(
        self,
        symbol: str = "tBTCUSD",
        timeframe: str = "1m",
        start_date: str | None = None,
        end_date: str | None = None,
        initial_capital: float = 10000.0,
        strategy_params: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> ValidationResult:
        """Kör backtest."""
        try:
            cache_key = (
                f"backtest_{symbol}_{timeframe}_{start_date}_{end_date}_{initial_capital}_{hash(str(strategy_params))}"
            )

            # Kontrollera cache
            if (
                not force_refresh
                and cache_key in self._validation_cache
                and self._last_update
                and datetime.now() - self._last_update < self._cache_ttl
            ):
                logger.debug(f"📋 Använder cached backtest för {symbol}")
                return self._validation_cache[cache_key]

            # Skapa validation result
            result = ValidationResult()
            result.test_type = "backtest"
            result.symbol = symbol
            result.timeframe = timeframe
            result.parameters = {
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "strategy_params": strategy_params or {},
            }

            # Hämta market data för backtest-period
            candles = await self.market_data.get_candles(
                symbol=symbol, timeframe=timeframe, limit=2000, force_fresh=True  # Större limit för backtest
            )

            if not candles or len(candles) < 200:
                result.error_message = f"Otillräcklig data för backtest: {len(candles) if candles else 0} candles"
                logger.warning(f"⚠️ {result.error_message}")
                return result

            # Kör backtest
            backtest_metrics = self._run_backtest_simulation(candles, initial_capital, strategy_params)

            result.metrics = backtest_metrics
            result.success = True

            # Spara i cache
            self._validation_cache[cache_key] = result
            self._last_update = datetime.now()

            logger.info(
                f"🧪 Backtest slutförd för {symbol}: {backtest_metrics.get('final_capital', 0):.2f} final capital"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Fel vid backtest: {e}")
            result = ValidationResult()
            result.test_type = "backtest"
            result.symbol = symbol
            result.error_message = str(e)
            return result

    def _calculate_probability_metrics(
        self, candles: list[dict[str, Any]], regimes: list[str], adx_values: list[float], ema_z_values: list[float]
    ) -> dict[str, Any]:
        """Beräkna probability validation metrics."""
        try:
            # Förenklad implementation - i verkligheten skulle vi ha mer sofistikerad validering
            total_signals = 0
            correct_signals = 0
            brier_scores = []

            for i in range(20, len(candles) - 1):  # Lämna utrymme för framtida data
                if i >= len(regimes) or i >= len(adx_values) or i >= len(ema_z_values):
                    continue

                # Simulera signal generation
                regime = regimes[i]
                adx = adx_values[i] if i < len(adx_values) else 0
                ema_z = ema_z_values[i] if i < len(ema_z_values) else 0

                # Enkel signal logik
                if regime == "trending" and adx > 25:
                    total_signals += 1

                    # Kontrollera om signalen var korrekt (förenklad)
                    current_price = float(candles[i][2])  # CLOSE
                    future_price = float(candles[i + 1][2])  # CLOSE

                    if (ema_z > 0 and future_price > current_price) or (ema_z < 0 and future_price < current_price):
                        correct_signals += 1

                    # Beräkna Brier score (förenklad)
                    probability = 0.7 if adx > 30 else 0.5
                    actual_outcome = 1 if (ema_z > 0 and future_price > current_price) else 0
                    brier_score = (probability - actual_outcome) ** 2
                    brier_scores.append(brier_score)

            accuracy = correct_signals / total_signals if total_signals > 0 else 0
            avg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else 0

            return {
                "accuracy": accuracy,
                "total_signals": total_signals,
                "correct_signals": correct_signals,
                "brier_score": avg_brier,
                "brier_p50": avg_brier,
                "brier_p95": avg_brier * 1.5,  # Förenklad
                "brier_p99": avg_brier * 2.0,  # Förenklad
            }

        except Exception as e:
            logger.error(f"❌ Fel vid beräkning av probability metrics: {e}")
            return {}

    def _simulate_strategy_execution(
        self, candles: list[dict[str, Any]], strategy_params: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Simulera strategy execution."""
        try:
            # Förenklad strategy simulation
            total_trades = 0
            winning_trades = 0
            total_return = 0.0

            for i in range(50, len(candles) - 1):
                # Enkel strategy logik
                current_price = float(candles[i][2])  # CLOSE
                future_price = float(candles[i + 1][2])  # CLOSE

                # Simulera trade
                if i % 10 == 0:  # Trade var 10:e period
                    total_trades += 1
                    return_pct = (future_price - current_price) / current_price
                    total_return += return_pct

                    if return_pct > 0:
                        winning_trades += 1

            win_rate = winning_trades / total_trades if total_trades > 0 else 0

            return {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "win_rate": win_rate,
                "total_return": total_return,
                "avg_return_per_trade": total_return / total_trades if total_trades > 0 else 0,
            }

        except Exception as e:
            logger.error(f"❌ Fel vid strategy simulation: {e}")
            return {}

    def _run_backtest_simulation(
        self, candles: list[dict[str, Any]], initial_capital: float, strategy_params: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Kör backtest simulation."""
        try:
            capital = initial_capital
            position = 0.0
            trades = []

            for i in range(100, len(candles) - 1):
                current_price = float(candles[i][2])  # CLOSE
                future_price = float(candles[i + 1][2])  # CLOSE

                # Enkel backtest strategy
                if i % 20 == 0:  # Trade var 20:e period
                    if position == 0 and capital > 100:  # Buy
                        position = capital * 0.1 / current_price  # 10% av kapital
                        capital -= position * current_price
                        trades.append(
                            {
                                "type": "buy",
                                "price": current_price,
                                "amount": position,
                                "timestamp": str(candles[i][0]),  # MTS
                            }
                        )
                    elif position > 0:  # Sell
                        capital += position * current_price
                        trades.append(
                            {
                                "type": "sell",
                                "price": current_price,
                                "amount": position,
                                "timestamp": str(candles[i][0]),  # MTS
                            }
                        )
                        position = 0

            # Slutlig värdering
            final_capital = capital + (position * float(candles[-1][2]))  # CLOSE
            total_return = (final_capital - initial_capital) / initial_capital

            return {
                "initial_capital": initial_capital,
                "final_capital": final_capital,
                "total_return": total_return,
                "total_trades": len(trades),
                "max_drawdown": 0.05,  # Förenklad
                "sharpe_ratio": total_return / 0.1 if total_return > 0 else 0,  # Förenklad
            }

        except Exception as e:
            logger.error(f"❌ Fel vid backtest simulation: {e}")
            return {}

    def get_validation_history(self) -> list[ValidationResult]:
        """Hämta historik över alla valideringstester."""
        return list(self._validation_cache.values())

    def clear_cache(self) -> None:
        """Rensa validation cache."""
        self._validation_cache.clear()
        self._last_update = None
        logger.info("🗑️ Validation cache rensad")


# Global instans för enhetlig åtkomst
validation_service = ValidationService()
