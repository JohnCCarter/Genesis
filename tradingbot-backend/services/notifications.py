"""
Notifications Service - Telegram (optional) + Socket.IO helpers
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


class NotificationService:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._bot_token = self.settings.TELEGRAM_BOT_TOKEN
        self._chat_id = self.settings.TELEGRAM_CHAT_ID

    async def send_telegram(self, text: str) -> bool:
        if not self._bot_token or not self._chat_id:
            logger.debug("Telegram ej konfigurerat; hoppar över")
            return False
        try:
            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
            payload = {"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Telegram-notis misslyckades: {e}")
            return False

    async def notify(
        self, level: str, title: str, payload: Optional[Dict[str, Any]] = None
    ) -> None:
        # Socket.IO broadcast
        try:
            from ws.manager import socket_app

            await socket_app.emit(
                "notification",
                {"type": level, "title": title, "payload": payload or {}},
            )
        except Exception:
            pass
        # Telegram (best effort)
        try:
            text = f"[{level.upper()}] {title}\n{payload or {}}"
            await self.send_telegram(text)
        except Exception:
            pass


notification_service = NotificationService()
