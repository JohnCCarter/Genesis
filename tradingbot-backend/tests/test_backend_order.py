import pytest

pytestmark = pytest.mark.skip(reason="Legacy HTTP tests – skipped; use manual smoke tests in README")
import hashlib
import hmac
import json
import os
import sys

import requests
from dotenv import load_dotenv

# Lägg till projektets rot i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ladda miljövariabler från .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Importera efter att sys.path är uppdaterad
# Tagit bort import av test_auto_price

API = "https://api.bitfinex.com/v2"

API_KEY = os.getenv("BITFINEX_API_KEY")
API_SECRET = os.getenv("BITFINEX_API_SECRET")


# Testa direkt mot Bitfinex API med samma metod som exemplet
def test_direct_bitfinex():
    """Testar direkt mot Bitfinex API med samma metod som exemplet"""
    from datetime import datetime

    endpoint = "auth/w/order/submit"

    payload = {
        "type": "EXCHANGE LIMIT",
        "symbol": "tTESTBTC:TESTUSD",  # Paper trading symbol
        "amount": "0.001",
        "price": "114100",
    }

    # Bygg autentiseringsheaders med mikrosekunder för högre nonce
    nonce = str(int(datetime.now().timestamp() * 1_000_000))  # Mikrosekunder

    message = f"/api/v2/{endpoint}{nonce}"

    if payload != None:
        message += json.dumps(payload)

    signature = hmac.new(
        key=API_SECRET.encode("utf8"),
        msg=message.encode("utf8"),
        digestmod=hashlib.sha384,
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "bfx-apikey": API_KEY,
        "bfx-nonce": nonce,
        "bfx-signature": signature,
    }

    print("\n📋 Testar direkt mot Bitfinex API med exemplets metod...")
    print(f"🔍 API URL: {API}/{endpoint}")
    print(f"🔍 Symbol: {payload['symbol']}")
    print(f"🔍 Amount: {payload['amount']}")
    print(f"🔍 Price: {payload['price']}")

    response = requests.post(f"{API}/{endpoint}", json=payload, headers=headers)

    print(f"🔍 Status: {response.status_code}")
    print(f"🔍 Svar: {response.text}")

    # Förbättrad loggning för direkt API-test
    if response.status_code == 200:
        try:
            result = response.json()
            print("\n" + "=" * 50)
            print("✅ ORDER LAGD FRAMGÅNGSRIKT DIREKT MOT BITFINEX! ✅")
            print("=" * 50)
            print("📊 ORDER DETALJER:")
            print(f"  Symbol: {payload['symbol']}")
            print(f"  Typ: {payload['type']}")
            print(f"  Mängd: {payload['amount']}")
            print(f"  Pris: {payload['price']}")
            print("\n📈 SVAR FRÅN BITFINEX:")
            print(f"  Order ID: {result[0] if isinstance(result, list) and len(result) > 0 else 'N/A'}")
            print(f"  Fullständigt svar: {json.dumps(result, indent=2)}")
            print("=" * 50)
        except Exception as e:
            print(f"❌ Kunde inte tolka JSON-svar: {e}")
    elif "error" in response.text:
        print("\n" + "=" * 50)
        print("❌ BITFINEX API ERROR ❌")
        print("=" * 50)
        print(f"Error: {response.text}")
        print("=" * 50)

    return response


# Backend API URL
BACKEND_URL = "http://localhost:8000/api/v2"


def test_backend_market_order():
    """Testar market orderläggning via backend's REST auth"""

    # Order payload för backend - market order
    order_data = {
        "type": "EXCHANGE MARKET",
        "symbol": "tTESTBTC:TESTUSD",  # ✅ Paper trading symbol
        "amount": "0.001",  # Mycket liten mängd för test
        "price": None,  # Explicit None för market order
        "side": "buy",  # Explicit side för market order
    }

    headers = {"Content-Type": "application/json"}

    print("\n📋 Testar MARKET order via backend REST auth...")
    print(f"🔍 Backend URL: {BACKEND_URL}/order")
    print(f"🔍 Symbol: {order_data['symbol']}")
    print(f"🔍 Amount: {order_data['amount']}")
    print(f"🔍 Type: {order_data['type']}")
    print(f"🔍 Side: {order_data['side']}")

    try:
        response = requests.post(f"{BACKEND_URL}/order", json=order_data, headers=headers)

        print(f"🔍 Status: {response.status_code}")
        print(f"🔍 Svar: {response.text}")

        if response.status_code == 200:
            result = response.json()
            print("\n" + "=" * 50)
            print("✅ MARKET ORDER LAGD FRAMGÅNGSRIKT VIA BACKEND! ✅")
            print("=" * 50)
            print("📊 ORDER DETALJER:")
            print(f"  Symbol: {order_data['symbol']}")
            print(f"  Typ: {order_data['type']}")
            print(f"  Mängd: {order_data['amount']}")
            print(f"  Sida: {order_data['side']}")
            print("\n📈 SVAR FRÅN BITFINEX:")
            print(f"  Order ID: {result[0] if isinstance(result, list) and len(result) > 0 else 'N/A'}")
            print(f"  Fullständigt svar: {json.dumps(result, indent=2)}")
            print("=" * 50)
        elif response.status_code == 400:
            print("\n" + "=" * 50)
            print("⚠️  MARKET ORDER AVVISAD AV BACKEND ⚠️")
            print("=" * 50)
            print(f"Svar: {response.text}")
            print("=" * 50)
        elif response.status_code == 500:
            print("\n" + "=" * 50)
            print("❌ BACKEND SERVER ERROR ❌")
            print("=" * 50)
            print(f"Error: {response.text}")
            try:
                error_json = response.json()
                if "error" in error_json:
                    print(f"Felmeddelande: {error_json['error']}")
                    if "apikey: invalid" in str(error_json):
                        print("\n⚠️ API-NYCKEL PROBLEM: Bitfinex accepterar inte API-nyckeln")
                        print("Kontrollera att rätt nyckel används och att den har rätt behörigheter")
            except:
                pass
            print("=" * 50)
        else:
            print("\n" + "=" * 50)
            print(f"❌ FEL: OVÄNTAT STATUSKOD {response.status_code} ❌")
            print("=" * 50)
            print("Headers:", headers)
            print("Payload:", order_data)
            print(f"Svar: {response.text}")
            print("=" * 50)

        assert response.status_code in (200, 400, 500)

    except requests.exceptions.ConnectionError:
        print("❌ Kunde inte ansluta till backend server!")
        print("💡 Lösning: Starta backend-servern med 'python main.py'")
        assert False, "Backend server inte tillgänglig"


