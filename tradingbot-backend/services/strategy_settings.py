"""
Strategy Settings Service - Hanterar indikatorparametrar och vikter för strategier.

Persistens sker i `config/strategy_settings.json` för enkel justering via API.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StrategySettings:
    # Vikter ska summera till 1.0 (valideras), men vi tillåter flexibilitet och normaliserar vid behov
    ema_weight: float = 0.4
    rsi_weight: float = 0.4
    atr_weight: float = 0.2

    # Indikatorparametrar (enkla standardvärden)
    ema_period: int = 14
    rsi_period: int = 14
    atr_period: int = 14

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict) -> "StrategySettings":
        return StrategySettings(
            ema_weight=float(data.get("ema_weight", 0.4)),
            rsi_weight=float(data.get("rsi_weight", 0.4)),
            atr_weight=float(data.get("atr_weight", 0.2)),
            ema_period=int(data.get("ema_period", 14)),
            rsi_period=int(data.get("rsi_period", 14)),
            atr_period=int(data.get("atr_period", 14)),
        )

    def normalized(self) -> "StrategySettings":
        total = max(self.ema_weight + self.rsi_weight + self.atr_weight, 1e-9)
        return StrategySettings(
            ema_weight=self.ema_weight / total,
            rsi_weight=self.rsi_weight / total,
            atr_weight=self.atr_weight / total,
            ema_period=self.ema_period,
            rsi_period=self.rsi_period,
            atr_period=self.atr_period,
        )


class StrategySettingsService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        # Bygg absolut sökväg till config-katalogen relativt projektroten
        base_dir = os.path.dirname(os.path.dirname(__file__))
        cfg_dir = os.path.join(base_dir, "config")
        os.makedirs(cfg_dir, exist_ok=True)
        self.file_path = os.path.join(cfg_dir, "strategy_settings.json")
        self.overrides_path = os.path.join(cfg_dir, "strategy_settings.overrides.json")

    def _load_overrides(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self.overrides_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {}
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.warning(f"Kunde inte läsa overrides för strategiinställningar: {e}")
            return {}

    def _save_overrides(self, overrides: Dict[str, Dict[str, Any]]) -> None:
        try:
            os.makedirs(os.path.dirname(self.overrides_path), exist_ok=True)
            with open(self.overrides_path, "w", encoding="utf-8") as f:
                json.dump(overrides, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Kunde inte spara overrides för strategiinställningar: {e}")
            raise

    def get_settings(self, symbol: Optional[str] = None) -> StrategySettings:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                base = StrategySettings.from_dict(data)
        except FileNotFoundError:
            logger.info("Inga strategiinställningar hittades – använder default och skapar fil.")
            base = StrategySettings()
            self.save_settings(base)
        except FileNotFoundError:
            # Redundant branch retained for clarity
            base = StrategySettings()
        except Exception as e:
            logger.warning(f"Kunde inte läsa strategiinställningar: {e}")
            base = StrategySettings()

        # Applicera per-symbol override om angiven symbol
        if symbol:
            try:
                overrides = self._load_overrides()
                ov = overrides.get(symbol)
                if isinstance(ov, dict):
                    merged = base.to_dict()
                    for k, v in ov.items():
                        if v is not None and k in merged:
                            merged[k] = v
                    return StrategySettings.from_dict(merged).normalized()
            except Exception as e:
                logger.warning(f"Kunde inte applicera symboloverride för {symbol}: {e}")
        return base.normalized()

    def save_settings(self, settings_obj: StrategySettings, symbol: Optional[str] = None) -> StrategySettings:
        try:
            normalized = settings_obj.normalized()
            if symbol:
                # Spara som per-symbol override
                overrides = self._load_overrides()
                overrides[symbol] = normalized.to_dict()
                self._save_overrides(overrides)
            else:
                # Spara som global default
                os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(normalized.to_dict(), f, ensure_ascii=False, indent=2)
            return normalized
        except Exception as e:
            logger.error(f"Kunde inte spara strategiinställningar: {e}")
            raise


