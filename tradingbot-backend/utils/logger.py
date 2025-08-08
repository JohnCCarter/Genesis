"""
Logger Utility - TradingBot Backend

Denna modul tillhandahåller centraliserad loggning för applikationen.
Inkluderar konfigurerad loggning med olika nivåer och formatering.
"""

import logging
import sys
from typing import Optional
from datetime import datetime


class SafeFormatter(logging.Formatter):
    """Formatter som sanerar tecken som inte kan skrivas till konsolen.

    På Windows kan konsolens encoding vara cp1252 vilket inte stödjer emojis.
    Denna formatter ersätter icke-stödda tecken med '?' så loggningen inte kraschar.
    """

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        try:
            # Försök round-trip i aktuell encoding; ersätt otillåtna tecken
            return msg.encode(encoding, errors="replace").decode(encoding, errors="replace")
        except Exception:
            # Sista utväg: ASCII utan specialtecken
            return msg.encode("ascii", errors="replace").decode("ascii", errors="replace")

def get_logger(name: str) -> logging.Logger:
    """
    Skapar och konfigurerar en logger för den angivna modulen.
    
    Args:
        name: Modulnamn (t.ex. __name__)
        
    Returns:
        logging.Logger: Konfigurerad logger
    """
    logger = logging.getLogger(name)
    
    # Undvik att lägga till handlers flera gånger
    if not logger.handlers:
        # Skapa formatter (säker för Windows-konsol)
        formatter = SafeFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Skapa console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Sätt loggningsnivå
        logger.setLevel(logging.INFO)
    
    return logger 