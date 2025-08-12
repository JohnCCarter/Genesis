"""
Symbol Service - laddar och filtrerar symboler (inkl. TEST-symboler) från cache.
"""

from __future__ import annotations

import json
import os
from typing import List

from utils.logger import get_logger

logger = get_logger(__name__)


class SymbolService:
    def __init__(self) -> None:
        base_dir = os.path.dirname(os.path.dirname(__file__))  # tradingbot-backend/
        self.file_path = os.path.join(base_dir, "docs", "legacy", "bitfinex_docs", "extracted", "symbols.json")
        self._cache: List[str] = []

    def _load(self) -> List[str]:
        if self._cache:
            return self._cache
        symbols: List[str] = []
        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = json.load(f)
            # Hantera både [[...]] och [...]
            if isinstance(data, list) and len(data) == 1 and isinstance(data[0], list):
                symbols = [str(s) for s in data[0]]
            elif isinstance(data, list):
                symbols = [str(s) for s in data]
            else:
                logger.warning("Oväntat symbolformat i filen, fallback till default")
        except Exception as e:
            logger.warning(f"Kunde inte läsa symbols-fil: {e}. Använder fallback.")
        if not symbols:
            symbols = [
                "TESTBTC:TESTUSD",
                "TESTETH:TESTUSD",
                "TESTLTC:TESTUSD",
                "TESTSOL:TESTUSD",
                "TESTADA:TESTUSD",
                "BTCUSD",
                "ETHUSD",
            ]
        self._cache = symbols
        return self._cache

    def get_symbols(self, test_only: bool = False, fmt: str = "v2") -> List[str]:
        symbols = self._load()
        if test_only:
            symbols = [s for s in symbols if "TEST" in s]
        if fmt.lower() in ("v2", "bitfinex_v2", "t"):
            return [f"t{s}" for s in symbols]
        return symbols
