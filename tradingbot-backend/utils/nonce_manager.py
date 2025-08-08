import json
import os
import time
from threading import Lock
from pathlib import Path

# Använd utils-mappen för nonce-filen
NONCE_FILE = Path(__file__).parent / ".nonce_tracker.json"
_lock = Lock()

def get_nonce(key_id: str) -> str:
    """Returnerar en strikt ökande nonce per API-nyckel med mikrosekunder"""
    now = int(time.time() * 1_000_000)  # Mikrosekunder för Bitfinex

    with _lock:
        try:
            if NONCE_FILE.exists():
                with open(NONCE_FILE, "r") as f:
                    data = json.load(f)
            else:
                data = {}

            last_nonce = data.get(key_id, 0)
            new_nonce = max(now, last_nonce + 1)
            data[key_id] = new_nonce

            # Skapa utils-mappen om den inte finns
            NONCE_FILE.parent.mkdir(exist_ok=True)
            
            with open(NONCE_FILE, "w") as f:
                json.dump(data, f)

            return str(new_nonce)
            
        except (json.JSONDecodeError, IOError) as e:
            # Om filen är korrupt, starta om med nuvarande tid
            print(f"⚠️  Nonce-fil problem: {e}. Startar om med nuvarande tid.")
            new_nonce = now
            data = {key_id: new_nonce}
            
            try:
                NONCE_FILE.parent.mkdir(exist_ok=True)
                with open(NONCE_FILE, "w") as f:
                    json.dump(data, f)
            except IOError:
                print("❌ Kunde inte skapa nonce-fil. Använder nuvarande tid.")
            
            return str(new_nonce)
