from services.bracket_manager import bracket_manager


def test_register_group_sets_ids():
    gid = "br_test"
    entry, sl, tp = 1, 2, 3
    bracket_manager.register_group(gid, entry, sl, tp)
    grp = bracket_manager.groups.get(gid)
    assert grp is not None
    assert grp.entry_id == entry and grp.sl_id == sl and grp.tp_id == tp
