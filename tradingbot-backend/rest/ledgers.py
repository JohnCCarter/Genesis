"""
Ledger Service - TradingBot Backend

Fristående modul för ledger-hämtning så att andra tjänster
(t.ex. HistoryService) kan bero på en enkel LedgerService utan att
dra in hela orderhistorik-implementationen.

Implementationen återanvänder OrderHistoryService för själva Bitfinex
REST-anropet och konverterar Pydantic-objekt till dict så att
förbrukare (som HistoryService) kan filtrera med .get(...).
"""

from __future__ import annotations

from typing import Any, List

from config.settings import settings, Settings
from rest.order_history import OrderHistoryService


class LedgerService:
    """Tunn wrapper för att hämta ledgers som dict-listor."""

    def __init__(self, settings_override: Settings | None = None) -> None:
        # Settings hålls för framtida bruk/konfiguration
        self.settings = settings_override or settings
        # Återanvänd befintlig orderhistorikservice för API-anropen
        self._order_history = OrderHistoryService()

    async def get_ledgers(self, currency: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
        """Hämta ledger-poster som dicts.

        Args:
            currency: Valuta att filtrera på via API (t.ex. "USD"). None för alla.
            limit: Max antal poster.

        Returns:
            Lista av dict med fält som minst innehåller:
            - id, currency, amount, balance, description, created_at, wallet_type
        """
        entries = await self._order_history.get_ledgers(currency=currency, limit=limit)

        # Konvertera Pydantic-objekt (eller andra objekt) till dict för downstream .get(...)
        out: list[dict[str, Any]] = []
        for e in entries:
            if hasattr(e, "dict"):
                out.append(e.dict())  # Pydantic v1-style
            elif hasattr(e, "model_dump"):
                out.append(e.model_dump())  # Pydantic v2 fallback
            elif isinstance(e, dict):
                out.append(e)
            else:
                # Sista utväg: bygg en enkel dict via attribut
                out.append(
                    {
                        k: getattr(e, k)
                        for k in (
                            "id",
                            "currency",
                            "amount",
                            "balance",
                            "description",
                            "created_at",
                            "wallet_type",
                        )
                        if hasattr(e, k)
                    }
                )
        return out
