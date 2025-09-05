"""
Cost-Aware Backtest Service - Realistisk backtesting med kostnader.

Implementerar:
- Avgiftsmodellering (maker/taker fees)
- Spread och slippage simulering
- Partial fills hantering
- Latency och ack simulering
- Sharpe/Sortino/MAR rapportering
"""

import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from services.market_data_facade import get_market_data
from services.strategy import evaluate_strategy
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TradeCosts:
    """Kostnadsmodell för en trade."""

    maker_fee: float = 0.001  # 0.1% maker fee
    taker_fee: float = 0.002  # 0.2% taker fee
    spread_bps: float = 10.0  # 10 basis points spread
    slippage_bps: float = 5.0  # 5 basis points slippage
    partial_fill_prob: float = 0.1  # 10% chans för partial fill
    latency_ms: float = 50.0  # 50ms latency


@dataclass
class BacktestTrade:
    """En trade i backtest."""

    timestamp: datetime
    symbol: str
    side: str  # 'buy' eller 'sell'
    amount: float
    price: float
    executed_price: float
    fees: float
    slippage: float
    partial_fill: bool
    fill_ratio: float  # 0.0-1.0
    latency_ms: float


@dataclass
class BacktestResult:
    """Resultat från backtest."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    total_fees: float
    total_slippage: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    hit_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    equity_curve: list[dict[str, Any]]
    trades: list[BacktestTrade]


class CostAwareBacktestService:
    """Service för cost-aware backtesting."""

    def __init__(self, costs: TradeCosts | None = None):
        self.costs = costs or TradeCosts()
        self.data_service = get_market_data()

    def simulate_market_impact(self, base_price: float, amount: float, side: str) -> tuple[float, float, float]:
        """
        Simulera marknadsimpact, slippage och spread.

        Args:
            base_price: Baspris från candles
            amount: Trade amount
            side: 'buy' eller 'sell'

        Returns:
            Tuple[float, float, float]: (executed_price, slippage, spread_cost)
        """
        # Spread (bid-ask spread)
        spread_bps = self.costs.spread_bps / 10000.0
        spread_cost = base_price * spread_bps

        # Slippage (marknadsimpact)
        # Större trades = mer slippage
        impact_factor = min(abs(amount) / 1000.0, 1.0)  # Normalisera till 1000
        slippage_bps = self.costs.slippage_bps * impact_factor / 10000.0
        slippage = base_price * slippage_bps

        # Exekveringspris
        if side == "buy":
            executed_price = base_price + spread_cost + slippage
        else:  # sell
            executed_price = base_price - spread_cost - slippage

        return executed_price, slippage, spread_cost

    def simulate_partial_fill(self, requested_amount: float) -> tuple[float, float]:
        """
        Simulera partial fill.

        Args:
            requested_amount: Begärt amount

        Returns:
            Tuple[float, float]: (filled_amount, fill_ratio)
        """
        if random.random() < self.costs.partial_fill_prob:
            # Partial fill
            fill_ratio = random.uniform(0.3, 0.9)  # 30-90% fill
            filled_amount = requested_amount * fill_ratio
        else:
            # Full fill
            fill_ratio = 1.0
            filled_amount = requested_amount

        return filled_amount, fill_ratio

    def calculate_fees(self, amount: float, price: float, is_maker: bool = False) -> float:
        """
        Beräkna avgifter för en trade.

        Args:
            amount: Trade amount
            price: Trade price
            is_maker: Om det är en maker order

        Returns:
            float: Totala avgifter
        """
        trade_value = abs(amount) * price
        fee_rate = self.costs.maker_fee if is_maker else self.costs.taker_fee
        return trade_value * fee_rate

    def simulate_latency(self) -> float:
        """
        Simulera order latency.

        Returns:
            float: Latency i millisekunder
        """
        # Normal distribution runt mean latency
        latency = random.gauss(self.costs.latency_ms, self.costs.latency_ms * 0.2)
        return max(10.0, latency)  # Minst 10ms

    def calculate_metrics(self, trades: list[BacktestTrade], initial_capital: float) -> dict[str, Any]:
        """
        Beräkna avancerade metrics från trades.

        Args:
            trades: Lista av trades
            initial_capital: Startkapital

        Returns:
            Dict med alla metrics
        """
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_pnl": 0.0,
                "total_fees": 0.0,
                "total_slippage": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "hit_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
            }

        # Grundläggande statistik
        total_trades = len(trades)
        total_pnl = sum(trade.amount * (trade.price - trade.executed_price) for trade in trades)
        total_fees = sum(trade.fees for trade in trades)
        total_slippage = sum(trade.slippage for trade in trades)

        # Vinnande/förlorande trades
        winning_trades = [t for t in trades if t.amount * (t.price - t.executed_price) > 0]
        losing_trades = [t for t in trades if t.amount * (t.price - t.executed_price) < 0]

        winning_count = len(winning_trades)
        losing_count = len(losing_trades)

        # Hit rate
        hit_rate = winning_count / total_trades if total_trades > 0 else 0.0

        # Genomsnittliga vinster/förluster
        avg_win = (
            sum(t.amount * (t.price - t.executed_price) for t in winning_trades) / winning_count
            if winning_count > 0
            else 0.0
        )
        avg_loss = (
            abs(sum(t.amount * (t.price - t.executed_price) for t in losing_trades) / losing_count)
            if losing_count > 0
            else 0.0
        )

        # Profit factor
        total_wins = sum(t.amount * (t.price - t.executed_price) for t in winning_trades)
        total_losses = abs(sum(t.amount * (t.price - t.executed_price) for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        # Expectancy
        expectancy = (hit_rate * avg_win) - ((1 - hit_rate) * avg_loss)

        # Drawdown beräkning
        equity_curve = self._calculate_equity_curve(trades, initial_capital)
        max_drawdown = self._calculate_max_drawdown(equity_curve)

        # Risk-adjusted returns
        returns = self._calculate_returns(equity_curve)
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        sortino_ratio = self._calculate_sortino_ratio(returns)
        calmar_ratio = self._calculate_calmar_ratio(returns, max_drawdown)

        return {
            "total_trades": total_trades,
            "winning_trades": winning_count,
            "losing_trades": losing_count,
            "total_pnl": total_pnl,
            "total_fees": total_fees,
            "total_slippage": total_slippage,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "hit_rate": hit_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
        }

    def _calculate_equity_curve(self, trades: list[BacktestTrade], initial_capital: float) -> list[dict[str, Any]]:
        """Beräkna equity curve från trades."""
        equity_curve = []
        current_equity = initial_capital

        for trade in trades:
            # Beräkna PnL för denna trade
            pnl = trade.amount * (trade.price - trade.executed_price)
            fees = trade.fees
            net_pnl = pnl - fees

            current_equity += net_pnl

            equity_curve.append(
                {
                    "timestamp": trade.timestamp,
                    "equity": current_equity,
                    "pnl": pnl,
                    "fees": fees,
                    "net_pnl": net_pnl,
                    "trade": trade,
                }
            )

        return equity_curve

    def _calculate_max_drawdown(self, equity_curve: list[dict[str, Any]]) -> float:
        """Beräkna maximum drawdown."""
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]["equity"]
        max_dd = 0.0

        for point in equity_curve:
            equity = point["equity"]
            if equity > peak:
                peak = equity
            else:
                dd = (peak - equity) / peak
                max_dd = max(max_dd, dd)

        return max_dd

    def _calculate_returns(self, equity_curve: list[dict[str, Any]]) -> list[float]:
        """Beräkna returns från equity curve."""
        if len(equity_curve) < 2:
            return [0.0]

        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i - 1]["equity"]
            curr_equity = equity_curve[i]["equity"]
            ret = (curr_equity - prev_equity) / prev_equity
            returns.append(ret)

        return returns

    def _calculate_sharpe_ratio(self, returns: list[float]) -> float:
        """Beräkna Sharpe ratio."""
        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return 0.0

        # Annualized Sharpe ratio (antag 252 trading days)
        sharpe = (mean_return * 252) / (std_dev * math.sqrt(252))
        return sharpe

    def _calculate_sortino_ratio(self, returns: list[float]) -> float:
        """Beräkna Sortino ratio."""
        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)
        negative_returns = [r for r in returns if r < 0]

        if not negative_returns:
            return float("inf")

        downside_variance = sum((r - mean_return) ** 2 for r in negative_returns) / len(returns)
        downside_deviation = math.sqrt(downside_variance)

        if downside_deviation == 0:
            return 0.0

        # Annualized Sortino ratio
        sortino = (mean_return * 252) / (downside_deviation * math.sqrt(252))
        return sortino

    def _calculate_calmar_ratio(self, returns: list[float], max_drawdown: float) -> float:
        """Beräkna Calmar ratio."""
        if not returns or max_drawdown == 0:
            return 0.0

        mean_return = sum(returns) / len(returns)
        annualized_return = mean_return * 252

        calmar = annualized_return / max_drawdown
        return calmar

    async def run_backtest(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 500,
        initial_capital: float = 10000.0,
        position_size_pct: float = 0.1,  # 10% per trade
        costs: TradeCosts | None = None,
    ) -> BacktestResult:
        """
        Kör cost-aware backtest.

        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            limit: Antal candles
            initial_capital: Startkapital
            position_size_pct: Position size som % av kapital
            costs: Kostnadsmodell (optional)

        Returns:
            BacktestResult: Resultat från backtest
        """
        if costs:
            self.costs = costs

        # Hämta historisk data
        candles = await self.data_service.get_candles(symbol, timeframe, limit)
        if not candles:
            raise ValueError(f"Kunde inte hämta data för {symbol}")

        # Parse candles
        try:
            from utils.candles import parse_candles_to_strategy_data

            parsed = parse_candles_to_strategy_data(candles)
        except Exception:
            parsed = {"closes": [], "highs": [], "lows": []}
        closes = parsed.get("closes", [])
        highs = parsed.get("highs", [])
        lows = parsed.get("lows", [])

        if len(closes) < 50:
            raise ValueError("Inte tillräckligt med data för backtest")

        # Backtest variabler
        current_equity = initial_capital
        position = 0.0  # +1 long, -1 short, 0 flat
        entry_price = 0.0
        trades: list[BacktestTrade] = []

        # Rullande strategiutvärdering
        for i in range(50, len(closes)):
            window = {
                "closes": closes[: i + 1],
                "highs": highs[: i + 1],
                "lows": lows[: i + 1],
            }

            # Strategiutvärdering
            strat = evaluate_strategy(window)
            signal = (strat.get("weighted", {}) or {}).get("signal", "hold")
            price = closes[i]

            # Simulera latency
            latency = self.simulate_latency()

            # Trade logik
            if signal == "buy" and position <= 0:
                # Stäng short position om vi har en
                if position < 0:
                    exit_trade = self._create_trade(
                        timestamp=datetime.now(),
                        symbol=symbol,
                        side="buy",
                        amount=abs(position),
                        price=price,
                        is_exit=True,
                    )
                    trades.append(exit_trade)
                    current_equity += exit_trade.amount * (exit_trade.price - entry_price) - exit_trade.fees

                # Öppna long position
                position_size = current_equity * position_size_pct / price
                entry_trade = self._create_trade(
                    timestamp=datetime.now(),
                    symbol=symbol,
                    side="buy",
                    amount=position_size,
                    price=price,
                    is_exit=False,
                )
                trades.append(entry_trade)
                position = position_size
                entry_price = entry_trade.executed_price

            elif signal == "sell" and position >= 0:
                # Stäng long position om vi har en
                if position > 0:
                    exit_trade = self._create_trade(
                        timestamp=datetime.now(),
                        symbol=symbol,
                        side="sell",
                        amount=position,
                        price=price,
                        is_exit=True,
                    )
                    trades.append(exit_trade)
                    current_equity += exit_trade.amount * (exit_trade.price - entry_price) - exit_trade.fees

                # Öppna short position
                position_size = current_equity * position_size_pct / price
                entry_trade = self._create_trade(
                    timestamp=datetime.now(),
                    symbol=symbol,
                    side="sell",
                    amount=position_size,
                    price=price,
                    is_exit=False,
                )
                trades.append(entry_trade)
                position = -position_size
                entry_price = entry_trade.executed_price

        # Stäng eventuell öppen position
        if position != 0:
            side = "sell" if position > 0 else "buy"
            exit_trade = self._create_trade(
                timestamp=datetime.now(),
                symbol=symbol,
                side=side,
                amount=abs(position),
                price=closes[-1],
                is_exit=True,
            )
            trades.append(exit_trade)

        # Beräkna metrics
        metrics = self.calculate_metrics(trades, initial_capital)
        equity_curve = self._calculate_equity_curve(trades, initial_capital)

        return BacktestResult(
            total_trades=metrics["total_trades"],
            winning_trades=metrics["winning_trades"],
            losing_trades=metrics["losing_trades"],
            total_pnl=metrics["total_pnl"],
            total_fees=metrics["total_fees"],
            total_slippage=metrics["total_slippage"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            sortino_ratio=metrics["sortino_ratio"],
            calmar_ratio=metrics["calmar_ratio"],
            hit_rate=metrics["hit_rate"],
            avg_win=metrics["avg_win"],
            avg_loss=metrics["avg_loss"],
            profit_factor=metrics["profit_factor"],
            expectancy=metrics["expectancy"],
            equity_curve=equity_curve,
            trades=trades,
        )

    def _create_trade(
        self,
        timestamp: datetime,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        is_exit: bool,
    ) -> BacktestTrade:
        """Skapa en trade med alla kostnader."""
        # Simulera marknadsimpact
        executed_price, slippage, spread_cost = self.simulate_market_impact(price, amount, side)

        # Simulera partial fill
        filled_amount, fill_ratio = self.simulate_partial_fill(amount)

        # Beräkna avgifter (maker för limit orders, taker för market)
        is_maker = not is_exit  # Entry orders är limit, exit är market
        fees = self.calculate_fees(filled_amount, executed_price, is_maker)

        # Simulera latency
        latency = self.simulate_latency()

        return BacktestTrade(
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            amount=filled_amount,
            price=price,
            executed_price=executed_price,
            fees=fees,
            slippage=slippage,
            partial_fill=fill_ratio < 1.0,
            fill_ratio=fill_ratio,
            latency_ms=latency,
        )


# Global instans
cost_aware_backtest = CostAwareBacktestService()
