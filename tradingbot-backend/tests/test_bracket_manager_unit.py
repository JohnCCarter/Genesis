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


@pytest.mark.asyncio
async def test_bracket_entry_partial_adjusts_protectives(monkeypatch):
    # Patcha ActiveOrdersService.get_order_by_id och update_order
    from services import bracket_manager as bm_mod
    from services.bracket_manager import BracketManager

    class DummyOrder:
        def __init__(self, id, amount):
            self.id = id
            self.amount = amount

    # Simulera skyddsordrar med initial size 0.5 och -0.5
    orders = {
        201: DummyOrder(201, -0.5),  # SL
        202: DummyOrder(202, 0.5),  # TP
    }

    async def fake_get_order_by_id(order_id: int):
        return orders.get(order_id)

    async def fake_update_order(order_id: int, price=None, amount=None):
        if order_id in orders and amount is not None:
            orders[order_id].amount = float(amount)
        return {"ok": True, "id": order_id, "amount": amount}

    # Patcha ActiveOrdersService metoder via modulnamn
    import rest.active_orders as ao
    import services.bracket_manager as mod

    class FakeAOSvc:
        async def get_order_by_id(self, order_id: int):
            return await fake_get_order_by_id(order_id)

        async def update_order(self, order_id: int, price=None, amount=None):
            return await fake_update_order(order_id, price=price, amount=amount)

    monkeypatch.setattr(ao, "ActiveOrdersService", lambda: FakeAOSvc())

    mgr = BracketManager()
    entry_id = 200
    sl_id = 201
    tp_id = 202
    mgr.register_group("g2", entry_id=entry_id, sl_id=sl_id, tp_id=tp_id)

    # Simulera två partial fills på entry: 0.2 och 0.3 => total 0.5
    msg1 = [0, "te", [999990, "tBTCUSD", 1700000000000, entry_id, 0.2, 50000]]
    await mgr.handle_private_event("te", msg1)
    msg2 = [0, "tu", [999991, "tBTCUSD", 1700000001000, entry_id, 0.3, 50050]]
    await mgr.handle_private_event("tu", msg2)

    # Båda skyddsordrar ska nu ha absolut storlek 0.5 (med tecken bibehållet)
    assert abs(orders[sl_id].amount) == 0.5
    assert abs(orders[tp_id].amount) == 0.5
    # Gruppen fortfarande aktiv
    assert mgr.groups["g2"].active is True


def test_bracket_state_persist_and_load(tmp_path, monkeypatch):
    # Patcha settings så state skrivs till tmp
    from services import bracket_manager as bm_mod

    tmp_state = tmp_path / "bracket_state.json"

    class DummySettings:
        BRACKET_STATE_FILE = str(tmp_state)

    monkeypatch.setattr(bm_mod, "Settings", lambda: DummySettings())

    # Skapa manager och registrera
    from services.bracket_manager import BracketManager as _BM

    mgr = _BM()
    mgr.register_group("gX", entry_id=1, sl_id=2, tp_id=3)

    # Skapa ny instans som ska ladda från fil
    mgr2 = _BM()
    assert "gX" in mgr2.groups
    # Child index återskapas
    assert 2 in mgr2.child_to_group and 3 in mgr2.child_to_group
