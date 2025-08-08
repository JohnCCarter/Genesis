"""
Nonce Validation - TradingBot Backend

Denna modul tillhandahåller verktyg för att validera och felsöka nonce-generering
för både REST och WebSocket API. Den hjälper till att säkerställa att nonce-värden
följer Bitfinex API-krav om strikt ökande värden.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from utils.nonce_manager import get_nonce, NONCE_FILE
from utils.logger import get_logger

logger = get_logger(__name__)


def get_last_nonces() -> Dict[str, int]:
    """
    Hämtar senaste nonce-värden för alla API-nycklar.
    
    Returns:
        Dict[str, int]: Dict med API-nyckel och dess senaste nonce
    """
    if not NONCE_FILE.exists():
        return {}
        
    try:
        with open(NONCE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Fel vid läsning av nonce-fil: {e}")
        return {}


def test_nonce_generation(key_id: str, count: int = 10) -> List[Tuple[str, int]]:
    """
    Testar nonce-generering för en API-nyckel.
    
    Args:
        key_id: API-nyckel
        count: Antal nonce-värden att generera
        
    Returns:
        List[Tuple[str, int]]: Lista med (nonce, differens) för varje genererat nonce
    """
    results = []
    prev_nonce = 0
    
    for _ in range(count):
        nonce = get_nonce(key_id)
        nonce_int = int(nonce)
        diff = nonce_int - prev_nonce if prev_nonce > 0 else 0
        results.append((nonce, diff))
        prev_nonce = nonce_int
        time.sleep(0.001)  # Liten paus mellan genereringar
    
    return results


def validate_nonce_format(nonce: str, api_type: str = "rest") -> Tuple[bool, Optional[str]]:
    """
    Validerar formatet på ett nonce-värde.
    
    Args:
        nonce: Nonce-värde att validera
        api_type: Typ av API ('rest' eller 'ws')
        
    Returns:
        Tuple[bool, Optional[str]]: (är giltig, felmeddelande)
    """
    try:
        nonce_int = int(nonce)
        
        # Kontrollera att värdet är positivt
        if nonce_int <= 0:
            return False, "Nonce måste vara ett positivt heltal"
        
        # Kontrollera maxgräns (MAX_SAFE_INTEGER i JavaScript)
        if nonce_int > 9007199254740991:  # 2^53 - 1
            return False, "Nonce överstiger MAX_SAFE_INTEGER (9007199254740991)"
        
        # Kontrollera precision för API-typ
        timestamp_now = datetime.now().timestamp()
        
        if api_type.lower() == "rest":
            # REST API använder mikrosekunder
            expected_digits = len(str(int(timestamp_now * 1_000_000)))
            actual_digits = len(nonce)
            
            if abs(expected_digits - actual_digits) > 1:
                return False, f"REST nonce bör ha ca {expected_digits} siffror (mikrosekunder), men har {actual_digits}"
                
        elif api_type.lower() == "ws":
            # WebSocket API använder millisekunder
            expected_digits = len(str(int(timestamp_now * 1_000)))
            actual_digits = len(nonce)
            
            if abs(expected_digits - actual_digits) > 1:
                return False, f"WebSocket nonce bör ha ca {expected_digits} siffror (millisekunder), men har {actual_digits}"
        
        return True, None
        
    except ValueError:
        return False, "Nonce måste vara ett giltigt heltal"


def print_nonce_statistics(key_id: str, count: int = 5):
    """
    Skriver ut statistik om nonce-generering för en API-nyckel.
    """
    print(f"\n===== Nonce-statistik för API-nyckel: {key_id[:10]}... =====")
    
    # Hämta senaste nonce från fil
    nonces = get_last_nonces()
    last_nonce = nonces.get(key_id, "Ingen tidigare nonce")
    print(f"Senaste lagrade nonce: {last_nonce}")
    
    # Generera nya nonces
    print(f"\nGenererar {count} nya nonce-värden:")
    results = test_nonce_generation(key_id, count)
    
    for i, (nonce, diff) in enumerate(results):
        is_valid_rest, rest_error = validate_nonce_format(nonce, "rest")
        is_valid_ws, ws_error = validate_nonce_format(nonce, "ws")
        
        print(f"  {i+1}. Nonce: {nonce}")
        print(f"     Differens: +{diff}")
        print(f"     Giltig för REST API: {'✅' if is_valid_rest else '❌'} {rest_error or ''}")
        print(f"     Giltig för WebSocket API: {'✅' if is_valid_ws else '❌'} {ws_error or ''}")
    
    # Visa tid- och värdeinfo
    now = datetime.now()
    timestamp_ms = int(now.timestamp() * 1_000)
    timestamp_us = int(now.timestamp() * 1_000_000)
    
    print("\nTidsstämplar:")
    print(f"  Nuvarande tid: {now}")
    print(f"  Millisekunder (WebSocket): {timestamp_ms}")
    print(f"  Mikrosekunder (REST): {timestamp_us}")
    
    print("\nRekommendation:")
    rest_nonce = get_nonce(f"{key_id}_rest")
    ws_nonce_micro = get_nonce(f"{key_id}_ws")
    ws_nonce_milli = str(int(int(ws_nonce_micro) / 1_000))
    
    print(f"  REST nonce (mikrosekunder): {rest_nonce}")
    print(f"  WebSocket nonce (millisekunder): {ws_nonce_milli}")
    print(f"  WebSocket nonce (original mikrosekunder): {ws_nonce_micro}")


if __name__ == "__main__":
    # Exempel på användning
    print_nonce_statistics("test_api_key", 5)
    print("\nKör med din egen API-nyckel genom att anropa:")
    print("  python -m utils.nonce_validation YOUR_API_KEY")
