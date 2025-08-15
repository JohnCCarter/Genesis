"""
Symbol Service - central resolver och listningskontroll för symboler.

Ansvar:
- Hämta och cacha Bitfinex parlistor (exchange + margin) via REST Configs
- Hämta och cacha currency-alias (pub:map:currency:sym), ex. ALGO->ALG
- Mappa TEST-symboler till giltiga Bitfinex v2-symboler (tPAIR)
- Verifiera om ett effektivt par är listat
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


# Delad cache över alla instanser för att undvika upprepade REST‑anrop vid startup
_CACHE: dict = {
    "pairs": [],
    "alias_fwd": {},
    "alias_rev": {},
    "ts": 0.0,
    "ttl": 3600.0,
}
_REFRESH_LOCK: asyncio.Lock = asyncio.Lock()


class SymbolService:
    def __init__(self) -> None:
        # Legacy fil-stöd (fallback)
        base_dir = os.path.dirname(os.path.dirname(__file__))  # tradingbot-backend/
        self.file_path = os.path.join(
            base_dir, "docs", "legacy", "bitfinex_docs", "extracted", "symbols.json"
        )
        self._legacy_cache: list[str] = []
        # Delad cache används; behåll instansfält för bakåtkompatibilitet
        self._pairs: list[str] = _CACHE["pairs"]
        self._alias_fwd: dict[str, str] = _CACHE["alias_fwd"]
        self._alias_rev: dict[str, str] = _CACHE["alias_rev"]
        self._last_refresh_ts: float = _CACHE["ts"]
        self._ttl_seconds: float = _CACHE["ttl"]

    def _load_legacy(self) -> list[str]:
        if self._legacy_cache:
            return self._legacy_cache
        symbols: list[str] = []
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

    def get_symbols(self, test_only: bool = False, fmt: str = "v2") -> list[str]:
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
            # Läs delad cache först
            if (now - float(_CACHE["ts"] or 0)) <= float(_CACHE["ttl"]):
                # Synka instanspekare
                self._pairs = _CACHE["pairs"]
                self._alias_fwd = _CACHE["alias_fwd"]
                self._alias_rev = _CACHE["alias_rev"]
                self._last_refresh_ts = _CACHE["ts"]
                return

            async with _REFRESH_LOCK:
                # Double‑check under lås
                now = _t.time()
                if (now - float(_CACHE["ts"] or 0)) <= float(_CACHE["ttl"]):
                    self._pairs = _CACHE["pairs"]
                    self._alias_fwd = _CACHE["alias_fwd"]
                    self._alias_rev = _CACHE["alias_rev"]
                    self._last_refresh_ts = _CACHE["ts"]
                    return
                # Hämta från BitfinexDataService
                from services.bitfinex_data import BitfinexDataService

                svc = BitfinexDataService()
                pairs = await svc.get_configs_symbols() or []
                fwd, rev = await svc.get_currency_symbol_map()
                if pairs:
                    _CACHE["pairs"] = list(pairs)
                _CACHE["alias_fwd"] = {k.upper(): v.upper() for k, v in fwd.items()}
                _CACHE["alias_rev"] = {k.upper(): v.upper() for k, v in rev.items()}
                _CACHE["ts"] = now
                # Synka instanspekare
                self._pairs = _CACHE["pairs"]
                self._alias_fwd = _CACHE["alias_fwd"]
                self._alias_rev = _CACHE["alias_rev"]
                self._last_refresh_ts = _CACHE["ts"]
                logger.info(
                    "SymbolService refresh: pairs=%s aliases=%s",
                    len(self._pairs),
                    len(self._alias_fwd),
                )
        except Exception as e:
            logger.warning("SymbolService refresh misslyckades: %s", e)

    def _split_symbol(self, t_symbol: str) -> tuple[str, str]:
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
