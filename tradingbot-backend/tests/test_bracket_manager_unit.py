import asyncio

import pytest


@pytest.mark.asyncio
async def test_bracket_manager_cancels_sibling_on_fill(monkeypatch):
    # Importera efter monkeypatch-setup
    from services import bracket_manager as bm_mod
    from services.bracket_manager import BracketManager

    cancelled = []

    async def fake_cancel_order(order_id: int):
        cancelled.append(order_id)
        return {"ok": True}

    # Patcha cancel_order som används inne i BracketManager
    monkeypatch.setattr(bm_mod, "cancel_order", fake_cancel_order)

    mgr = BracketManager()
    # Registrera en bracket med SL och TP
    sl_id = 111
    tp_id = 222
    mgr.register_group("g1", entry_id=123, sl_id=sl_id, tp_id=tp_id)

    # Simulera privat 'te' event för SL-order (exec_amount != 0 => fill)
    msg = [0, "te", [999999, "tBTCUSD", 1700000000000, sl_id, 0.1, 50000]]
    await mgr.handle_private_event("te", msg)

    # Syskon (TP) ska cancelleras och gruppen bli inaktiv
    assert tp_id in cancelled
    assert mgr.groups["g1"].active is False
