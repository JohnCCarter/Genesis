"""
Regime Ablation Service - A/B-testning och gate switching för tradingregimer.

Implementerar:
- A/B-testning av regime switching
- Expectancy-baserad gate
- Regime performance tracking
- Dynamic regime selection
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from utils.logger import get_logger

from config.settings import Settings
from services.performance import PerformanceService

logger = get_logger(__name__)


@dataclass
class RegimeConfig:
    """Konfiguration för ett regime."""

    name: str
    enabled: bool = True
    weight: float = 1.0
    min_trades: int = 10  # Minsta antal trades för att bedöma performance
    lookback_days: int = 30  # Antal dagar att titta tillbaka
    expectancy_threshold: float = 0.001  # Minsta expectancy för att aktivera
    max_drawdown_threshold: float = 0.05  # Max drawdown innan deaktivering


@dataclass
class RegimePerformance:
    """Performance data för ett regime."""

    regime_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    avg_win: float
    avg_loss: float
    hit_rate: float
    expectancy: float
    max_drawdown: float
    sharpe_ratio: float
    last_updated: datetime


class RegimeAblationService:
    """Service för regime ablation och gate switching."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.config_file = "config/regime_ablation.json"
        self.performance_file = "config/regime_performance.json"
        self.performance_service = PerformanceService(self.settings)

        # Ladda eller skapa default konfiguration
        self.regimes = self._load_regimes()
        self.performance_data = self._load_performance()

        logger.info("🔬 RegimeAblationService initialiserad")

    def _load_regimes(self) -> dict[str, RegimeConfig]:
        """Ladda regime konfiguration från fil eller skapa defaults."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, encoding="utf-8") as f:
                    data = json.load(f)

                regimes = {}
                for name, config_data in data.items():
                    regimes[name] = RegimeConfig(**config_data)

                logger.info(f"📋 Laddade regime konfiguration från {self.config_file}")
                return regimes
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte ladda regime konfiguration: {e}")

        # Default regimes
        default_regimes = {
            "momentum": RegimeConfig(
                name="momentum",
                enabled=True,
                weight=1.0,
                min_trades=10,
                lookback_days=30,
                expectancy_threshold=0.001,
                max_drawdown_threshold=0.05,
            ),
            "mean_reversion": RegimeConfig(
                name="mean_reversion",
                enabled=True,
                weight=1.0,
                min_trades=10,
                lookback_days=30,
                expectancy_threshold=0.001,
                max_drawdown_threshold=0.05,
            ),
            "volatility_breakout": RegimeConfig(
                name="volatility_breakout",
                enabled=True,
                weight=1.0,
                min_trades=10,
                lookback_days=30,
                expectancy_threshold=0.001,
                max_drawdown_threshold=0.05,
            ),
            "trend_following": RegimeConfig(
                name="trend_following",
                enabled=True,
                weight=1.0,
                min_trades=10,
                lookback_days=30,
                expectancy_threshold=0.001,
                max_drawdown_threshold=0.05,
            ),
        }

        self._save_regimes(default_regimes)
        return default_regimes

    def _save_regimes(self, regimes: dict[str, RegimeConfig]) -> None:
        """Spara regime konfiguration till fil."""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            data = {name: config.__dict__ for name, config in regimes.items()}
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Kunde inte spara regime konfiguration: {e}")

    def _load_performance(self) -> dict[str, RegimePerformance]:
        """Ladda performance data från fil."""
        try:
            if os.path.exists(self.performance_file):
                with open(self.performance_file, encoding="utf-8") as f:
                    data = json.load(f)

                performance = {}
                for name, perf_data in data.items():
                    perf_data["last_updated"] = datetime.fromisoformat(perf_data["last_updated"])
                    performance[name] = RegimePerformance(**perf_data)

                return performance
        except Exception as e:
            logger.warning(f"⚠️ Kunde inte ladda performance data: {e}")

        return {}

    def _save_performance(self, performance: dict[str, RegimePerformance]) -> None:
        """Spara performance data till fil."""
        try:
            os.makedirs(os.path.dirname(self.performance_file), exist_ok=True)
            data = {name: perf.__dict__ for name, perf in performance.items()}
            # Konvertera datetime till string för JSON serialisering
            for name in data:
                data[name]["last_updated"] = data[name]["last_updated"].isoformat()

            with open(self.performance_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Kunde inte spara performance data: {e}")

    def calculate_regime_performance(self, regime_name: str) -> RegimePerformance | None:
        """
        Beräkna performance för ett specifikt regime.

        Args:
            regime_name: Namn på regimet

        Returns:
            RegimePerformance eller None om inte tillräckligt med data
        """
        try:
            # Hämta trades för detta regime från performance service
            # Detta är en förenklad implementation - i verkligheten skulle vi
            # filtrera trades baserat på regime metadata

            # Placeholder - ersätt med riktig implementation
            trades = []  # Hämta trades för detta regime

            if len(trades) < self.regimes[regime_name].min_trades:
                return None

            # Beräkna metrics
            winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
            losing_trades = [t for t in trades if t.get("pnl", 0) < 0]

            total_trades = len(trades)
            winning_count = len(winning_trades)
            losing_count = len(losing_trades)

            if total_trades == 0:
                return None

            total_pnl = sum(t.get("pnl", 0) for t in trades)
            hit_rate = winning_count / total_trades

            avg_win = sum(t.get("pnl", 0) for t in winning_trades) / winning_count if winning_count > 0 else 0.0
            avg_loss = abs(sum(t.get("pnl", 0) for t in losing_trades) / losing_count) if losing_count > 0 else 0.0

            # Expectancy = (hit_rate * avg_win) - ((1 - hit_rate) * avg_loss)
            expectancy = (hit_rate * avg_win) - ((1 - hit_rate) * avg_loss)

            # Beräkna drawdown och Sharpe ratio (förenklad)
            max_drawdown = 0.0  # Placeholder
            sharpe_ratio = 0.0  # Placeholder

            return RegimePerformance(
                regime_name=regime_name,
                total_trades=total_trades,
                winning_trades=winning_count,
                losing_trades=losing_count,
                total_pnl=total_pnl,
                avg_win=avg_win,
                avg_loss=avg_loss,
                hit_rate=hit_rate,
                expectancy=expectancy,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                last_updated=datetime.now(),
            )

        except Exception as e:
            logger.error(f"❌ Kunde inte beräkna performance för regime {regime_name}: {e}")
            return None

    def update_regime_performance(self, regime_name: str) -> bool:
        """
        Uppdatera performance för ett regime.

        Args:
            regime_name: Namn på regimet

        Returns:
            bool: True om uppdatering lyckades
        """
        try:
            performance = self.calculate_regime_performance(regime_name)
            if performance:
                self.performance_data[regime_name] = performance
                self._save_performance(self.performance_data)
                logger.info(f"📊 Performance uppdaterad för regime {regime_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Kunde inte uppdatera performance för regime {regime_name}: {e}")
            return False

    def get_active_regimes(self) -> list[str]:
        """
        Hämta aktiva regimer baserat på performance gates.

        Returns:
            List[str]: Lista med aktiva regime namn
        """
        active_regimes = []

        for regime_name, config in self.regimes.items():
            if not config.enabled:
                continue

            performance = self.performance_data.get(regime_name)
            if not performance:
                # Om ingen performance data finns, aktivera regimet
                active_regimes.append(regime_name)
                continue

            # Kontrollera expectancy gate
            if performance.expectancy < config.expectancy_threshold:
                logger.info(f"🚫 Regime {regime_name} deaktiverat pga låg expectancy: {performance.expectancy:.6f}")
                continue

            # Kontrollera drawdown gate
            if performance.max_drawdown > config.max_drawdown_threshold:
                logger.info(f"🚫 Regime {regime_name} deaktiverat pga hög drawdown: {performance.max_drawdown:.2%}")
                continue

            # Kontrollera minsta antal trades
            if performance.total_trades < config.min_trades:
                logger.info(
                    f"⏳ Regime {regime_name} väntar på fler trades: {performance.total_trades}/{config.min_trades}"
                )
                continue

            active_regimes.append(regime_name)

        return active_regimes

    def get_regime_weights(self) -> dict[str, float]:
        """
        Hämta vikter för aktiva regimer baserat på performance.

        Returns:
            Dict[str, float]: Regime namn -> vikt
        """
        active_regimes = self.get_active_regimes()

        if not active_regimes:
            # Om inga aktiva regimer, returnera default
            return {name: config.weight for name, config in self.regimes.items() if config.enabled}

        # Beräkna vikter baserat på expectancy
        total_expectancy = 0.0
        regime_expectancies = {}

        for regime_name in active_regimes:
            performance = self.performance_data.get(regime_name)
            if performance and performance.expectancy > 0:
                regime_expectancies[regime_name] = performance.expectancy
                total_expectancy += performance.expectancy

        if total_expectancy == 0:
            # Om ingen positiv expectancy, använd lika vikter
            weight = 1.0 / len(active_regimes)
            return {name: weight for name in active_regimes}

        # Normalisera vikter baserat på expectancy
        weights = {}
        for regime_name in active_regimes:
            expectancy = regime_expectancies.get(regime_name, 0.0)
            weight = expectancy / total_expectancy
            weights[regime_name] = weight

        return weights

    def run_ablation_test(self, test_duration_days: int = 7) -> dict[str, Any]:
        """
        Kör A/B-test av regime switching.

        Args:
            test_duration_days: Testlängd i dagar

        Returns:
            Dict med testresultat
        """
        try:
            # Simulera A/B-test genom att jämföra olika regime kombinationer
            test_results = {}

            # Test 1: Alla regimer aktiva
            all_regimes = list(self.regimes.keys())
            test_results["all_regimes"] = self._simulate_regime_performance(all_regimes)

            # Test 2: Endast momentum
            test_results["momentum_only"] = self._simulate_regime_performance(["momentum"])

            # Test 3: Endast mean reversion
            test_results["mean_reversion_only"] = self._simulate_regime_performance(["mean_reversion"])

            # Test 4: Momentum + mean reversion
            test_results["momentum_mean_reversion"] = self._simulate_regime_performance(["momentum", "mean_reversion"])

            # Jämför resultat
            best_performance = max(test_results.values(), key=lambda x: x.get("total_pnl", 0))
            best_config = [k for k, v in test_results.items() if v == best_performance][0]

            return {
                "test_results": test_results,
                "best_config": best_config,
                "best_performance": best_performance,
                "recommendation": f"Använd {best_config} konfiguration",
                "test_duration_days": test_duration_days,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Fel vid ablation test: {e}")
            return {"error": str(e)}

    def _simulate_regime_performance(self, regime_names: list[str]) -> dict[str, Any]:
        """
        Simulera performance för en regime kombination.

        Args:
            regime_names: Lista med regime namn att testa

        Returns:
            Dict med simulerad performance
        """
        # Detta är en förenklad simulation
        # I verkligheten skulle vi köra backtest med dessa regimer

        total_pnl = 0.0
        total_trades = 0
        winning_trades = 0

        for regime_name in regime_names:
            performance = self.performance_data.get(regime_name)
            if performance:
                total_pnl += performance.total_pnl
                total_trades += performance.total_trades
                winning_trades += performance.winning_trades

        hit_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        return {
            "regimes": regime_names,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "hit_rate": hit_rate,
            "avg_pnl_per_trade": total_pnl / total_trades if total_trades > 0 else 0.0,
        }

    def update_regime_config(self, regime_name: str, config: dict[str, Any]) -> bool:
        """
        Uppdatera konfiguration för ett regime.

        Args:
            regime_name: Namn på regimet
            config: Ny konfiguration

        Returns:
            bool: True om uppdatering lyckades
        """
        try:
            if regime_name in self.regimes:
                current_config = self.regimes[regime_name]

                # Uppdatera endast tillåtna fält
                for key, value in config.items():
                    if hasattr(current_config, key):
                        setattr(current_config, key, value)

                self._save_regimes(self.regimes)
                logger.info(f"⚙️ Regime konfiguration uppdaterad: {regime_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Kunde inte uppdatera regime konfiguration {regime_name}: {e}")
            return False

    def get_regime_status(self) -> dict[str, Any]:
        """
        Hämta status för alla regimer.

        Returns:
            Dict med regime status
        """
        try:
            active_regimes = self.get_active_regimes()
            weights = self.get_regime_weights()

            status = {
                "regimes": {},
                "active_regimes": active_regimes,
                "weights": weights,
                "total_active": len(active_regimes),
                "last_updated": datetime.now().isoformat(),
            }

            for regime_name, config in self.regimes.items():
                performance = self.performance_data.get(regime_name)

                regime_status = {
                    "enabled": config.enabled,
                    "weight": config.weight,
                    "active": regime_name in active_regimes,
                    "current_weight": weights.get(regime_name, 0.0),
                    "performance": performance.__dict__ if performance else None,
                    "config": config.__dict__,
                }

                status["regimes"][regime_name] = regime_status

            return status
        except Exception as e:
            logger.error(f"❌ Kunde inte hämta regime status: {e}")
            return {"error": str(e)}


# Global instans
regime_ablation = RegimeAblationService()
