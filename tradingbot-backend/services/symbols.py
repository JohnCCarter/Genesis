"""
Symbol Service - central resolver och listningskontroll för symboler.

Ansvar:
- Hämta och cacha Bitfinex parlistor (exchange + margin) via REST Configs
- Hämta och cacha currency-alias (pub:map:currency:sym), ex. ALGO->ALG
- Mappa TEST-symboler till giltiga Bitfinex v2-symboler (tPAIR)
- Verifiera om ett effektivt par är listat
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


class SymbolService:
    def __init__(self) -> None:
        # Legacy fil-stöd (fallback)
        base_dir = os.path.dirname(os.path.dirname(__file__))  # tradingbot-backend/
        self.file_path = os.path.join(
            base_dir, "docs", "legacy", "bitfinex_docs", "extracted", "symbols.json"
        )
        self._legacy_cache: List[str] = []
        # Live config-cacher
        self._pairs: List[str] = []  # ex. ["BTCUSD","ETHUSD", ...]
        self._alias_fwd: Dict[str, str] = {}  # RAW -> API (ex. ALGO -> ALG)
        self._alias_rev: Dict[str, str] = {}  # API -> RAW
        self._last_refresh_ts: float = 0.0
        self._ttl_seconds: float = 3600.0

    def _load_legacy(self) -> List[str]:
        if self._legacy_cache:
            return self._legacy_cache
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
        self._legacy_cache = symbols
        return self._legacy_cache

    def get_symbols(self, test_only: bool = False, fmt: str = "v2") -> List[str]:
        # Legacy-läsning (endast för dokumentationssyfte i UI)
        symbols = self._load_legacy()
        if test_only:
            symbols = [s for s in symbols if "TEST" in s]
        if fmt.lower() in ("v2", "bitfinex_v2", "t"):
            return [f"t{s}" for s in symbols]
        return symbols

    async def refresh(self) -> None:
        """Hämta och cacha parlistor + alias om TTL löpt ut."""
        try:
            import time as _t

            now = _t.time()
            if (now - float(self._last_refresh_ts or 0)) <= self._ttl_seconds:
                return
            # Hämta från BitfinexDataService
            from services.bitfinex_data import BitfinexDataService

            svc = BitfinexDataService()
            pairs = await svc.get_configs_symbols() or []
            fwd, rev = await svc.get_currency_symbol_map()
            if pairs:
                self._pairs = list(pairs)
            self._alias_fwd = dict((k.upper(), v.upper()) for k, v in fwd.items())
            self._alias_rev = dict((k.upper(), v.upper()) for k, v in rev.items())
            self._last_refresh_ts = now
            logger.info(
                "SymbolService refresh: pairs=%s aliases=%s",
                len(self._pairs),
                len(self._alias_fwd),
            )
        except Exception as e:
            logger.warning("SymbolService refresh misslyckades: %s", e)

    def _split_symbol(self, t_symbol: str) -> Tuple[str, str]:
        """Ta 'tBTCUSD' eller 'tTESTADA:TESTUSD' → (BASE, QUOTE) utan prefix."""
        s = t_symbol
        if s.startswith("t"):
            s = s[1:]
        if ":" in s:
            base, quote = s.split(":", 1)
        else:
            base, quote = s[:-3], s[-3:]
        return base.upper(), quote.upper()

    def _apply_alias(self, base: str) -> str:
        """Currency alias (ALGO->ALG etc)."""
        return self._alias_fwd.get(base.upper(), base.upper())

    def listed(self, t_symbol: str) -> bool:
        """Är tPAIR listad i configs (exchange eller margin)?"""
        try:
            base, quote = self._split_symbol(t_symbol)
            base = self._apply_alias(base)
            pair = f"{base}{quote}"
            # Offline/CI-fallback: om vi saknar live-parlista, tillåt alla
            if not self._pairs:
                return True
            return pair in self._pairs
        except Exception:
            return False

    def resolve(self, t_symbol: str) -> str:
        """
        Mappa inkommande symbol (t.ex. 'tTESTBTC:TESTUSDT'/'tALGOUSD') till giltig Bitfinex-v2 'tPAIR'.
        Regler: TEST->live, alias (ALGO->ALG), USD->UST fallback.
        """
        try:
            s = (t_symbol or "").strip()
            if not s:
                return t_symbol
            # TEST-mappningar
            base, quote = self._split_symbol(s)
            # tTEST<ASSET>:TESTUSD -> <ASSET>USD
            if base.startswith("TEST") and quote == "TESTUSD":
                base = base[4:]
                quote = "USD"
            # tTEST<ASSET>:TESTUSDT -> <ASSET>UST
            if base.startswith("TEST") and quote == "TESTUSDT":
                base = base[4:]
                quote = "UST"
            # Alias
            base = self._apply_alias(base)
            # Kandidater i ordning
            candidates = [f"{base}{quote}"]
            if quote == "USD":
                candidates.append(f"{base}UST")
            # Välj första listade
            for cand in candidates:
                if not self._pairs or cand in self._pairs:
                    return f"t{cand}"
            # Fallback till ursprunglig utan ändring
            return f"t{base}{quote}"
        except Exception:
            return t_symbol
