import pytest

pytestmark = pytest.mark.skip(reason="Legacy WS order handler test – skipped in CI")
"""
Test för WebSocket Order Handler.

Dessa tester verifierar att WSOrderHandler fungerar korrekt
och kan hantera orderoperationer via Bitfinex WebSocket API.
"""

import json
import os
import sys
import unittest
from unittest import mock

# Lägg till projektets rot i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ws.order_handler import WSOrderHandler


class MockWebSocket:
    """Mock för WebSocket-anslutning."""

    def __init__(self):
        self.sent_messages = []

    async def send(self, message):
        """Registrerar skickade meddelanden."""
        self.sent_messages.append(message)
        return True


class TestWSOrderHandler(unittest.IsolatedAsyncioTestCase):
    """Testfall för WSOrderHandler."""

    async def asyncSetUp(self):
        """Förbered testmiljö."""
        # Skapa en mock för WebSocket
        self.mock_ws = MockWebSocket()

        # Skapa en instans av WSOrderHandler med mockad WebSocket
        self.handler = WSOrderHandler(self.mock_ws)

        # Mocka order_validator
        self.mock_validator = mock.Mock()
        self.handler.order_validator = self.mock_validator

        # Sätt authenticated till True för att testa orderoperationer
        self.handler.authenticated = True

    async def test_authenticate(self):
        """Testa autentisering via WebSocket."""
        with mock.patch("ws.order_handler.build_ws_auth_payload", return_value='{"event":"auth"}'):
            result = await self.handler.authenticate()

            # Kontrollera att autentiseringsmeddelandet skickades
            self.assertTrue(result)
            self.assertEqual(len(self.mock_ws.sent_messages), 1)
            self.assertEqual(self.mock_ws.sent_messages[0], '{"event":"auth"}')

    async def test_place_order_valid(self):
        """Testa att lägga en giltig order via WebSocket."""
        # Konfigurera mock för validate_order
        self.mock_validator.validate_order.return_value = (True, None)

        # Konfigurera mock för format_order_for_bitfinex
        self.mock_validator.format_order_for_bitfinex.return_value = {
            "type": "EXCHANGE LIMIT",
            "symbol": "tBTCUSD",
            "amount": "0.001",
            "price": "50000",
        }

        # Testa att lägga en order
        success, error = await self.handler.place_order(
            {"symbol": "tBTCUSD", "amount": "0.001", "price": "50000"}
        )

        # Kontrollera resultatet
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(len(self.mock_ws.sent_messages), 1)

        # Kontrollera att meddelandet har rätt format
        sent_message = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(sent_message[0], 0)
        self.assertEqual(sent_message[1], "on")
        self.assertIsNone(sent_message[2])
        self.assertEqual(sent_message[3]["symbol"], "tBTCUSD")
        self.assertEqual(sent_message[3]["amount"], "0.001")
        self.assertEqual(sent_message[3]["price"], "50000")

    async def test_place_order_invalid(self):
        """Testa att lägga en ogiltig order via WebSocket."""
        # Konfigurera mock för validate_order
        self.mock_validator.validate_order.return_value = (False, "Ogiltig symbol")

        # Testa att lägga en order
        success, error = await self.handler.place_order(
            {"symbol": "INVALID", "amount": "0.001", "price": "50000"}
        )

        # Kontrollera resultatet
        self.assertFalse(success)
        self.assertEqual(error, "Ogiltig symbol")
        self.assertEqual(len(self.mock_ws.sent_messages), 0)  # Inget meddelande skickat

    async def test_place_order_not_authenticated(self):
        """Testa att lägga en order utan autentisering."""
        # Sätt authenticated till False
        self.handler.authenticated = False

        # Testa att lägga en order
        success, error = await self.handler.place_order(
            {"symbol": "tBTCUSD", "amount": "0.001", "price": "50000"}
        )

        # Kontrollera resultatet
        self.assertFalse(success)
        self.assertEqual(error, "WebSocket inte autentiserad")
        self.assertEqual(len(self.mock_ws.sent_messages), 0)  # Inget meddelande skickat

    async def test_cancel_order(self):
        """Testa att avbryta en order via WebSocket."""
        # Testa att avbryta en order
        success, error = await self.handler.cancel_order(12345)

        # Kontrollera resultatet
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(len(self.mock_ws.sent_messages), 1)

        # Kontrollera att meddelandet har rätt format
        sent_message = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(sent_message[0], 0)
        self.assertEqual(sent_message[1], "oc")
        self.assertIsNone(sent_message[2])
        self.assertEqual(sent_message[3]["id"], 12345)

    async def test_get_active_orders(self):
        """Testa att hämta aktiva order via WebSocket."""
        # Testa att hämta aktiva order
        success, orders, error = await self.handler.get_active_orders()

        # Kontrollera resultatet
        self.assertTrue(success)
        self.assertIsNone(orders)  # Svaret hanteras via callback
        self.assertIsNone(error)
        self.assertEqual(len(self.mock_ws.sent_messages), 1)

        # Kontrollera att meddelandet har rätt format
        sent_message = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(sent_message[0], 0)
        self.assertEqual(sent_message[1], "os")
        self.assertIsNone(sent_message[2])
        self.assertEqual(sent_message[3], {})


if __name__ == "__main__":
    unittest.main()
