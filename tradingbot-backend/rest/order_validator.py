"""
Order Validator - TradingBot Backend

Denna modul validerar orderparametrar mot Bitfinex API-dokumentation.
Använder information från scraper-modulen för att validera ordertyper,
symboler och parametrar.
"""

from typing import Any

try:
    from scraper.bitfinex_docs import BitfinexDocsScraper  # pylint: disable=E0401
except Exception:
    BitfinexDocsScraper = None  # type: ignore
from utils.logger import get_logger

logger = get_logger(__name__)


class OrderValidator:
    """
    Validerar orderparametrar mot Bitfinex API-dokumentation.
    """

    def __init__(self):
        """
        Initialiserar validator med information från Bitfinex API-dokumentation.
        """
        self.scraper = BitfinexDocsScraper() if BitfinexDocsScraper else None
        self._load_data()

    def _load_data(self) -> None:
        """
        Laddar nödvändig data från scrapern.
        """
        # Om scraper saknas (förväntat i detta projektläge), använd fallback tyst
        if not self.scraper:
            logger.info("OrderValidator: scraper inaktiv – använder fallback-data")
            self._setup_fallback_data()
            return
        try:
            # Ladda ordertyper
            self.order_types = self.scraper.fetch_order_types()
            logger.info(f"Laddade {len(self.order_types)} ordertyper")

            # Ladda symboler
            self.symbols = self.scraper.fetch_symbols()
            self.symbol_names = [s["symbol"] for s in self.symbols]
            logger.info(f"Laddade {len(self.symbols)} symboler")

            # Ladda paper trading symboler
            self.paper_symbols = self.scraper.get_paper_trading_symbols()
            self.paper_symbol_names = [s["symbol"] for s in self.paper_symbols]
            logger.info(f"Laddade {len(self.paper_symbols)} paper trading symboler")

        except Exception as e:
            logger.warning(f"OrderValidator: kunde inte ladda scraper-data, fallback används: {e}")
            self._setup_fallback_data()

    def _setup_fallback_data(self) -> None:
        """
        Sätter upp grundläggande fallback-data om scrapern misslyckas.
        """
        logger.info("Använder fallback-data för ordervalidering")

        # Grundläggande ordertyper
        self.order_types = {
            "EXCHANGE LIMIT": {
                "name": "EXCHANGE LIMIT",
                "description": "Limit order för exchange wallets",
                "required_params": ["symbol", "amount", "price"],
                "optional_params": [
                    "price_trailing",
                    "price_aux_limit",
                    "price_oco_stop",
                    "flags",
                ],
            },
            "EXCHANGE MARKET": {
                "name": "EXCHANGE MARKET",
                "description": "Market order för exchange wallets",
                "required_params": ["symbol", "amount"],
                "optional_params": ["price", "flags"],
            },
            "EXCHANGE STOP": {
                "name": "EXCHANGE STOP",
                "description": "Stop order för exchange wallets",
                "required_params": ["symbol", "amount", "price"],
                "optional_params": ["flags"],
            },
            # Margin-ordrar (utan EXCHANGE-prefix)
            "LIMIT": {
                "name": "LIMIT",
                "description": "Limit order för margin wallets",
                "required_params": ["symbol", "amount", "price"],
                "optional_params": ["flags"],
            },
            "MARKET": {
                "name": "MARKET",
                "description": "Market order för margin wallets",
                "required_params": ["symbol", "amount"],
                "optional_params": ["price", "flags"],
            },
        }

        # Grundläggande symboler (inkl. de testsymboler du använder)
        test_syms = [
            # Med t prefix (för API-anrop)
            "tTESTADA:TESTUSD",
            "tTESTALGO:TESTUSD",
            "tTESTAPT:TESTUSD",
            "tTESTAVAX:TESTUSD",
            "tTESTBTC:TESTUSD",
            "tTESTBTC:TESTUSDT",
            "tTESTDOGE:TESTUSD",
            "tTESTDOT:TESTUSD",
            "tTESTEOS:TESTUSD",
            "tTESTETH:TESTUSD",
            "tTESTFIL:TESTUSD",
            "tTESTLTC:TESTUSD",
            "tTESTNEAR:TESTUSD",
            "tTESTSOL:TESTUSD",
            "tTESTXAUT:TESTUSD",
            "tTESTXTZ:TESTUSD",
            # Utan t prefix (för frontend)
            "TESTADA:TESTUSD",
            "TESTALGO:TESTUSD",
            "TESTAPT:TESTUSD",
            "TESTAVAX:TESTUSD",
            "TESTBTC:TESTUSD",
            "TESTBTC:TESTUSDT",
            "TESTDOGE:TESTUSD",
            "TESTDOT:TESTUSD",
            "TESTEOS:TESTUSD",
            "TESTETH:TESTUSD",
            "TESTFIL:TESTUSD",
            "TESTLTC:TESTUSD",
            "TESTNEAR:TESTUSD",
            "TESTSOL:TESTUSD",
            "TESTXAUT:TESTUSD",
            "TESTXTZ:TESTUSD",
        ]
        # Bygg live-lista via SymbolService om möjligt
        try:
            from services.symbols import SymbolService

            svc = SymbolService()
            # Använd befintlig cache istället för att köra refresh synkront
            live_pairs = getattr(svc, "_pairs", [])  # ex. ["BTCUSD","ETHUSD",...]
            live = [{"symbol": f"t{p}"} for p in live_pairs]
        except Exception:
            live = [{"symbol": "tBTCUSD"}, {"symbol": "tETHUSD"}]

        # Inkludera alltid TEST‑symboler i fallback (paper trading)
        self.symbols = live + [{"symbol": s, "is_paper": True} for s in test_syms]
        self.symbol_names = [s["symbol"] for s in self.symbols]

        # Paper trading symboler
        self.paper_symbols = [s for s in self.symbols if s.get("is_paper", False)]
        self.paper_symbol_names = [s["symbol"] for s in self.paper_symbols]

    def validate_order(self, order: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validerar en order mot Bitfinex API-krav.

        Args:
            order: Dict med orderdata

        Returns:
            Tuple[bool, Optional[str]]: (är_giltig, felmeddelande)
        """
        # Validera ordertyp
        order_type = order.get("type", "EXCHANGE LIMIT").upper()
        if order_type not in self.order_types:
            return (
                False,
                f"Ogiltig ordertyp: {order_type}. Giltiga typer: {', '.join(self.order_types.keys())}",
            )

        # Validera symbol
        symbol = order.get("symbol")
        if not symbol:
            return False, "Symbol saknas i ordern"

        if symbol not in self.symbol_names:
            return False, f"Ogiltig symbol: {symbol}"

        # Kontrollera om det är en paper trading symbol
        is_paper_symbol = symbol in self.paper_symbol_names
        if not is_paper_symbol and symbol.startswith("tTEST"):
            logger.warning(f"Symbol {symbol} börjar med 'tTEST' men är inte registrerad som paper trading symbol")

        # Validera krävda parametrar för ordertypen
        required_params = self.order_types[order_type].get("required_params", [])
        for param in required_params:
            if param not in order or order[param] is None:
                return (
                    False,
                    f"Saknad parameter: {param} krävs för ordertyp {order_type}",
                )

        # Validera belopp
        amount = order.get("amount")
        if amount is not None:
            try:
                amount_float = float(amount)
                # Kontrollera att beloppet inte är noll
                if amount_float == 0:
                    return False, "Belopp kan inte vara noll"
            except (ValueError, TypeError):
                return False, f"Ogiltigt beloppsformat: {amount}"

        # Validera pris för limit orders
        if "price" in required_params and order_type != "EXCHANGE MARKET":
            price = order.get("price")
            if price is not None:
                try:
                    price_float = float(price)
                    # Kontrollera att priset är positivt för limit orders
                    if price_float <= 0:
                        return False, "Pris måste vara större än noll för limit orders"
                except (ValueError, TypeError):
                    return False, f"Ogiltigt prisformat: {price}"

        # Tolerera kända flaggor (reduce_only/post_only/flags) utan hård validering här
        try:
            _ = bool(order.get("reduce_only"))
            _ = bool(order.get("post_only")) or bool(order.get("postonly"))
            if order.get("flags") is not None:
                int(order.get("flags"))
        except Exception:
            return False, "Ogiltiga flaggor (reduce_only/post_only/flags)"

        return True, None

    def suggest_paper_trading_symbol(self, symbol: str) -> str | None:
        """
        Föreslår en motsvarande paper trading symbol.

        Args:
            symbol: Original symbol (t.ex. "tBTCUSD")

        Returns:
            Optional[str]: Motsvarande paper trading symbol eller None
        """
        # Om det redan är en paper trading symbol
        if symbol in self.paper_symbol_names:
            return symbol

        # Försök matcha med en liknande paper trading symbol
        base_currency = None
        quote_currency = None

        # Extrahera base/quote från vanliga symboler
        if symbol.startswith("t"):
            if ":" in symbol:
                parts = symbol[1:].split(":")
                base_currency, quote_currency = parts[0], parts[1]
            else:
                # Antar format som tBTCUSD
                symbol_clean = symbol[1:]  # Ta bort 't'
                if len(symbol_clean) >= 6:
                    base_currency = symbol_clean[:-3]
                    quote_currency = symbol_clean[-3:]

        if base_currency and quote_currency:
            # Sök efter matchande paper trading symbol
            for paper_symbol in self.paper_symbol_names:
                if "TEST" + base_currency in paper_symbol or base_currency in paper_symbol:
                    return paper_symbol

            # Fallback till standard test symbol
            return "tTESTBTC:TESTUSD"

        return None

    def format_order_for_bitfinex(self, order: dict[str, Any]) -> dict[str, Any]:
        """
        Formaterar en order för Bitfinex API.

        Args:
            order: Original orderdata

        Returns:
            Dict[str, Any]: Formaterad order för Bitfinex API
        """
        # Skapa en kopia för att undvika att modifiera originalet
        formatted_order = order.copy()

        # Standardvärden
        if "type" not in formatted_order:
            formatted_order["type"] = "EXCHANGE LIMIT"

        # Konvertera ordertyp till versaler
        formatted_order["type"] = formatted_order["type"].upper()

        # Hantera side parameter
        side = formatted_order.get("side")
        if isinstance(side, str):
            formatted_order["side"] = side.lower()
        elif side is None and "amount" in formatted_order:
            # Om side saknas men amount finns, bestäm side baserat på amount
            try:
                amount = float(formatted_order["amount"])
                formatted_order["side"] = "buy" if amount > 0 else "sell"
            except (ValueError, TypeError):
                formatted_order["side"] = "buy"  # Fallback

        # Konvertera amount till string om det är ett nummer
        if "amount" in formatted_order and not isinstance(formatted_order["amount"], str):
            formatted_order["amount"] = str(formatted_order["amount"])

        # Konvertera price till string om det är ett nummer och inte None
        if (
            "price" in formatted_order
            and formatted_order["price"] is not None
            and not isinstance(formatted_order["price"], str)
        ):
            formatted_order["price"] = str(formatted_order["price"])

        return formatted_order


# Singleton-instans för enkel åtkomst
order_validator = OrderValidator()
