def test_symbol_service_resolve_and_listed():
    from services.symbols import SymbolService

    svc = SymbolService()

    # TEST mapping to live
    assert svc.resolve("tTESTADA:TESTUSD").startswith("tADA")
    assert svc.resolve("tTESTBTC:TESTUSDT").startswith("tBTC")

    # Alias application optionally; tolerate fallback
    sym = svc.resolve("tALGOUSD")
    assert sym.startswith("tALG") or sym.startswith("tALGO")

    # listed returns True if pairs cache empty, else checks membership without crashing
    if not svc._pairs:
        assert svc.listed("tBTCUSD") is True
    else:
        _ = svc.listed("tBTCUSD")
