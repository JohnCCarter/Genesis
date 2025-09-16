"""
Trading Integration Service - TradingBot Backend

Denna modul integrerar olika delar av tradingboten för att skapa en komplett tradingfunktionalitet.
Inkluderar integration mellan marknadsdata, strategier, orderhantering och positionshantering.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from rest.auth import place_order
from rest.margin import get_leverage, get_margin_info, get_margin_status
from rest.positions import get_positions
from rest.wallet import get_total_balance_usd, get_wallets
from services.market_data_facade import get_market_data
from services.metrics import inc
from services.realtime_strategy import realtime_strategy
from services.unified_risk_service import unified_risk_service
from services.strategy import evaluate_strategy
from utils.logger import get_logger

logger = get_logger(__name__)


class TradingIntegrationService:
    """Service för att integrera olika delar av tradingboten."""

    def __init__(self):
        self.active_symbols = set()
        self.strategy_results = {}
        self.position_info = {}
        self.wallet_info = {}
        self.margin_info = None
        self.market_data = {}
        self.signal_callbacks = {}
        self.risk_limits = {
            "max_position_size": 0.01,  # BTC
            "max_leverage": 3.0,
            "max_open_positions": 3,
            "max_drawdown_percent": 5.0,
            "stop_loss_percent": 2.0,
            "take_profit_percent": 5.0,
        }

    async def initialize(self):
        """Initialiserar trading-integrationen."""
        try:
            # Hämta initial data
            await self.update_wallet_info()
            await self.update_position_info()
            await self.update_margin_info()

            logger.info("✅ Trading-integration initialiserad")

        except Exception as e:
            logger.error(f"❌ Fel vid initialisering av trading-integration: {e}")

    async def update_wallet_info(self):
        """Uppdaterar plånboksinformation."""
        try:
            wallets = await get_wallets()

            # Organisera plånböcker efter typ och valuta
            self.wallet_info = {
                "exchange": {},
                "margin": {},
                "funding": {},
                "total_usd": await get_total_balance_usd(),
            }

            for wallet in wallets:
                wallet_type = wallet.wallet_type
                currency = wallet.currency

                if wallet_type not in self.wallet_info:
                    self.wallet_info[wallet_type] = {}

                self.wallet_info[wallet_type][currency] = wallet

            logger.info(f"✅ Plånboksinformation uppdaterad: {len(wallets)} plånböcker")

        except Exception as e:
            logger.error(f"❌ Fel vid uppdatering av plånboksinformation: {e}")

    async def update_position_info(self):
        """Uppdaterar positionsinformation."""
        try:
            positions = await get_positions()

            # Organisera positioner efter symbol
            self.position_info = {}

            for position in positions:
                symbol = position.symbol
                self.position_info[symbol] = position

            logger.info(
                f"✅ Positionsinformation uppdaterad: {len(positions)} positioner"
            )

        except Exception as e:
            logger.error(f"❌ Fel vid uppdatering av positionsinformation: {e}")

    async def update_margin_info(self):
        """Uppdaterar margin-information."""
        try:
            margin_info = await get_margin_info()
            margin_status = await get_margin_status()

            self.margin_info = {
                "info": margin_info,
                "status": margin_status,
                "leverage": await get_leverage(),
            }

            logger.info(
                f"✅ Margin-information uppdaterad: {self.margin_info['leverage']}x hävstång"
            )

        except Exception as e:
            logger.error(f"❌ Fel vid uppdatering av margin-information: {e}")

    async def update_market_data(self, symbol: str):
        """
        Uppdaterar marknadsdata för en symbol.

        Args:
            symbol: Trading pair (t.ex. 'tBTCUSD')
        """
        try:
            data = get_market_data()
            # Hämta ticker
            ticker = await data.get_ticker(symbol)

            # Hämta candles
            candles = await data.get_candles(symbol, timeframe="1h", limit=100)

            if ticker and candles:
                self.market_data[symbol] = {
                    "ticker": ticker,
                    "candles": candles,
                    "timestamp": datetime.now().isoformat(),
                }

                logger.info(
                    f"✅ Marknadsdata uppdaterad för {symbol}: ${ticker['last_price']:,.2f}"
                )

        except Exception as e:
            logger.error(f"❌ Fel vid uppdatering av marknadsdata för {symbol}: {e}")

    async def evaluate_trading_opportunity(self, symbol: str) -> dict[str, Any]:
        """
        Utvärderar en tradingmöjlighet för en symbol.

        Args:
            symbol: Trading pair (t.ex. 'tBTCUSD')

        Returns:
            Dict med utvärderingsresultat
        """
        try:
            # Uppdatera marknadsdata
            await self.update_market_data(symbol)

            if symbol not in self.market_data:
                return {
                    "symbol": symbol,
                    "signal": "ERROR",
                    "reason": "Ingen marknadsdata tillgänglig",
                }

            # Hämta candles och konvertera till strategidata
            candles = self.market_data[symbol]["candles"]

            # Tillfällig: enkel konvertering här, behåll bitfinex_data util om behövs
            def _parse(candles_in):
                highs = [float(c[3]) for c in candles_in if len(c) >= 4]
                lows = [float(c[4]) for c in candles_in if len(c) >= 5]
                closes = [float(c[2]) for c in candles_in if len(c) >= 3]
                return {"high": highs, "low": lows, "close": closes}

            strategy_data = _parse(candles)

            # Utvärdera strategi
            result = evaluate_strategy(strategy_data)

            # Lägg till symbol och pris
            result["symbol"] = symbol
            result["current_price"] = self.market_data[symbol]["ticker"]["last_price"]

            # Spara resultat
            self.strategy_results[symbol] = result

            # Kontrollera riskhantering
            risk_assessment = self._assess_risk(symbol, result)
            result.update(risk_assessment)

            logger.info(
                f"✅ Tradingmöjlighet utvärderad för {symbol}: {result['signal']}"
            )

            return result

        except Exception as e:
            logger.error(
                f"❌ Fel vid utvärdering av tradingmöjlighet för {symbol}: {e}"
            )
            return {
                "symbol": symbol,
                "signal": "ERROR",
                "reason": f"Fel vid utvärdering: {e}",
            }

    def _assess_risk(
        self, symbol: str, strategy_result: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Utvärderar risk för en tradingmöjlighet.

        Args:
            symbol: Trading pair
            strategy_result: Resultat från strategiutvärdering

        Returns:
            Dict med riskbedömning
        """
        try:
            signal = strategy_result["signal"]
            current_price = strategy_result.get("current_price", 0)

            # Kontrollera om vi redan har en position
            has_position = symbol in self.position_info
            position_size = self.position_info[symbol].amount if has_position else 0

            # Kontrollera antal öppna positioner
            open_positions = len(self.position_info)

            # Kontrollera margin-status
            margin_level = (
                self.margin_info["status"]["margin_level"] if self.margin_info else 0
            )
            leverage = self.margin_info["leverage"] if self.margin_info else 1.0

            # Riskbedömning
            risk_assessment = {
                "risk_level": "LOW",
                "can_trade": True,
                "max_position_size": self.risk_limits["max_position_size"],
                "reason": "Ingen risk detekterad",
            }

            # Kontrollera om vi kan handla
            if signal in ["BUY", "SELL"]:
                # Kontrollera antal öppna positioner
                if open_positions >= self.risk_limits["max_open_positions"]:
                    risk_assessment["can_trade"] = False
                    risk_assessment["risk_level"] = "HIGH"
                    risk_assessment["reason"] = (
                        f"För många öppna positioner ({open_positions})"
                    )

                # Kontrollera hävstång
                elif leverage > self.risk_limits["max_leverage"]:
                    risk_assessment["can_trade"] = False
                    risk_assessment["risk_level"] = "HIGH"
                    risk_assessment["reason"] = f"För hög hävstång ({leverage}x)"

                # Kontrollera margin-nivå
                elif margin_level < 1.5:
                    risk_assessment["can_trade"] = False
                    risk_assessment["risk_level"] = "HIGH"
                    risk_assessment["reason"] = f"För låg margin-nivå ({margin_level})"

                # Om vi redan har en position i samma riktning
                elif has_position:
                    if (signal == "BUY" and position_size > 0) or (
                        signal == "SELL" and position_size < 0
                    ):
                        risk_assessment["can_trade"] = False
                        risk_assessment["risk_level"] = "MEDIUM"
                        risk_assessment["reason"] = f"Har redan en {signal} position"

            return risk_assessment

        except Exception as e:
            logger.error(f"❌ Fel vid riskbedömning för {symbol}: {e}")
            return {
                "risk_level": "UNKNOWN",
                "can_trade": False,
                "reason": f"Fel vid riskbedömning: {e}",
            }

    async def execute_trading_signal(
        self, symbol: str, signal_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Utför en tradingsignal för en symbol.

        Args:
            symbol: Trading pair
            signal_data: Data från strategiutvärdering

        Returns:
            Dict med resultat från orderläggning
        """
        try:
            signal = signal_data["signal"]
            current_price = signal_data.get("current_price", 0)
            risk_level = signal_data.get("risk_level", "UNKNOWN")
            can_trade = signal_data.get("can_trade", False)

            if not can_trade:
                logger.warning(
                    f"⚠️ Kan inte handla {symbol}: {signal_data.get('reason', 'Okänd anledning')}"
                )
                return {
                    "success": False,
                    "message": f"Kan inte handla: {signal_data.get('reason', 'Okänd anledning')}",
                    "order": None,
                }

            # Enhetliga riskkontroller (Trade constraints, guards, CB)
            try:
                decision = unified_risk_service.evaluate_risk(symbol=symbol)
                if not decision.allowed:
                    logger.warning(f"🚫 Risk block: {decision.reason}")
                    return {
                        "success": False,
                        "message": f"risk_blocked:{decision.reason}",
                        "order": None,
                    }
            except Exception as e:
                logger.warning(f"Unified risk-kontroll misslyckades: {e}")

            # Kontrollera om vi ska handla
            if signal not in ["BUY", "SELL"]:
                logger.info(f"ℹ️ Ingen handel för {symbol}: Signal är {signal}")
                return {
                    "success": False,
                    "message": f"Ingen handel: Signal är {signal}",
                    "order": None,
                }

            # Beräkna ordervolym baserat på riskhantering
            position_size = self._calculate_position_size(symbol, signal_data)

            # Skapa orderdata
            order_data = {
                "symbol": symbol,
                "amount": (
                    str(position_size) if signal == "BUY" else str(-position_size)
                ),
                "price": str(current_price),
                "type": "EXCHANGE LIMIT",
            }

            # Lägg order
            logger.info(
                f"🛒 Lägger {signal} order för {symbol}: {position_size} @ ${current_price:,.2f}"
            )
            result = await place_order(order_data)

            if "error" in result:
                logger.error(
                    f"❌ Fel vid orderläggning för {symbol}: {result['error']}"
                )
                try:
                    inc("orders_total")
                    inc("orders_failed_total")
                    unified_risk_service.record_error()
                except Exception:
                    pass
                return {
                    "success": False,
                    "message": f"Orderläggning misslyckades: {result['error']}",
                    "order": None,
                }

            logger.info(f"✅ Order lagd för {symbol}: {result}")
            try:
                inc("orders_total")
                unified_risk_service.record_trade(symbol=symbol)
            except Exception:
                pass

            # Uppdatera position- och plånboksinformation
            await asyncio.gather(self.update_position_info(), self.update_wallet_info())

            return {
                "success": True,
                "message": f"{signal} order lagd framgångsrikt",
                "order": result,
            }

        except Exception as e:
            logger.error(f"❌ Fel vid utförande av tradingsignal för {symbol}: {e}")
            return {
                "success": False,
                "message": f"Fel vid utförande av tradingsignal: {e}",
                "order": None,
            }

    def _calculate_position_size(
        self, symbol: str, signal_data: dict[str, Any]
    ) -> float:
        """
        Beräknar lämplig positionsstorlek baserat på riskhantering.

        Args:
            symbol: Trading pair
            signal_data: Data från strategiutvärdering

        Returns:
            Positionsstorlek
        """
        try:
            # Hämta max positionsstorlek från riskhantering
            max_size = signal_data.get(
                "max_position_size", self.risk_limits["max_position_size"]
            )

            # Hämta tillgängligt saldo
            available_balance = 0

            if "exchange" in self.wallet_info:
                # För BTC-baserade symboler
                if symbol.startswith("tBTC"):
                    if "BTC" in self.wallet_info["exchange"]:
                        available_balance = self.wallet_info["exchange"]["BTC"].balance
                # För andra symboler, använd USD
                elif "USD" in self.wallet_info["exchange"]:
                    available_balance = self.wallet_info["exchange"][
                        "USD"
                    ].balance / signal_data.get("current_price", 50000)

            # Begränsa positionsstorlek baserat på tillgängligt saldo
            # Använd max 20% av tillgängligt saldo
            balance_limit = available_balance * 0.2

            # Använd det mindre av max_size och balance_limit
            position_size = min(max_size, balance_limit)

            # Avrunda till 4 decimaler
            position_size = round(position_size, 4)

            # Säkerställ att positionsstorleken är minst 0.001
            position_size = max(position_size, 0.001)

            return position_size

        except Exception as e:
            logger.error(f"❌ Fel vid beräkning av positionsstorlek för {symbol}: {e}")
            return 0.001  # Minimal positionsstorlek som fallback

    async def start_automated_trading(
        self, symbol: str, callback: Callable | None = None
    ):
        """
        Startar automatiserad trading för en symbol.

        Args:
            symbol: Trading pair
            callback: Funktion som anropas vid nya signaler
        """
        try:
            if symbol in self.active_symbols:
                logger.warning(f"⚠️ {symbol} handlas redan automatiskt")
                return

            # Spara callback
            if callback:
                self.signal_callbacks[symbol] = callback

            # Starta realtidsövervakning med vår egen callback
            await realtime_strategy.start_monitoring(
                symbol, self._handle_realtime_signal
            )

            self.active_symbols.add(symbol)

            logger.info(f"🤖 Startade automatiserad trading för {symbol}")

        except Exception as e:
            logger.error(f"❌ Fel vid start av automatiserad trading för {symbol}: {e}")

    async def stop_automated_trading(self, symbol: str):
        """
        Stoppar automatiserad trading för en symbol.

        Args:
            symbol: Trading pair
        """
        try:
            if symbol in self.active_symbols:
                self.active_symbols.remove(symbol)

                # Ta bort callback
                if symbol in self.signal_callbacks:
                    del self.signal_callbacks[symbol]

                # Stoppa realtidsövervakning
                await realtime_strategy.stop_monitoring(symbol)

                logger.info(f"🛑 Stoppade automatiserad trading för {symbol}")
            else:
                logger.warning(f"⚠️ {symbol} handlades inte automatiskt")

        except Exception as e:
            logger.error(f"❌ Fel vid stopp av automatiserad trading för {symbol}: {e}")

    async def _handle_realtime_signal(self, result: dict):
        """
        Hanterar realtidssignaler från strategiutvärdering.

        Args:
            result: Strategi-resultat med signal och data
        """
        try:
            symbol = result.get("symbol", "unknown")
            signal = result.get("signal", "UNKNOWN")

            # Uppdatera position- och plånboksinformation
            await asyncio.gather(
                self.update_position_info(),
                self.update_wallet_info(),
                self.update_margin_info(),
            )

            # Utför riskbedömning
            risk_assessment = self._assess_risk(symbol, result)
            result.update(risk_assessment)

            # Spara senaste resultat
            self.strategy_results[symbol] = result

            # Logga signal
            logger.info(
                f"🎯 {symbol}: {signal} @ ${result.get('current_price', 0):,.2f} - {result.get('reason', '')}"
            )

            # Utför tradingsignal om det är BUY eller SELL
            if signal in ["BUY", "SELL"] and result.get("can_trade", False):
                trade_result = await self.execute_trading_signal(symbol, result)
                result["trade_result"] = trade_result

            # Anropa callback om den finns
            if symbol in self.signal_callbacks:
                await self.signal_callbacks[symbol](result)

        except Exception as e:
            logger.error(f"❌ Fel vid hantering av realtidssignal: {e}")

    async def get_account_summary(self) -> dict[str, Any]:
        """
        Skapar en sammanfattning av kontostatus.

        Returns:
            Dict med kontosammanfattning
        """
        try:
            # Uppdatera all information
            await asyncio.gather(
                self.update_position_info(),
                self.update_wallet_info(),
                self.update_margin_info(),
            )

            # Beräkna totalt positionsvärde
            total_position_value = 0
            for symbol, position in self.position_info.items():
                # Hämta aktuellt pris om möjligt
                current_price = 0
                if symbol in self.market_data and "ticker" in self.market_data[symbol]:
                    current_price = self.market_data[symbol]["ticker"]["last_price"]
                elif position.base_price:
                    current_price = position.base_price

                position_value = abs(position.amount) * current_price
                total_position_value += position_value

            # Sammanställ information
            summary = {
                "total_balance_usd": self.wallet_info.get("total_usd", 0),
                "margin_balance": (
                    self.margin_info["info"].margin_balance if self.margin_info else 0
                ),
                "unrealized_pl": (
                    self.margin_info["info"].unrealized_pl if self.margin_info else 0
                ),
                "leverage": self.margin_info["leverage"] if self.margin_info else 1.0,
                "margin_level": (
                    self.margin_info["status"]["margin_level"]
                    if self.margin_info
                    else 0
                ),
                "margin_status": (
                    self.margin_info["status"]["status"]
                    if self.margin_info
                    else "unknown"
                ),
                "open_positions": len(self.position_info),
                "total_position_value": total_position_value,
                "active_symbols": list(self.active_symbols),
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"✅ Kontosammanfattning skapad: ${summary['total_balance_usd']:,.2f}"
            )

            return summary

        except Exception as e:
            logger.error(f"❌ Fel vid skapande av kontosammanfattning: {e}")
            return {
                "error": "internal_error",
                "timestamp": datetime.now().isoformat(),
            }

    async def stop_all_trading(self):
        """Stoppar all automatiserad trading."""
        try:
            symbols_to_stop = list(self.active_symbols)
            for symbol in symbols_to_stop:
                await self.stop_automated_trading(symbol)

            logger.info("🛑 Stoppade all automatiserad trading")

        except Exception as e:
            logger.error(f"❌ Fel vid stopp av all automatiserad trading: {e}")


# Global instans för enkel åtkomst
trading_integration = TradingIntegrationService()
