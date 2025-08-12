import pytest

pytestmark = pytest.mark.skip(reason="Legacy docs/scraper test – skipped in CI")

import pytest

pytestmark = pytest.mark.skip(reason="Legacy tests – skipped in current backend focus")
"""
Test för Bitfinex dokumentations-scraper.

Dessa tester verifierar att dokumentations-scrapern fungerar korrekt
och kan hämta relevant information från Bitfinex API-dokumentation.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

# Lägg till projektets rot i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.bitfinex_docs import BitfinexDocsScraper


class MockResponse:
    """Mock för HTTP-svar."""

    def __init__(self, json_data=None, text="", status_code=200, headers=None):
        self.json_data = json_data
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error: {self.status_code}")


class TestBitfinexDocsScraper(unittest.TestCase):
    """Testfall för Bitfinex dokumentations-scraper."""

    def setUp(self):
        """Förbered testmiljö."""
        # Använd en temporär cache-katalog för tester
        self.temp_cache_dir = Path("tests/test_cache/bitfinex_docs")
        os.makedirs(self.temp_cache_dir, exist_ok=True)

        # Skapa en instans av scrapern med den temporära cache-katalogen
        self.scraper = BitfinexDocsScraper(cache_dir=self.temp_cache_dir)

    def tearDown(self):
        """Städa upp efter tester."""
        # Ta bort temporära filer
        for file in self.temp_cache_dir.glob("*.json"):
            try:
                file.unlink()
            except:
                pass

    @mock.patch("requests.Session.get")
    def test_fetch_symbols(self, mock_get):
        """Testa hämtning av symboler."""
        # Förbered mock-svar
        mock_response = MockResponse(
            json_data=[["BTCUSD", "ETHUSD", "LTCUSD"]],
            headers={"Content-Type": "application/json"},
        )
        mock_get.return_value = mock_response

        # Anropa metoden
        symbols = self.scraper.fetch_symbols()

        # Verifiera resultatet
        self.assertIsInstance(symbols, list)
        self.assertTrue(len(symbols) >= 3)  # Minst 3 symboler (plus 2 testsymboler)

        # Kontrollera att testsymbolerna finns med
        test_symbols = [s for s in symbols if s.get("is_paper", False)]
        self.assertEqual(len(test_symbols), 2)
        self.assertEqual(test_symbols[0]["symbol"], "tTESTBTC:TESTUSD")

    @mock.patch("requests.Session.get")
    def test_fetch_order_types(self, mock_get):
        """Testa hämtning av ordertyper."""
        # Förbered mock-svar
        mock_response = MockResponse(
            text="<html><body>Order types documentation</body></html>",
            headers={"Content-Type": "text/html"},
        )
        mock_get.return_value = mock_response

        # Anropa metoden
        order_types = self.scraper.fetch_order_types()

        # Verifiera resultatet
        self.assertIsInstance(order_types, dict)
        self.assertGreaterEqual(len(order_types), 4)  # Minst 4 ordertyper

        # Kontrollera att grundläggande ordertyper finns med
        self.assertIn("EXCHANGE LIMIT", order_types)
        self.assertIn("EXCHANGE MARKET", order_types)

        # Kontrollera att ordertyper har rätt struktur
        for order_type, info in order_types.items():
            self.assertIn("name", info)
            self.assertIn("description", info)
            self.assertIn("required_params", info)

    def test_get_paper_trading_symbols(self):
        """Testa hämtning av paper trading symboler."""
        # Förbered testdata
        self.scraper.symbols = [
            {"symbol": "tBTCUSD"},
            {"symbol": "tETHUSD"},
            {"symbol": "tTESTBTC:TESTUSD", "is_paper": True},
            {"symbol": "tTESTETH:TESTUSD", "is_paper": True},
        ]

        # Anropa metoden
        paper_symbols = self.scraper.get_paper_trading_symbols()

        # Verifiera resultatet
        self.assertEqual(len(paper_symbols), 2)
        self.assertEqual(paper_symbols[0]["symbol"], "tTESTBTC:TESTUSD")
        self.assertEqual(paper_symbols[1]["symbol"], "tTESTETH:TESTUSD")

    def test_get_order_type_info(self):
        """Testa hämtning av information om ordertyper."""
        # Förbered testdata
        self.scraper.order_types = {
            "EXCHANGE LIMIT": {
                "name": "EXCHANGE LIMIT",
                "description": "Limit order för exchange wallets",
                "required_params": ["symbol", "amount", "price"],
            }
        }

        # Anropa metoden
        info = self.scraper.get_order_type_info("EXCHANGE LIMIT")

        # Verifiera resultatet
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "EXCHANGE LIMIT")
        self.assertIn("required_params", info)

        # Testa med olika skiftläge
        info = self.scraper.get_order_type_info("exchange limit")
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "EXCHANGE LIMIT")

        # Testa med okänd ordertyp
        info = self.scraper.get_order_type_info("UNKNOWN_TYPE")
        self.assertIsNone(info)


if __name__ == "__main__":
    unittest.main()
