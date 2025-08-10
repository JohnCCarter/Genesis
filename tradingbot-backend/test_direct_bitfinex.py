import pytest

pytestmark = pytest.mark.skip(
    reason="Legacy direct Bitfinex test – skipped in current backend focus"
)
"""
Test Direct Bitfinex API - TradingBot Backend

Denna fil testar riktiga orderläggning direkt mot Bitfinex API utan backend-server.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

# Ladda miljövariabler
load_dotenv()

# API credentials
API_KEY = os.getenv("BITFINEX_API_KEY")
API_SECRET = os.getenv("BITFINEX_API_SECRET")


def _build_authentication_headers(endpoint, payload=None):
    import time

    nonce = str(
        int(time.time() * 1_000_000)
    )  # Mikrosekunder för att säkerställa unikhet

    message = f"/api/v2/{endpoint}{nonce}"

    if payload != None:
        message += json.dumps(payload)

    signature = hmac.new(
        key=API_SECRET.encode("utf8"),
        msg=message.encode("utf8"),
        digestmod=hashlib.sha384,
    ).hexdigest()

    return {"bfx-apikey": API_KEY, "bfx-nonce": nonce, "bfx-signature": signature}


def place_order_direct():
    """Placerar en order direkt mot Bitfinex API."""

    if not API_KEY or not API_SECRET:
        print("❌ API-nycklar saknas i .env filen!")
        return

    print(f"✅ API Key status: {'✅ Konfigurerad' if API_KEY else '❌ Saknas'}")
    print(f"✅ API Secret status: {'✅ Konfigurerad' if API_SECRET else '❌ Saknas'}")

    # API endpoint
    url = "https://api.bitfinex.com/v2/auth/w/order/submit"

    # Order payload
    payload = {
        "type": "EXCHANGE LIMIT",
        "symbol": "tTESTBTC:TESTUSD",
        "amount": "0.002",  # Mycket liten mängd för test
        "price": "113000",  # Lågt pris för att undvika execution
        "lev": 0,
        "price_trailing": "",
        "price_aux_limit": "",
        "price_oco_stop": "",
        "gid": 0,
        "cid": 0,
        "flags": 0,
        "tif": "",
        "meta": {"aff_code": "", "make_visible": 0},
    }

    # Skapa autentiseringsheaders
    auth_headers = _build_authentication_headers("auth/w/order/submit", payload)

    # Kombinera headers
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        **auth_headers,
    }

    print("\n📋 Lägger en LIMIT order direkt mot Bitfinex...")
    print(f"🔍 Symbol: {payload['symbol']}")
    print(f"🔍 Amount: {payload['amount']}")
    print(f"🔍 Price: {payload['price']}")
    print(f"🔍 Type: {payload['type']}")

    try:
        response = requests.post(url, json=payload, headers=headers)

        print(f"\n🔍 Response Status: {response.status_code}")
        print(f"🔍 Response Headers: {dict(response.headers)}")
        print(f"🔍 Response Body: {response.text}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Order lagd framgångsrikt!")
            print(f"🔍 Order Result: {json.dumps(result, indent=2)}")

            # Om ordern blev lagd, försök stänga den
            if isinstance(result, list) and len(result) > 0:
                order_id = (
                    result[0].get("id") if isinstance(result[0], dict) else result[0]
                )
                if order_id:
                    print(f"\n❌ Stänger order {order_id}...")
                    cancel_order_direct(order_id)

        else:
            print(f"❌ Orderläggning misslyckades: {response.status_code}")
            print(f"❌ Error: {response.text}")

    except Exception as e:
        print(f"❌ Exception: {e}")


def cancel_order_direct(order_id):
    """Stänger en order direkt mot Bitfinex API."""

    url = "https://api.bitfinex.com/v2/auth/w/order/cancel"

    payload = {"id": order_id}

    # Skapa autentiseringsheaders
    auth_headers = _build_authentication_headers("auth/w/order/cancel", payload)

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        **auth_headers,
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        print(f"🔍 Cancel Response Status: {response.status_code}")
        print(f"🔍 Cancel Response: {response.text}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Order stängd framgångsrikt!")
            print(f"🔍 Cancel Result: {json.dumps(result, indent=2)}")
        else:
            print(f"❌ Orderstängning misslyckades: {response.status_code}")

    except Exception as e:
        print(f"❌ Exception vid stängning: {e}")


def test_market_order():
    """Testar en MARKET order."""

    url = "https://api.bitfinex.com/v2/auth/w/order/submit"

    payload = {
        "type": "EXCHANGE MARKET",
        "symbol": "tBTCUSD",
        "amount": "0.001",  # Mycket liten mängd för test
        "lev": 0,
        "price_trailing": "",
        "price_aux_limit": "",
        "price_oco_stop": "",
        "gid": 0,
        "cid": 0,
        "flags": 0,
        "tif": "",
        "meta": {"aff_code": "", "make_visible": 0},
    }

    # Skapa autentiseringsheaders
    auth_headers = _build_authentication_headers("auth/w/order/submit", payload)

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        **auth_headers,
    }

    print("\n📋 Lägger en MARKET order direkt mot Bitfinex...")
    print(f"🔍 Symbol: {payload['symbol']}")
    print(f"🔍 Amount: {payload['amount']}")
    print(f"🔍 Type: {payload['type']}")

    try:
        response = requests.post(url, json=payload, headers=headers)

        print(f"🔍 Response Status: {response.status_code}")
        print(f"🔍 Response: {response.text}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ MARKET order lagd framgångsrikt!")
            print(f"⚠️  MARKET orders kan bli executed direkt!")
            print(f"🔍 Order Result: {json.dumps(result, indent=2)}")
        else:
            print(f"❌ MARKET orderläggning misslyckades: {response.status_code}")

    except Exception as e:
        print(f"❌ Exception: {e}")


def main():
    """Huvudfunktion för direkta API-tester."""
    print("🚀 Startar direkta Bitfinex API-tester...")
    print("⚠️  VARNING: Detta kommer att lägga riktiga orders på ditt sub-account!")
    print("⚠️  Använd endast små mängder för testning!")

    # Testa LIMIT order
    place_order_direct()

    # Vänta lite mellan testerna
    print("\n⏳ Väntar 3 sekunder...")
    time.sleep(3)

    # Testa MARKET order
    test_market_order()

    print("\n🎉 Alla direkta API-tester slutförda!")


if __name__ == "__main__":
    main()
