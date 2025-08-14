"""
Bracket Manager - enkel server-sides OCO-hantering.

Lagrar bracket-grupper i minnet och reagerar på privata WS-event (te/tu/oc)
för att auto-avbryta kvarvarande barnorder när en av SL/TP fylls.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from config.settings import Settings
from rest.auth import cancel_order
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BracketGroup:
    entry_id: int | None
    sl_id: int | None
    tp_id: int | None
    active: bool = True
    # Ackumulerad fylld mängd på entry (absolutvärde)
    entry_filled: float = 0.0


class BracketManager:
    def __init__(self) -> None:
        # Mappar: child_order_id -> (gid, role)
        self.child_to_group: dict[int, tuple[str, str]] = {}
        # Mappar: gid -> BracketGroup
        self.groups: dict[str, BracketGroup] = {}
        self.settings = Settings()
        self._state_path = self._abs_state_path()
        # Ladda tidigare state om det finns
        try:
            self._load_state()
        except Exception as e:
            logger.warning(f"Kunde inte ladda bracket-state: {e}")

    def register_group(
        self,
        gid: str,
        entry_id: int | None,
        sl_id: int | None,
        tp_id: int | None,
    ) -> None:
        self.groups[gid] = BracketGroup(entry_id=entry_id, sl_id=sl_id, tp_id=tp_id, active=True)
        for role, oid in (("entry", entry_id), ("sl", sl_id), ("tp", tp_id)):
            if isinstance(oid, int):
                self.child_to_group[oid] = (gid, role)
        logger.info(f"Registered bracket gid={gid} entry={entry_id} sl={sl_id} tp={tp_id}")
        self._save_state_safe()

    async def _cancel_sibling(self, filled_child_id: int) -> None:
        group = self.child_to_group.get(filled_child_id)
        if not group:
            return
        gid, role = group
        data = self.groups.get(gid)
        if not data or not data.active:
            return
        # Bestäm syskon
        sibling_role = "tp" if role == "sl" else "sl"
        sibling_id = data.tp_id if sibling_role == "tp" else data.sl_id
        if isinstance(sibling_id, int):
            try:
                logger.info(
                    f"Bracket gid={gid}: cancel {sibling_role} order {sibling_id} efter fill av {role} {filled_child_id}"
                )
                await cancel_order(sibling_id)
            except Exception as e:
                logger.warning(f"Kunde inte cancel syskon-order {sibling_id}: {e}")
        data.active = False
        self._save_state_safe()

    async def handle_private_event(self, event_code: str, msg) -> None:
        """Hantera Bitfinex privata event (te/tu/oc/ou)."""
        try:
            # Vi lyssnar främst på te/tu (trade executed/update)
            if event_code in ("te", "tu"):
                payload: Any = msg[2] if isinstance(msg, list) and len(msg) > 2 else None
                if isinstance(payload, list) and len(payload) >= 6:
                    # Bitfinex format: [ID, PAIR, MTS, ORDER_ID, EXEC_AMOUNT, EXEC_PRICE, ...]
                    order_id = payload[3]
                    exec_amount = float(payload[4] or 0)
                    exec_price = float(payload[5] or 0)
                    if isinstance(order_id, int) and exec_amount != 0:
                        gid_role = self.child_to_group.get(order_id)
                        if gid_role:
                            gid, role = gid_role
                            if role == "entry":
                                try:
                                    # Ackumulera fylld mängd (absolut)
                                    g = self.groups.get(gid)
                                    if g and g.active:
                                        g.entry_filled = float(
                                            max(0.0, (g.entry_filled or 0.0))
                                        ) + abs(exec_amount)
                                        # Justera skyddsordrar (SL/TP) till ny fylld mängd
                                        await self._sync_protectives_to_entry_filled(gid)
                                        self._save_state_safe()
                                except Exception:
                                    pass
                            else:
                                # SL/TP fylld → OCO: avbryt syskon
                                # Om partial-justering är aktiverad för SL/TP kan vi minska syskon innan cancel,
                                # men OCO-semantiken: cancella syskon vid första fill.
                                if self.settings.BRACKET_PARTIAL_ADJUST:
                                    try:
                                        await self._adjust_sibling_on_partial(
                                            gid, role, exec_amount
                                        )
                                    except Exception:
                                        pass
                                await self._cancel_sibling(order_id)
            # På explicit cancel (oc) kan vi markera grupp som inaktiv
            elif event_code == "oc":
                payload = msg[2] if isinstance(msg, list) and len(msg) > 2 else None
                if isinstance(payload, list) and len(payload) > 0:
                    order_id = payload[0]
                    group = self.child_to_group.get(order_id)
                    if group:
                        gid, role = group
                        g = self.groups.get(gid)
                        if not g:
                            return
                        if role == "entry":
                            # Entry cancelled: om inget fyllt → städa bort skyddsordrar; annars låt gruppen leva
                            if (g.entry_filled or 0.0) <= 0.0:
                                # Cancella skyddsordrar om de finns
                                for oid in (g.sl_id, g.tp_id):
                                    if isinstance(oid, int):
                                        try:
                                            await cancel_order(oid)
                                        except Exception:
                                            pass
                                g.active = False
                            else:
                                # Markera att entry saknas men grupp lever vidare (skydd kan kvarstå)
                                g.entry_id = None
                            # Spara status (protectives ev. kvar)
                            self._save_state_safe()
                        else:
                            # Cancel på skyddsorder → inaktivera grupp
                            g.active = False
                            self._save_state_safe()
        except Exception as e:
            logger.error(f"Fel i BracketManager.handle_private_event: {e}")

    async def _adjust_sibling_on_partial(
        self, gid: str, filled_role: str, exec_amount: float
    ) -> None:
        """Justera syskonorder vid partial fill om aktiverat.

        Enkel heuristik: minska syskonets amount med samma belopp som fylld del.
        Kräver att uppdatering av order stöds (via REST update endpoint)."""
        try:
            data = self.groups.get(gid)
            if not data or not data.active:
                return
            sibling_role = "tp" if filled_role == "sl" else "sl"
            sibling_id = data.tp_id if sibling_role == "tp" else data.sl_id
            if not isinstance(sibling_id, int):
                return
            # Hämta aktuell order för att kunna räkna ny mängd
            from rest.active_orders import ActiveOrdersService

            svc = ActiveOrdersService()
            order = await svc.get_order_by_id(sibling_id)
            if not order:
                return
            current_amount = float(order.amount)
            # Minska absolutbeloppet med exec_amount, behåll tecken (sell/buy)
            new_amount_abs = max(abs(current_amount) - abs(exec_amount), 0.0)
            new_amount = new_amount_abs if current_amount > 0 else -new_amount_abs
            if new_amount_abs <= 0:
                # Om noll, cancella syskon i stället
                await cancel_order(sibling_id)
                data.active = False
                self._save_state_safe()
                return
            # Uppdatera ordern
            await svc.update_order(sibling_id, amount=new_amount)
        except Exception as e:
            logger.warning(f"Partial adjust misslyckades: {e}")

    async def _sync_protectives_to_entry_filled(self, gid: str) -> None:
        """Synka SL/TP amount till ackumulerad entry_filled.

        Hämtar nuvarande SL/TP-order, beräknar ny mängd med samma tecken men
        absolutvärde = entry_filled.
        """
        data = self.groups.get(gid)
        if not data or not data.active:
            return
        desired_abs = float(max(0.0, data.entry_filled or 0.0))
        if desired_abs <= 0.0:
            return
        from rest.active_orders import ActiveOrdersService

        svc = ActiveOrdersService()
        for oid in (data.sl_id, data.tp_id):
            if not isinstance(oid, int):
                continue
            try:
                order = await svc.get_order_by_id(oid)
                if not order:
                    continue
                current_amount = float(order.amount)
                new_amount_abs = desired_abs
                new_amount = new_amount_abs if current_amount > 0 else -new_amount_abs
                # Undvik onödiga uppdateringar vid redan rätt storlek
                if abs(float(current_amount)) != new_amount_abs:
                    await svc.update_order(oid, amount=new_amount)
            except Exception as e:
                logger.warning(f"Sync protectives misslyckades för {oid}: {e}")

    def _abs_state_path(self) -> str:
        path = self.settings.BRACKET_STATE_FILE
        if os.path.isabs(path):
            return path
        base_dir = os.path.dirname(os.path.dirname(__file__))
        cfg_dir = os.path.join(base_dir, "config")
        return os.path.join(cfg_dir, os.path.basename(path))

    def _load_state(self) -> None:
        raw = _safe_read_json(self._state_path)
        if not raw:
            return
        if not _is_valid_state(raw):
            logger.warning("Ogiltig bracket-state, ignorerar")
            return
        groups = _deserialize_groups(raw.get("groups", {}))
        # Filtrera bort inaktiva grupper direkt
        groups = {gid: g for gid, g in groups.items() if g.active}
        self.groups = groups
        self.child_to_group = _child_index(groups)
        logger.info(f"Laddade {len(self.groups)} bracket-grupper från state")

    def _save_state_safe(self) -> None:
        payload = {"groups": _serialize_groups(self.groups)}
        _safe_write_json(self._state_path, payload)

    def reset(self, delete_file: bool = True) -> int:
        """Töm alla grupper och nollställ state.

        Args:
            delete_file: Om True, försök ta bort state-filen från disk.

        Returns:
            Antal grupper som rensades.
        """
        cleared = len(self.groups)
        self.groups.clear()
        self.child_to_group.clear()
        if delete_file:
            try:
                if os.path.exists(self._state_path):
                    os.remove(self._state_path)
            except Exception as e:
                logger.warning(f"Kunde inte ta bort bracket-state-fil: {e}")
        else:
            self._save_state_safe()
        return cleared


# --- Persistenshelpers ---
def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def _coerce_int(v):
    try:
        return int(v)
    except Exception:
        return None


def _serialize_groups(groups: dict[str, BracketGroup]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for gid, g in groups.items():
        out[gid] = {
            "entry_id": _coerce_int(g.entry_id),
            "sl_id": _coerce_int(g.sl_id),
            "tp_id": _coerce_int(g.tp_id),
            "active": bool(g.active),
        }
    return out


def _deserialize_groups(raw: dict[str, dict]) -> dict[str, BracketGroup]:
    out: dict[str, BracketGroup] = {}
    for gid, v in raw.items():
        out[gid] = BracketGroup(
            entry_id=_coerce_int(v.get("entry_id")),
            sl_id=_coerce_int(v.get("sl_id")),
            tp_id=_coerce_int(v.get("tp_id")),
            active=bool(v.get("active", True)),
        )
    return out


def _child_index(groups: dict[str, BracketGroup]) -> dict[int, tuple[str, str]]:
    idx: dict[int, tuple[str, str]] = {}
    for gid, g in groups.items():
        if isinstance(g.sl_id, int):
            idx[g.sl_id] = (gid, "sl")
        if isinstance(g.tp_id, int):
            idx[g.tp_id] = (gid, "tp")
    return idx


def _is_valid_state(data: dict) -> bool:
    return isinstance(data, dict) and "groups" in data and isinstance(data.get("groups"), dict)


def _safe_read_json(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _safe_write_json(path: str, payload: dict) -> None:
    try:
        _ensure_dir(path)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        logger.warning(f"Kunde inte skriva bracket-state: {e}")


# Global instans
bracket_manager = BracketManager()