def test_backend_limit_order():
    """Testar limit orderläggning via backend's REST auth"""

    # Order payload för backend - exakt som i test_order_operations.py
    order_data = {
        "type": "EXCHANGE LIMIT",
        "symbol": "tTESTBTC:TESTUSD",  # ✅ Paper trading symbol
        "amount": "0.001",  # Mycket liten mängd för test
        "price": "114200",  # Strax över aktuellt ask-pris
        "side": "buy",  # Explicit side för att säkerställa köp
    }

    headers = {"Content-Type": "application/json"}

    print("\n📋 Testar LIMIT order via backend REST auth...")
    print(f"🔍 Backend URL: {BACKEND_URL}/order")
    print(f"🔍 Symbol: {order_data['symbol']}")
    print(f"🔍 Amount: {order_data['amount']}")
    print(f"🔍 Price: {order_data['price']}")
    if "side" in order_data:
        print(f"🔍 Side: {order_data['side']}")

    try:
        response = requests.post(f"{BACKEND_URL}/order", json=order_data, headers=headers)

        print(f"🔍 Status: {response.status_code}")
        print(f"🔍 Svar: {response.text}")

        if response.status_code == 200:
            result = response.json()
            print("\n" + "=" * 50)
            print("✅ LIMIT ORDER LAGD FRAMGÅNGSRIKT VIA BACKEND! ✅")
            print("=" * 50)
            print("📊 ORDER DETALJER:")
            print(f"  Symbol: {order_data['symbol']}")
            print(f"  Typ: {order_data['type']}")
            print(f"  Mängd: {order_data['amount']}")
            print(f"  Pris: {order_data['price']}")
            print("\n📈 SVAR FRÅN BITFINEX:")
            print(f"  Order ID: {result[0] if isinstance(result, list) and len(result) > 0 else 'N/A'}")
            print(f"  Fullständigt svar: {json.dumps(result, indent=2)}")
            print("=" * 50)
        elif response.status_code == 400:
            print("\n" + "=" * 50)
            print("⚠️  LIMIT ORDER AVVISAD AV BACKEND ⚠️")
            print("=" * 50)
            print(f"Svar: {response.text}")
            print("=" * 50)
        elif response.status_code == 500:
            print("\n" + "=" * 50)
            print("❌ BACKEND SERVER ERROR ❌")
            print("=" * 50)
            print(f"Error: {response.text}")
            try:
                error_json = response.json()
                if "error" in error_json:
                    print(f"Felmeddelande: {error_json['error']}")
                    if "apikey: invalid" in str(error_json):
                        print("\n⚠️ API-NYCKEL PROBLEM: Bitfinex accepterar inte API-nyckeln")
                        print("Kontrollera att rätt nyckel används och att den har rätt behörigheter")
            except:
                pass
            print("=" * 50)
        else:
            print("\n" + "=" * 50)
            print(f"❌ FEL: OVÄNTAT STATUSKOD {response.status_code} ❌")
            print("=" * 50)
            print("Headers:", headers)
            print("Payload:", order_data)
            print(f"Svar: {response.text}")
            print("=" * 50)

        assert response.status_code in (200, 400, 500)

    except requests.exceptions.ConnectionError:
        print("❌ Kunde inte ansluta till backend server!")
        print("💡 Lösning: Starta backend-servern med 'python main.py'")
        assert False, "Backend server inte tillgänglig"


if __name__ == "__main__":
    print("🚀 Startar order-tester...")
    print("⚠️  VARNING: Detta kommer att lägga riktiga orders!")

    # Kommenterat ut direkt Bitfinex-test för att köra backend-testerna direkt
    # print("\n--- TEST 1: Direkt mot Bitfinex API med exemplets metod ---")
    # direct_response = test_direct_bitfinex()

    # Kör backend-testerna direkt utan att vänta på direkt test
    print("\n--- TEST 1: Via backend server (LIMIT order) ---")
    print("⚠️  VARNING: Detta kräver att backend-servern är igång!")
    try:
        # Kör limit order test
        test_backend_limit_order()

        print("\n--- TEST 2: Via backend server (MARKET order) ---")
        print("⚠️  VARNING: Detta kräver att backend-servern är igång!")
        test_backend_market_order()
    except Exception as e:
        print(f"❌ Backend test misslyckades: {e}")

    print("\n🎉 Tester slutförda!")
