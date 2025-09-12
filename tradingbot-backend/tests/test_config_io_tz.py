import json
import os
import tempfile

from fastapi.testclient import TestClient


def test_trading_rules_io_and_timezone_validation(monkeypatch):
    os.environ.setdefault("AUTH_REQUIRED", "False")
    # Temporär katalog och fil för trading rules
    tmpdir = tempfile.mkdtemp()
    rules_path = os.path.join(tmpdir, "trading_rules.json")

    # Peka Settings på vår temporära fil
    monkeypatch.setenv("TRADING_RULES_FILE", rules_path)

    from services.trading_window import TradingWindowService

    svc = TradingWindowService()
    # Default skrivs ut om fil saknas
    assert os.path.exists(rules_path)
    # Validera timezone
    assert isinstance(svc.rules.timezone, str)

    # Försök sätta ogiltig timezone -> ska kasta ValueError
    try:
        svc.save_rules(timezone="Not/AZone")
        assert False, "Expected ValueError for invalid timezone"
    except ValueError:
        pass

    # Sätt en giltig timezone och uppdatera windows
    svc.save_rules(timezone="UTC", windows={"mon": [("09:00", "17:00")]})
    # Läs om från fil och kontrollera persistens
    with open(rules_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["timezone"] == "UTC"
    assert data["windows"]["mon"] == [["09:00", "17:00"]]


def test_risk_guards_io(monkeypatch):
    os.environ.setdefault("AUTH_REQUIRED", "False")
    tmpdir = tempfile.mkdtemp()
    guards_path = os.path.join(tmpdir, "risk_guards.json")

    from services import risk_guards

    # Monkeypatcha guards filväg
    svc = risk_guards.RiskGuardsService()
    svc.guards_file = guards_path
    # Första spar init
    svc._save_guards(svc.guards)
    assert os.path.exists(guards_path)

    # Uppdatera config och spara
    ok = svc.update_guard_config("max_daily_loss", {"percentage": 7.5})
    assert ok is True

    # Läs om från fil och verifiera uppdatering
    loaded = svc._load_guards()
    assert loaded["max_daily_loss"]["percentage"] == 7.5
