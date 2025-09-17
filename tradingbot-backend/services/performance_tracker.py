import json
import os
from datetime import datetime, timedelta

from models.signal_models import SignalResponse
from utils.logger import get_logger

logger = get_logger(__name__)


class PerformanceTracker:
    """Performance tracking för enhanced auto-trading"""

    def __init__(self):
        self.performance_file = "config/enhanced_performance.json"
        self.trades_history: list[dict] = []
        self.daily_stats: dict[str, dict] = {}

        # Ladda befintlig data
        self._load_performance_data()

        logger.info("📊 PerformanceTracker initialiserad")

    def _load_performance_data(self):
        """Ladda befintlig performance data från fil"""
        try:
            if os.path.exists(self.performance_file):
                with open(self.performance_file) as f:
                    data = json.load(f)
                    self.trades_history = data.get("trades_history", [])
                    self.daily_stats = data.get("daily_stats", {})
                logger.info(
                    f"📊 Laddade {len(self.trades_history)} trades från performance fil"
                )
        except Exception as e:
            logger.error(f"❌ Fel vid laddning av performance data: {e}")

    def _save_performance_data(self):
        """Spara performance data till fil"""
        try:
            os.makedirs(os.path.dirname(self.performance_file), exist_ok=True)
            with open(self.performance_file, "w") as f:
                json.dump(
                    {
                        "trades_history": self.trades_history,
                        "daily_stats": self.daily_stats,
                        "last_updated": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"❌ Fel vid sparande av performance data: {e}")

    def record_trade(
        self,
        symbol: str,
        signal: SignalResponse,
        trade_result: dict,
        execution_time: datetime,
    ):
        """Registrera en utförd trade"""
        try:
            trade_record = {
                "id": f"trade_{len(self.trades_history) + 1}_{int(execution_time.timestamp())}",
                "symbol": symbol,
                "signal_type": signal.signal_type,
                "confidence_score": signal.confidence_score,
                "trading_probability": signal.trading_probability,
                "strength": signal.strength,
                "execution_time": execution_time.isoformat(),
                "trade_result": trade_result,
                "position_size": trade_result.get("position_size", 0),
                "entry_price": trade_result.get("entry_price", 0),
                "status": "OPEN",  # Kommer uppdateras när position stängs
            }

            self.trades_history.append(trade_record)

            # Uppdatera daily stats
            self._update_daily_stats(trade_record)

            # Spara data
            self._save_performance_data()

            logger.info(
                f"📊 Registrerade trade för {symbol}: {signal.signal_type} "
                f"(confidence: {signal.confidence_score}%, size: {trade_record['position_size']})"
            )

            return trade_record["id"]

        except Exception as e:
            logger.error(f"❌ Fel vid registrering av trade: {e}")
            return None

    def record_trade_close(
        self, trade_id: str, exit_price: float, profit_loss: float, close_time: datetime
    ):
        """Registrera stängning av en trade"""
        try:
            # Hitta trade i historik
            for trade in self.trades_history:
                if trade["id"] == trade_id:
                    trade.update(
                        {
                            "exit_price": exit_price,
                            "profit_loss": profit_loss,
                            "close_time": close_time.isoformat(),
                            "status": "CLOSED",
                            "duration_minutes": (
                                close_time
                                - datetime.fromisoformat(trade["execution_time"])
                            ).total_seconds()
                            / 60,
                        }
                    )

                    # Uppdatera daily stats
                    self._update_daily_stats(trade, is_close=True)

                    # Spara data
                    self._save_performance_data()

                    logger.info(
                        f"📊 Registrerade trade close för {trade['symbol']}: "
                        f"P&L: {profit_loss:.6f}, Duration: {trade['duration_minutes']:.1f} min"
                    )
                    return True

            logger.warning(f"⚠️ Kunde inte hitta trade med ID: {trade_id}")
            return False

        except Exception as e:
            logger.error(f"❌ Fel vid registrering av trade close: {e}")
            return False

    def _update_daily_stats(self, trade: dict, is_close: bool = False):
        """Uppdatera daglig statistik"""
        try:
            date_key = datetime.fromisoformat(trade["execution_time"]).strftime(
                "%Y-%m-%d"
            )

            if date_key not in self.daily_stats:
                self.daily_stats[date_key] = {
                    "total_trades": 0,
                    "buy_trades": 0,
                    "sell_trades": 0,
                    "total_volume": 0,
                    "total_profit_loss": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "avg_confidence": 0,
                    "avg_probability": 0,
                    "strong_signals": 0,
                    "medium_signals": 0,
                    "weak_signals": 0,
                }

            stats = self.daily_stats[date_key]

            if not is_close:
                # Ny trade
                stats["total_trades"] += 1
                stats["total_volume"] += trade.get("position_size", 0)

                if trade["signal_type"] == "BUY":
                    stats["buy_trades"] += 1
                elif trade["signal_type"] == "SELL":
                    stats["sell_trades"] += 1

                # Uppdatera genomsnitt confidence och probability
                current_avg_conf = stats["avg_confidence"]
                current_avg_prob = stats["avg_probability"]
                total_trades = stats["total_trades"]

                stats["avg_confidence"] = (
                    (current_avg_conf * (total_trades - 1)) + trade["confidence_score"]
                ) / total_trades
                stats["avg_probability"] = (
                    (current_avg_prob * (total_trades - 1))
                    + trade["trading_probability"]
                ) / total_trades

                # Räkna signal styrka
                if trade["strength"] == "STRONG":
                    stats["strong_signals"] += 1
                elif trade["strength"] == "MEDIUM":
                    stats["medium_signals"] += 1
                elif trade["strength"] == "WEAK":
                    stats["weak_signals"] += 1
            else:
                # Trade close
                profit_loss = trade.get("profit_loss", 0)
                stats["total_profit_loss"] += profit_loss

                if profit_loss > 0:
                    stats["winning_trades"] += 1
                elif profit_loss < 0:
                    stats["losing_trades"] += 1

        except Exception as e:
            logger.error(f"❌ Fel vid uppdatering av daily stats: {e}")

    def get_performance_summary(self, days: int = 30) -> dict:
        """Hämta performance sammanfattning för senaste dagarna"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_trades = [
                trade
                for trade in self.trades_history
                if datetime.fromisoformat(trade["execution_time"]) >= cutoff_date
            ]

            if not recent_trades:
                return {
                    "period_days": days,
                    "total_trades": 0,
                    "win_rate": 0,
                    "total_profit_loss": 0,
                    "avg_profit_per_trade": 0,
                    "best_trade": 0,
                    "worst_trade": 0,
                    "avg_confidence": 0,
                    "avg_probability": 0,
                    "signal_distribution": {"STRONG": 0, "MEDIUM": 0, "WEAK": 0},
                }

            # Beräkna statistik
            closed_trades = [t for t in recent_trades if t.get("status") == "CLOSED"]
            winning_trades = [t for t in closed_trades if t.get("profit_loss", 0) > 0]

            total_profit_loss = sum(t.get("profit_loss", 0) for t in closed_trades)
            avg_confidence = sum(t["confidence_score"] for t in recent_trades) / len(
                recent_trades
            )
            avg_probability = sum(
                t["trading_probability"] for t in recent_trades
            ) / len(recent_trades)

            signal_distribution = {
                "STRONG": len([t for t in recent_trades if t["strength"] == "STRONG"]),
                "MEDIUM": len([t for t in recent_trades if t["strength"] == "MEDIUM"]),
                "WEAK": len([t for t in recent_trades if t["strength"] == "WEAK"]),
            }

            return {
                "period_days": days,
                "total_trades": len(recent_trades),
                "closed_trades": len(closed_trades),
                "win_rate": (
                    len(winning_trades) / len(closed_trades) * 100
                    if closed_trades
                    else 0
                ),
                "total_profit_loss": total_profit_loss,
                "avg_profit_per_trade": (
                    total_profit_loss / len(closed_trades) if closed_trades else 0
                ),
                "best_trade": max(
                    (t.get("profit_loss", 0) for t in closed_trades), default=0
                ),
                "worst_trade": min(
                    (t.get("profit_loss", 0) for t in closed_trades), default=0
                ),
                "avg_confidence": avg_confidence,
                "avg_probability": avg_probability,
                "signal_distribution": signal_distribution,
            }

        except Exception as e:
            logger.error(f"❌ Fel vid beräkning av performance summary: {e}")
            return {}

    def get_symbol_performance(self, symbol: str, days: int = 30) -> dict:
        """Hämta performance för specifik symbol"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            symbol_trades = [
                trade
                for trade in self.trades_history
                if trade["symbol"] == symbol
                and datetime.fromisoformat(trade["execution_time"]) >= cutoff_date
            ]

            if not symbol_trades:
                return {
                    "symbol": symbol,
                    "period_days": days,
                    "total_trades": 0,
                    "win_rate": 0,
                    "total_profit_loss": 0,
                    "avg_confidence": 0,
                    "avg_probability": 0,
                }

            closed_trades = [t for t in symbol_trades if t.get("status") == "CLOSED"]
            winning_trades = [t for t in closed_trades if t.get("profit_loss", 0) > 0]

            total_profit_loss = sum(t.get("profit_loss", 0) for t in closed_trades)
            avg_confidence = sum(t["confidence_score"] for t in symbol_trades) / len(
                symbol_trades
            )
            avg_probability = sum(
                t["trading_probability"] for t in symbol_trades
            ) / len(symbol_trades)

            return {
                "symbol": symbol,
                "period_days": days,
                "total_trades": len(symbol_trades),
                "closed_trades": len(closed_trades),
                "win_rate": (
                    len(winning_trades) / len(closed_trades) * 100
                    if closed_trades
                    else 0
                ),
                "total_profit_loss": total_profit_loss,
                "avg_profit_per_trade": (
                    total_profit_loss / len(closed_trades) if closed_trades else 0
                ),
                "avg_confidence": avg_confidence,
                "avg_probability": avg_probability,
            }

        except Exception as e:
            logger.error(f"❌ Fel vid beräkning av symbol performance: {e}")
            return {}

    def get_recent_trades(self, limit: int = 20) -> list[dict]:
        """Hämta senaste trades"""
        try:
            return sorted(
                self.trades_history, key=lambda x: x["execution_time"], reverse=True
            )[:limit]
        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av recent trades: {e}")
            return []

    def get_daily_stats(self, days: int = 7) -> dict:
        """Hämta daglig statistik för senaste dagarna"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_stats = {
                date: stats
                for date, stats in self.daily_stats.items()
                if datetime.strptime(date, "%Y-%m-%d") >= cutoff_date
            }
            return recent_stats
        except Exception as e:
            logger.error(f"❌ Fel vid hämtning av daily stats: {e}")
            return {}


# Singleton instance
_performance_tracker_instance = None


def get_performance_tracker() -> PerformanceTracker:
    """Hämta singleton instance av PerformanceTracker"""
    global _performance_tracker_instance
    if _performance_tracker_instance is None:
        _performance_tracker_instance = PerformanceTracker()
    return _performance_tracker_instance
