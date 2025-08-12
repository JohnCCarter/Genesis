import pytest

pytestmark = pytest.mark.skip(reason="Legacy HTTP tests – skipped; use manual smoke tests in README")
"""
Test Wallets - TradingBot Backend

Denna fil testar plånboksfunktionaliteten mot Bitfinex API.
"""

import hashlib
import hmac
import json
import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

# Lägg till projektets rot i Python-sökvägen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ladda miljövariabler från .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

API = "https://api.bitfinex.com/v2"

API_KEY = os.getenv("BITFINEX_API_KEY")
API_SECRET = os.getenv("BITFINEX_API_SECRET")


def build_auth_headers(endpoint, payload=None):
    """Bygger autentiseringsheaders för Bitfinex API"""
    # Använd mikrosekunder för nonce
    nonce = str(int(datetime.now().timestamp() * 1_000_000))

    # Bygg message enligt Bitfinex dokumentation
    message = f"/api/v2/{endpoint}{nonce}"

    if payload != None:
        message += json.dumps(payload)

    signature = hmac.new(
        key=API_SECRET.encode("utf8"),
        msg=message.encode("utf8"),
        digestmod=hashlib.sha384,
    ).hexdigest()

    return {"bfx-apikey": API_KEY, "bfx-nonce": nonce, "bfx-signature": signature}


def test_get_wallets():
    """Hämtar plånboksinformation från Bitfinex API"""
    endpoint = "auth/r/wallets"

    headers = {"Content-Type": "application/json", **build_auth_headers(endpoint)}

    print("\n📋 Hämtar plånboksinformation...")

    response = requests.post(f"{API}/{endpoint}", headers=headers)

    print(f"🔍 Status: {response.status_code}")

    if response.status_code == 200:
        wallets = response.json()
        print(f"✅ Hittade {len(wallets)} plånböcker:")

        for wallet in wallets:
            wallet_type = wallet[0]
            currency = wallet[1]
            balance = wallet[2]

            print(f"  - {wallet_type} {currency}: {balance}")

        return wallets
    else:
        print(f"❌ Fel: {response.text}")
        return None


if __name__ == "__main__":
    print("🚀 Startar plånbokstest...")
    test_get_wallets()
    print("\n🎉 Test slutfört!")
