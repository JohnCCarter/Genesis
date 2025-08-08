"""
Bracket Manager - enkel server-sides OCO-hantering.

Lagrar bracket-grupper i minnet och reagerar på privata WS-event (te/tu/oc)
för att auto-avbryta kvarvarande barnorder när en av SL/TP fylls.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
from utils.logger import get_logger

from rest.auth import cancel_order

logger = get_logger(__name__)


class BracketManager:
    def __init__(self) -> None:
        # Mappar: child_order_id -> (gid, role)
        self.child_to_group: Dict[int, Tuple[str, str]] = {}
        # Mappar: gid -> {"entry": id, "sl": id, "tp": id, "active": True}
        self.groups: Dict[str, Dict[str, Optional[int]]] = {}

    def register_group(self, gid: str, entry_id: Optional[int], sl_id: Optional[int], tp_id: Optional[int]) -> None:
        self.groups[gid] = {"entry": entry_id, "sl": sl_id, "tp": tp_id, "active": True}
        for role, oid in (("sl", sl_id), ("tp", tp_id)):
            if isinstance(oid, int):
                self.child_to_group[oid] = (gid, role)
        logger.info(f"Registered bracket gid={gid} entry={entry_id} sl={sl_id} tp={tp_id}")

    async def _cancel_sibling(self, filled_child_id: int) -> None:
        group = self.child_to_group.get(filled_child_id)
        if not group:
            return
        gid, role = group
        data = self.groups.get(gid)
        if not data or not data.get("active"):
            return
        # Bestäm syskon
        sibling_role = "tp" if role == "sl" else "sl"
        sibling_id = data.get(sibling_role)
        if isinstance(sibling_id, int):
            try:
                logger.info(f"Bracket gid={gid}: cancel {sibling_role} order {sibling_id} efter fill av {role} {filled_child_id}")
                await cancel_order(sibling_id)
            except Exception as e:
                logger.warning(f"Kunde inte cancel syskon-order {sibling_id}: {e}")
        data["active"] = False

    async def handle_private_event(self, event_code: str, msg) -> None:
        """Hantera Bitfinex privata event (te/tu/oc/ou)."""
        try:
            # Vi lyssnar främst på te/tu (trade executed/update)
            if event_code in ("te", "tu"):
                payload = msg[2] if isinstance(msg, list) and len(msg) > 2 else None
                if isinstance(payload, list) and len(payload) >= 5:
                    # Bitfinex format: [ID, PAIR, MTS, ORDER_ID, EXEC_AMOUNT, EXEC_PRICE, ...]
                    order_id = payload[3]
                    exec_amount = payload[4]
                    # När exec_amount != 0 betraktas ordern som fylld/partial; vi cancel syskon om barn-order
                    if isinstance(order_id, int) and abs(float(exec_amount)) > 0:
                        await self._cancel_sibling(order_id)
            # På explicit cancel (oc) kan vi markera grupp som inaktiv
            elif event_code == "oc":
                payload = msg[2] if isinstance(msg, list) and len(msg) > 2 else None
                if isinstance(payload, list) and len(payload) > 0:
                    order_id = payload[0]
                    group = self.child_to_group.get(order_id)
                    if group:
                        gid, _ = group
                        if gid in self.groups:
                            self.groups[gid]["active"] = False
        except Exception as e:
            logger.error(f"Fel i BracketManager.handle_private_event: {e}")


# Global instans
bracket_manager = BracketManager()


