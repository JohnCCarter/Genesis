import pytest

pytestmark = pytest.mark.skip(reason="Legacy scraper-coupled test – skipped in CI")
"""
Test för Order Validator.

Dessa tester verifierar att OrderValidator fungerar korrekt
och kan validera orderparametrar mot Bitfinex API-krav.
"""

import os
import sys
import unittest
from unittest import mock

# Lägg till projektets rot i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rest.order_validator import OrderValidator


class TestOrderValidator(unittest.TestCase):
    """Testfall för OrderValidator."""

    def setUp(self):
        """Förbered testmiljö."""
        # Skapa en instans av validator med mockad scraper
        with mock.patch("scraper.bitfinex_docs.BitfinexDocsScraper") as mock_scraper:
            # Konfigurera mock för fetch_order_types
            mock_scraper.return_value.fetch_order_types.return_value = {
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
            }

            # Konfigurera mock för fetch_symbols
            mock_scraper.return_value.fetch_symbols.return_value = [
                {"symbol": "tBTCUSD"},
                {"symbol": "tETHUSD"},
                {"symbol": "tTESTBTC:TESTUSD", "is_paper": True},
                {"symbol": "tTESTETH:TESTUSD", "is_paper": True},
            ]

            # Konfigurera mock för get_paper_trading_symbols
            mock_scraper.return_value.get_paper_trading_symbols.return_value = [
                {"symbol": "tTESTBTC:TESTUSD", "is_paper": True},
                {"symbol": "tTESTETH:TESTUSD", "is_paper": True},
            ]

            self.validator = OrderValidator()

    def test_validate_valid_limit_order(self):
        """Testa validering av en giltig limit order."""
        order = {
            "type": "EXCHANGE LIMIT",
            "symbol": "tBTCUSD",
            "amount": "0.001",
            "price": "50000",
        }

        is_valid, error = self.validator.validate_order(order)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_valid_market_order(self):
        """Testa validering av en giltig market order."""
        order = {"type": "EXCHANGE MARKET", "symbol": "tBTCUSD", "amount": "0.001"}

        is_valid, error = self.validator.validate_order(order)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_invalid_order_type(self):
        """Testa validering av en order med ogiltig ordertyp."""
        order = {
            "type": "INVALID_TYPE",
            "symbol": "tBTCUSD",
            "amount": "0.001",
            "price": "50000",
        }

        is_valid, error = self.validator.validate_order(order)
        self.assertFalse(is_valid)
        self.assertIn("Ogiltig ordertyp", error)

    def test_validate_invalid_symbol(self):
        """Testa validering av en order med ogiltig symbol."""
        order = {
            "type": "EXCHANGE LIMIT",
            "symbol": "tINVALIDSYMBOL",
            "amount": "0.001",
            "price": "50000",
        }

        is_valid, error = self.validator.validate_order(order)
        self.assertFalse(is_valid)
        self.assertIn("Ogiltig symbol", error)

    def test_validate_missing_required_param(self):
        """Testa validering av en order som saknar en krävd parameter."""
        # Saknar pris för limit order
        order = {"type": "EXCHANGE LIMIT", "symbol": "tBTCUSD", "amount": "0.001"}

        is_valid, error = self.validator.validate_order(order)
        self.assertFalse(is_valid)
        self.assertIn("Saknad parameter", error)

    def test_validate_zero_amount(self):
        """Testa validering av en order med nollbelopp."""
        order = {
            "type": "EXCHANGE LIMIT",
            "symbol": "tBTCUSD",
            "amount": "0",
            "price": "50000",
        }

        is_valid, error = self.validator.validate_order(order)
        self.assertFalse(is_valid)
        self.assertIn("Belopp kan inte vara noll", error)

    def test_validate_negative_price(self):
        """Testa validering av en order med negativt pris."""
        order = {
            "type": "EXCHANGE LIMIT",
            "symbol": "tBTCUSD",
            "amount": "0.001",
            "price": "-50000",
        }

        is_valid, error = self.validator.validate_order(order)
        self.assertFalse(is_valid)
        self.assertIn("Pris måste vara större än noll", error)

    def test_suggest_paper_trading_symbol(self):
        """Testa förslag på paper trading symbol."""
        # Redan paper trading symbol
        self.assertEqual(
            self.validator.suggest_paper_trading_symbol("tTESTBTC:TESTUSD"),
            "tTESTBTC:TESTUSD",
        )

        # Vanlig symbol
        self.assertEqual(
            self.validator.suggest_paper_trading_symbol("tBTCUSD"), "tTESTBTC:TESTUSD"
        )

    def test_format_order_for_bitfinex(self):
        """Testa formatering av order för Bitfinex API."""
        order = {"symbol": "tBTCUSD", "amount": 0.001, "price": 50000, "side": "BUY"}

        formatted = self.validator.format_order_for_bitfinex(order)

        self.assertEqual(formatted["type"], "EXCHANGE LIMIT")  # Default type
        self.assertEqual(formatted["side"], "buy")  # Lowercase
        self.assertEqual(formatted["amount"], "0.001")  # String
        self.assertEqual(formatted["price"], "50000")  # String


if __name__ == "__main__":
    unittest.main()
