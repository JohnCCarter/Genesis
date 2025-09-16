"""
Order Templates Service - spara/hamta ordermallar (Market/Limit + SL/TP).
"""

from __future__ import annotations

import json
import os
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class OrderTemplatesService:
    def __init__(self, base_dir: str | None = None) -> None:
        base = base_dir or os.path.dirname(os.path.dirname(__file__))
        cfg_dir = os.path.join(base, "config")
        os.makedirs(cfg_dir, exist_ok=True)
        self.file_path = os.path.join(cfg_dir, "order_templates.json")

    def _load(self) -> dict[str, Any]:
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, encoding="utf-8") as f:
                    data = json.load(f)
                    # Om filen råkar vara en lista, wrappa den i {"templates": ...}
                    if isinstance(data, list):
                        return {"templates": data}
                    if isinstance(data, dict):
                        return data
                    return {"templates": []}
        except Exception as e:
            logger.warning(f"Kunde inte läsa templates: {e}")
        return {"templates": []}

    def _save(self, data: dict[str, Any]) -> dict[str, Any]:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    def list_templates(self) -> list[dict[str, Any]]:
        data = self._load()
        try:
            items = data.get("templates", []) if isinstance(data, dict) else []
            return items if isinstance(items, list) else []
        except Exception:
            return []

    def save_template(self, template: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        items = data.get("templates", [])
        # ersätt om name finns
        name = str(template.get("name", "")).strip()
        items = [t for t in items if str(t.get("name", "")).strip() != name]
        items.append(template)
        data["templates"] = items
        return self._save(data)

    def get_template(self, name: str) -> dict[str, Any] | None:
        """Hämta en mall per namn (case-insensitive, trimmat)."""
        try:
            name_norm = str(name or "").strip().lower()
            if not name_norm:
                return None
            for t in self.list_templates():
                tname = str(t.get("name", "")).strip().lower()
                if tname == name_norm:
                    return t
        except Exception:
            pass
        return None

    def delete_template(self, name: str) -> bool:
        """Ta bort en mall per namn. Returnerar True om något togs bort."""
        try:
            data = self._load()
            items = data.get("templates", [])
            name_norm = str(name or "").strip().lower()
            kept = [
                t for t in items if str(t.get("name", "")).strip().lower() != name_norm
            ]
            if len(kept) != len(items):
                data["templates"] = kept
                self._save(data)
                return True
        except Exception:
            pass
        return False
