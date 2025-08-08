"""
Logger Utility - TradingBot Backend

Denna modul tillhandahåller centraliserad loggning för applikationen.
Inkluderar konfigurerad loggning med olika nivåer och formatering.
"""

import logging
import sys
from typing import Optional
from datetime import datetime

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
        # Skapa formatter
        formatter = logging.Formatter(
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