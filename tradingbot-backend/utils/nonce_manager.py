import json
import time
from pathlib import Path
from threading import Lock

# Använd utils-mappen för nonce-filen
NONCE_FILE = Path(__file__).parent / ".nonce_tracker.json"
_lock = Lock()


def get_nonce(key_id: str) -> str:
    """Returnerar en strikt ökande nonce per API-nyckel med mikrosekunder"""
    # Använd mikrosekunder (16 siffror) för att säkerställa att vi alltid
    # ligger över ev. historiska ms‑baserade nonces på servern
    now = int(time.time() * 1_000_000)

    with _lock:
        try:
            if NONCE_FILE.exists():
                with open(NONCE_FILE, encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:  # Tom fil
                        data = {}
                    else:
                        data = json.loads(content)
            else:
                data = {}

            last_nonce = data.get(key_id, 0)
            # Säkerställ att ny nonce alltid är större än föregående
            new_nonce = max(now, last_nonce + 1)
            data[key_id] = new_nonce

            # Skapa utils-mappen om den inte finns
            NONCE_FILE.parent.mkdir(exist_ok=True)

            # Windows-säker skrivning (utan atomisk replace som failar)
            try:
                with open(NONCE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except (OSError, PermissionError):
                # Fallback: direkt skrivning utan temp-fil
                print(f"⚠️ Kunde inte skriva nonce-fil, använder fallback")
                pass

            return str(new_nonce)

        except (OSError, json.JSONDecodeError, ValueError) as e:
            # Om filen är korrupt, starta om med nuvarande tid
            print(f"⚠️  Nonce-fil problem: {e}. Startar om med nuvarande tid.")
            new_nonce = now
            data = {key_id: new_nonce}

            try:
                NONCE_FILE.parent.mkdir(exist_ok=True)
                with open(NONCE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except OSError:
                print("❌ Kunde inte skapa nonce-fil. Använder nuvarande tid.")

            return str(new_nonce)


def bump_nonce(key_id: str, min_increment_micro: int = 1_000_000) -> str:
    """Bumpar lagrad nonce rejält för angiven key_id för att passera serverns cached värde.

    Detta används när Bitfinex svarar med "nonce: small" (10114). Vi höjer den lokala noncen
    med minst min_increment_micro och säkerställer att den även ligger över current time.

    Args:
        key_id: API‑nyckelns identifierare (oftast själva API‑KEY strängen)
        min_increment_micro: Minsta bump i mikrosekunder (default 1e6 ≈ 1s)

    Returns:
        str: Den nya bumpade noncen (som str)
    """
    now = int(time.time() * 1_000_000)
    with _lock:
        try:
            data = {}
            if NONCE_FILE.exists():
                try:
                    with open(NONCE_FILE, encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            data = json.loads(content)
                except Exception:
                    data = {}

            last_nonce = int(data.get(key_id, 0) or 0)
            target = max(last_nonce + int(min_increment_micro), now + int(min_increment_micro))
            data[key_id] = target

            NONCE_FILE.parent.mkdir(exist_ok=True)
            try:
                with open(NONCE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except (OSError, PermissionError):
                pass

            return str(target)
        except Exception:
            # Fallback: returnera en bump på now + min_increment
            return str(now + int(min_increment_micro))
