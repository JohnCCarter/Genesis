"""
Order Templates Service - spara/hamta ordermallar (Market/Limit + SL/TP).
"""

from __future__ import annotations

import json
import os
from typing import Dict, Any, List
from utils.logger import get_logger

logger = get_logger(__name__)


class OrderTemplatesService:
    def __init__(self, base_dir: str | None = None) -> None:
        base = base_dir or os.path.dirname(os.path.dirname(__file__))
        cfg_dir = os.path.join(base, "config")
        os.makedirs(cfg_dir, exist_ok=True)
        self.file_path = os.path.join(cfg_dir, "order_templates.json")

    def _load(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Kunde inte läsa templates: {e}")
        return {"templates": []}

    def _save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    def list_templates(self) -> List[Dict[str, Any]]:
        data = self._load()
        return data.get("templates", [])

    def save_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        data = self._load()
        items = data.get("templates", [])
        # ersätt om name finns
        name = str(template.get("name", "")).strip()
        items = [t for t in items if str(t.get("name", "")).strip() != name]
        items.append(template)
        data["templates"] = items
        return self._save(data)


