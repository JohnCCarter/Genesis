"""
Trading Window Service - styr när boten får vara aktiv baserat på tid på dygnet/veckan.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any
from datetime import datetime, time, timedelta

from config.settings import Settings
from utils.logger import get_logger

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

logger = get_logger(__name__)

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _parse_time(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(hour=int(h), minute=int(m))


@dataclass
class TradingRules:
    timezone: str
    windows: dict[str, list[tuple[str, str]]]
    max_trades_per_day: int
    trade_cooldown_seconds: int
    paused: bool
    # Valfri per-symbol daglig gräns (0 eller saknas = inaktiverad)
    max_trades_per_symbol_per_day: int = 0


class TradingWindowService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.rules = self._load_rules()

    def _load_rules(self) -> TradingRules:
        try:
            # Säkerställ att config-katalogen finns innan läsning/skrivning
            cfg_path = self._abs_rules_path()
            with open(cfg_path, encoding="utf-8") as f:
                data = json.load(f)
            return TradingRules(
                timezone=data.get("timezone", self.settings.TIMEZONE),
                windows=data.get("windows", {}),
                max_trades_per_day=int(data.get("max_trades_per_day", self.settings.MAX_TRADES_PER_DAY)),
                trade_cooldown_seconds=int(data.get("trade_cooldown_seconds", self.settings.TRADE_COOLDOWN_SECONDS)),
                paused=bool(data.get("paused", self.settings.TRADING_PAUSED)),
                max_trades_per_symbol_per_day=int(
                    data.get(
                        "max_trades_per_symbol_per_day",
                        getattr(self.settings, "MAX_TRADES_PER_SYMBOL_PER_DAY", 0),
                    )
                ),
            )
        except FileNotFoundError:
            logger.warning("TRADING_RULES_FILE saknas – använder default från Settings")
        except Exception as e:
            # Korrupt JSON eller annan I/O – självläka med default och skriv om filen
            logger.warning(
                "Kunde inte läsa trading rules (%s) – initierar default och skriver om filen",
                e,
            )
        # Default-regler och skriv till fil
        default_rules = TradingRules(
            timezone=self.settings.TIMEZONE,
            windows={w: [] for w in WEEKDAY_KEYS},
            max_trades_per_day=self.settings.MAX_TRADES_PER_DAY,
            trade_cooldown_seconds=self.settings.TRADE_COOLDOWN_SECONDS,
            paused=self.settings.TRADING_PAUSED,
            max_trades_per_symbol_per_day=getattr(self.settings, "MAX_TRADES_PER_SYMBOL_PER_DAY", 0),
        )
        try:
            cfg_path = self._abs_rules_path()
            os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
            payload = {
                "timezone": default_rules.timezone,
                "windows": default_rules.windows,
                "max_trades_per_day": default_rules.max_trades_per_day,
                "trade_cooldown_seconds": default_rules.trade_cooldown_seconds,
                "paused": default_rules.paused,
                "max_trades_per_symbol_per_day": getattr(default_rules, "max_trades_per_symbol_per_day", 0),
            }
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            # Ignorera skrivfel – återvänd default i minne
            pass
        return default_rules

    def is_open(self, now: datetime | None = None) -> bool:
        if self.rules.paused:
            return False

        tz = ZoneInfo(self.rules.timezone) if ZoneInfo else None
        now = now or datetime.now(tz) if tz else datetime.utcnow()

        weekday = WEEKDAY_KEYS[now.weekday()]
        windows = self.rules.windows.get(weekday, [])
        if not windows:
            return False

        # Använd en naive time-of-day för jämförelse mot reglernas tider (som är naive)
        current_t = now.time()
        for start, end in windows:
            t_start, t_end = _parse_time(start), _parse_time(end)
            if t_start <= current_t <= t_end:
                return True
        return False

    def next_open(self, now: datetime | None = None) -> datetime | None:
        tz = ZoneInfo(self.rules.timezone) if ZoneInfo else None
        now = now or datetime.now(tz) if tz else datetime.utcnow()

        # Sök i dag och framåt sju dagar
        for delta in range(0, 8):
            candidate_day = now + timedelta(days=delta)
            weekday = WEEKDAY_KEYS[candidate_day.weekday()]
            windows = self.rules.windows.get(weekday, [])
            for start, _ in windows:
                t_start = _parse_time(start)
                candidate_dt = candidate_day.replace(hour=t_start.hour, minute=t_start.minute, second=0, microsecond=0)
                if candidate_dt >= now:
                    return candidate_dt
        return None

    def get_limits(self) -> dict[str, int]:
        return {
            "max_trades_per_day": self.rules.max_trades_per_day,
            "trade_cooldown_seconds": self.rules.trade_cooldown_seconds,
            "max_trades_per_symbol_per_day": getattr(self.rules, "max_trades_per_symbol_per_day", 0),
        }

    def is_paused(self) -> bool:
        return self.rules.paused

    def set_paused(self, paused: bool) -> None:
        """Sätt paused status."""
        self.save_rules(paused=paused)

    def set_windows(self, windows: dict[str, list[tuple[str, str]]]) -> None:
        """Sätt trading windows."""
        self.save_rules(windows=windows)

    def set_timezone(self, timezone: str) -> None:
        """Sätt timezone."""
        self.save_rules(timezone=timezone)

    def get_status(self) -> dict[str, Any]:
        """Hämta komplett status."""
        _next = self.next_open()
        return {
            "paused": self.rules.paused,
            "open": self.is_open(),
            "next_open": _next.isoformat() if _next is not None else None,
            "windows": self.rules.windows,
            "timezone": self.rules.timezone,
            "limits": self.get_limits(),
        }

    # --- Dynamiska uppdateringar/persistens ---
    def save_rules(
        self,
        *,
        timezone: str | None = None,
        windows: dict[str, list[tuple[str, str]]] | None = None,
        paused: bool | None = None,
        max_trades_per_symbol_per_day: int | None = None,
        max_trades_per_day: int | None = None,
        trade_cooldown_seconds: int | None = None,
    ) -> None:
        """Uppdaterar regler i minnet och persisterar till fil."""
        # Uppdatera in-memory
        if timezone is not None:
            if not self._is_valid_timezone(timezone):
                raise ValueError(f"Ogiltig tidszon: {timezone}")
            self.rules.timezone = timezone
        if windows is not None:
            self.validate_windows(windows)
            self.rules.windows = windows
        if paused is not None:
            self.rules.paused = paused
        if max_trades_per_symbol_per_day is not None and max_trades_per_symbol_per_day >= 0:
            self.rules.max_trades_per_symbol_per_day = int(max_trades_per_symbol_per_day)
        if max_trades_per_day is not None and max_trades_per_day > 0:
            self.rules.max_trades_per_day = int(max_trades_per_day)
        if trade_cooldown_seconds is not None and trade_cooldown_seconds >= 0:
            self.rules.trade_cooldown_seconds = int(trade_cooldown_seconds)

        # Skriv till fil
        payload = {
            "timezone": self.rules.timezone,
            "windows": self.rules.windows,
            "max_trades_per_day": self.rules.max_trades_per_day,
            "trade_cooldown_seconds": self.rules.trade_cooldown_seconds,
            "paused": self.rules.paused,
            "max_trades_per_symbol_per_day": getattr(self.rules, "max_trades_per_symbol_per_day", 0),
        }
        cfg_path = self._abs_rules_path()
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _abs_rules_path(self) -> str:
        """Returnerar absolut sökväg till trading_rules.json i projektets config-katalog."""
        # Om en absolut väg redan angivits i settings, respektera den
        path = self.settings.TRADING_RULES_FILE
        if os.path.isabs(path):
            return path
        base_dir = os.path.dirname(os.path.dirname(__file__))
        cfg_dir = os.path.join(base_dir, "config")
        return os.path.join(cfg_dir, os.path.basename(path))

    def reload(self) -> None:
        self.rules = self._load_rules()

    # removed duplicate set_paused (defined earlier)

    # --- Validering ---
    @staticmethod
    def _is_valid_time_string(s: str) -> bool:
        if not isinstance(s, str):
            return False
        if not re.match(r"^\d{2}:\d{2}$", s):
            return False
        try:
            h, m = s.split(":")
            h_i, m_i = int(h), int(m)
            return 0 <= h_i <= 23 and 0 <= m_i <= 59
        except Exception:
            return False

    def _is_valid_timezone(self, tz: str) -> bool:
        if ZoneInfo is None:
            # Om zoneinfo saknas, acceptera str och låt OS-zeit hindras senare
            return isinstance(tz, str) and len(tz) > 0
        try:
            ZoneInfo(tz)
            return True
        except Exception:
            return False

    def validate_windows(self, windows: dict[str, list[tuple[str, str]]]) -> None:
        # Nycklar måste vara veckodagar
        for key in windows.keys():
            if key not in WEEKDAY_KEYS:
                raise ValueError(f"Ogiltig veckodag: {key}")
        # Varje värde: lista av (start, slut) med giltiga tider och start < slut
        for day, ranges in windows.items():
            if not isinstance(ranges, list):
                raise ValueError(f"Tidsintervall för {day} måste vara en lista")
            for pair in ranges:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError(f"Fel format för intervall i {day}: {pair}")
                start, end = pair[0], pair[1]
                if not (self._is_valid_time_string(start) and self._is_valid_time_string(end)):
                    raise ValueError(f"Ogiltigt tidsformat i {day}: {start}-{end}")
                t_start, t_end = _parse_time(start), _parse_time(end)
                if not (t_start < t_end):
                    raise ValueError(f"Start måste vara före slut i {day}: {start}-{end}")
