#!/usr/bin/env python3
"""
Script för att automatiskt prenumerera på alla test-symboler
"""

import time

import requests

# Alla 16 test-symboler
TEST_SYMBOLS = [
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
]


def subscribe_symbol(symbol: str) -> None:
    """Prenumerera på en symbol"""
    url = "http://localhost:8000/api/v2/ws/subscribe"
    headers = {"Authorization": "Bearer test"}
    data = {"channel": "ticker", "symbol": symbol}

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"✅ Prenumererade på {symbol}")
            return True
        else:
            print(f"❌ Kunde inte prenumerera på {symbol}: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Fel vid prenumeration på {symbol}: {e}")
        return False


def main() -> None:
    """Huvudfunktion"""
    print("🚀 Startar prenumeration på alla test-symboler...")

    successful = 0
    for symbol in TEST_SYMBOLS:
        if subscribe_symbol(symbol):
            successful += 1
        time.sleep(0.1)  # Kort paus mellan requests

    print(f"\n📊 Resultat: {successful}/{len(TEST_SYMBOLS)} symboler prenumererade")

    if successful == len(TEST_SYMBOLS):
        print("🎉 Alla symboler prenumererade framgångsrikt!")
    else:
        print("⚠️ Vissa symboler kunde inte prenumereras")


if __name__ == "__main__":
    main()
