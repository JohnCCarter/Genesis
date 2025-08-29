"""
Global concurrency cap för privata REST-anrop (wallets/positions/order_history).

Användning:
  from utils.private_concurrency import get_private_rest_semaphore
  sem = get_private_rest_semaphore()
  async with sem:
      ...  # gör privata REST-anrop
"""

import asyncio

from config.settings import Settings

_private_sem: asyncio.Semaphore | None = None


def get_private_rest_semaphore() -> asyncio.Semaphore:
    global _private_sem
    if _private_sem is None:
        try:
            conc = int(getattr(Settings(), "PRIVATE_REST_CONCURRENCY", 2) or 2)
        except Exception:
            conc = 2
        _private_sem = asyncio.Semaphore(max(1, conc))
    return _private_sem
