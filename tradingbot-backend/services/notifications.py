"""
Notifications Service - Telegram (optional) + Socket.IO helpers
"""

from __future__ import annotations

from typing import Any

from services.http import apost

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class NotificationService:
    def __init__(self, settings_override=None) -> None:
        # Undvik att skugga importen 'settings'
        self.settings = settings_override or settings
        self._bot_token = getattr(self.settings, "TELEGRAM_BOT_TOKEN", None)
        self._chat_id = getattr(self.settings, "TELEGRAM_CHAT_ID", None)

    async def send_telegram(self, text: str) -> bool:
        if not self._bot_token or not self._chat_id:
            logger.debug("Telegram ej konfigurerat; hoppar över")
            return False
        try:
            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
            payload = {"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"}
            await apost(url, json=payload)
            return True
        except Exception as e:
            logger.warning(f"Telegram-notis misslyckades: {e}")
            return False

    async def notify(self, level: str, title: str, payload: dict[str, Any] | None = None) -> None:
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
