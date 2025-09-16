"""
Global concurrency cap för privata REST-anrop (wallets/positions/order_history).

Användning:
  from utils.private_concurrency import get_private_rest_semaphore
  sem = get_private_rest_semaphore()
  async with sem:
      ...  # gör privata REST-anrop
"""

import asyncio

from config.settings import settings

_private_sems: dict[int, asyncio.Semaphore] = {}


def get_private_rest_semaphore() -> asyncio.Semaphore:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None  # type: ignore
    loop_id = id(loop)
    sem = _private_sems.get(loop_id)
    if sem is None:
        try:
            conc = int(getattr(settings, "PRIVATE_REST_CONCURRENCY", 2) or 2)
        except Exception:
            conc = 2
        sem = asyncio.Semaphore(max(1, conc))
        _private_sems[loop_id] = sem
    return sem
