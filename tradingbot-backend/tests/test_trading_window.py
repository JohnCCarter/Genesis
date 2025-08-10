import json
import os
import tempfile

from config.settings import Settings
from services.trading_window import WEEKDAY_KEYS, TradingWindowService


def test_save_and_reload_rules(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        cfg_path = os.path.join(td, "rules.json")
        # Styr Settings att använda en absolut filväg
        monkeypatch.setenv("TRADING_RULES_FILE", cfg_path)

        s = Settings()
        svc = TradingWindowService(s)

        # Spara specifika regler
        windows = {k: [] for k in WEEKDAY_KEYS}
        windows["mon"] = [("08:00", "12:00")]
        svc.save_rules(
            timezone="Europe/Stockholm",
            windows=windows,
            paused=True,
            max_trades_per_day=7,
            trade_cooldown_seconds=5,
            max_trades_per_symbol_per_day=2,
        )

        # Verifiera att filen innehåller rätt nycklar
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["timezone"] == "Europe/Stockholm"
        assert data["paused"] is True
        assert data["max_trades_per_day"] == 7
        assert data["trade_cooldown_seconds"] == 5
        assert data["max_trades_per_symbol_per_day"] == 2
        assert data["windows"]["mon"] == [["08:00", "12:00"]]

        # Ladda om och verifiera i minnet
        svc = TradingWindowService(s)
        svc.reload()
        assert svc.rules.timezone == "Europe/Stockholm"
        assert svc.rules.paused is True
        assert svc.rules.max_trades_per_day == 7
        assert svc.rules.trade_cooldown_seconds == 5
        assert svc.rules.max_trades_per_symbol_per_day == 2
        # Windows återläses som List[List[str]]; acceptera båda representationer
        mon = svc.rules.windows["mon"]
        if isinstance(mon[0], tuple):
            assert list(mon) == [("08:00", "12:00")]
        else:
            assert mon == [["08:00", "12:00"]]
