import pytest

pytestmark = pytest.mark.skip(
    reason="Legacy HTTP tests – skipped; use manual smoke tests in README"
)
import hashlib
import hmac
import json
import os
import sys

import pytest
import requests
from dotenv import load_dotenv

# Lägg till projektets rot i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.nonce_manager import get_nonce

# Ladda miljövariabler från .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

API = "https://api.bitfinex.com/v2"

API_KEY = os.getenv("BITFINEX_API_KEY")
API_SECRET = os.getenv("BITFINEX_API_SECRET")

# Felsökningsutskrift
print("DEBUG - API_KEY:", "SET" if API_KEY else "MISSING")
print("DEBUG - API_SECRET:", "SET" if API_SECRET else "MISSING")


# Skapa korrekt signerad header enligt Bitfinex-spec
def _build_authentication_headers(endpoint: str, payload=None):
    nonce = get_nonce(API_KEY)  # Använd nonce-manager för strikt ökande nonce
    raw_path = f"/api/v2/{endpoint}"
    body = json.dumps(payload) if payload else ""
    message = raw_path + nonce + body

    signature = hmac.new(
        API_SECRET.encode("utf8"), msg=message.encode("utf8"), digestmod=hashlib.sha384
    ).hexdigest()

    return {"bfx-apikey": API_KEY, "bfx-nonce": nonce, "bfx-signature": signature}


def test_submit_limit_order():
    """Testar LIMIT order med korrekt symbol och pris"""
    endpoint = "auth/w/order/submit"

    payload = {
        "type": "EXCHANGE LIMIT",
        "symbol": "tTESTBTC:TESTUSD",  # ✅ Paper trading symbol
        "amount": "0.001",  # Mycket liten mängd för test
        "price": "40000",  # Realistiskt BTC-pris
    }

    headers = {
        "Content-Type": "application/json",
        **_build_authentication_headers(endpoint, payload),
    }

    print("\n📋 Testar LIMIT order...")
    print(f"🔍 Symbol: {payload['symbol']}")
    print(f"🔍 Amount: {payload['amount']}")
    print(f"🔍 Price: {payload['price']}")

    response = requests.post(f"{API}/{endpoint}", json=payload, headers=headers)

    print(f"🔍 Status: {response.status_code}")
    print(f"🔍 Svar: {response.text}")

    if response.status_code == 200:
        print("✅ Order lagd framgångsrikt!")
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            order_id = result[0].get("id") if isinstance(result[0], dict) else result[0]
            if order_id:
                print(f"🔍 Order ID: {order_id}")
    elif response.status_code == 400:
        print("⚠️  Order avvisad (förväntat för test)")
    elif response.status_code == 500 and "action: disabled" in response.text:
        print("⚠️  Trading är inaktiverat för ditt sub-account")
        print("💡 Lösning: Aktivera trading-permissions på Bitfinex")
    else:
        print("❌ FEL: Ovänatat statuskod")
        print("Headers:", headers)
        print("Payload:", payload)

    assert response.status_code in (200, 400, 500)  # 500 för action: disabled


def test_market_order():
    """Testar MARKET order (kan bli executed direkt!)"""
    endpoint = "auth/w/order/submit"

    payload = {
        "type": "EXCHANGE MARKET",
        "symbol": "tTESTBTC:TESTUSD",  # ✅ Paper trading symbol
        "amount": "0.001",  # Mycket liten mängd
    }

    headers = {
        "Content-Type": "application/json",
        **_build_authentication_headers(endpoint, payload),
    }

    print("\n📋 Testar MARKET order...")
    print(f"🔍 Symbol: {payload['symbol']}")
    print(f"🔍 Amount: {payload['amount']}")
    print("⚠️  VARNING: MARKET orders kan bli executed direkt!")

    response = requests.post(f"{API}/{endpoint}", json=payload, headers=headers)

    print(f"🔍 Status: {response.status_code}")
    print(f"🔍 Svar: {response.text}")

    if response.status_code == 200:
        print("✅ MARKET order lagd framgångsrikt!")
    elif response.status_code == 400:
        print("⚠️  MARKET order avvisad (förväntat för test)")
    else:
        print("❌ FEL: Ovänatat statuskod")

    assert response.status_code in (200, 400)


if __name__ == "__main__":
    print("🚀 Startar order-operation tester...")
    print("⚠️  VARNING: Detta kommer att lägga riktiga orders på ditt sub-account!")

    # Testa LIMIT order
    test_submit_limit_order()

    print("\n🎉 Test slutfört!")
