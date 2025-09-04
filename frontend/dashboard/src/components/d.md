36s

## [debug]Evaluating condition for step: 'Run CI script'

## [debug]Evaluating: success()

## [debug]Evaluating success

## [debug]=> true

## [debug]Result: true

## [debug]Starting: Run CI script

## [debug]Loading inputs

## [debug]Loading env

Run ./tradingbot-backend/scripts/ci.ps1
  ./tradingbot-backend/scripts/ci.ps1
  shell: C:\Program Files\PowerShell\7\pwsh.EXE -command ". '{0}'"
  env:
    pythonLocation: C:\hostedtoolcache\windows\Python\3.11.9\x64
    PKG_CONFIG_PATH: C:\hostedtoolcache\windows\Python\3.11.9\x64/lib/pkgconfig
    Python_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.11.9\x64
    Python2_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.11.9\x64
    Python3_ROOT_DIR: C:\hostedtoolcache\windows\Python\3.11.9\x64

## [debug]C:\Program Files\PowerShell\7\pwsh.EXE -command ". 'D:\a\_temp\cdb24282-49a7-4a24-9977-1d94d0b94c43.ps1'"

=== Black check ===
would reformat D:\a\Genesis\Genesis\tradingbot-backend\config\settings.py

Oh no! \U0001f4a5 \U0001f494 \U0001f4a5
1 file would be reformatted, 128 files would be left unchanged.
=== Ruff check (per pyproject) ===
indicators\atr.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / from typing import List, Optional
 9 | |
10 | | import pandas as pd
11 | | from utils.logger import get_logger
12 | |
13 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

indicators\ema.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / from typing import List, Optional
 9 | |
10 | | import pandas as pd
11 | | from utils.logger import get_logger
12 | |
13 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

indicators\rsi.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / from typing import List, Optional
 9 | |
10 | | import pandas as pd
11 | | from utils.logger import get_logger
12 | |
13 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

main.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import importlib
 9 | | import os
10 | | from contextlib import asynccontextmanager
11 | | from datetime import datetime
12 | |
13 | | import uvicorn
14 | | from fastapi import FastAPI, Request, Response
15 | | from fastapi.middleware.cors import CORSMiddleware
16 | | from fastapi.responses import FileResponse
17 | | from fastapi.staticfiles import StaticFiles
18 | | from rest.routes import router as rest_router
19 | | from services.bitfinex_websocket import bitfinex_ws
20 | | from services.metrics import observe_latency, render_prometheus_text
21 | | from services.runtime_mode import get_validation_on_start, get_ws_connect_on_start
22 | | from services.signal_service import signal_service
23 | | from services.trading_service import trading_service
24 | | from utils.logger import get_logger
25 | | from ws.manager import socket_app
26 | |
27 | | from config.settings import Settings
28 | |
29 | | # Kommenterar ut för att undvika cirkulära imports
   | |_^ I001
30 |   # from tests.test_backend_order import test_backend_limit_order
   |
   = help: Organize imports

main.py:36:20: ARG001 Unused function argument: `app`
   |
35 | @asynccontextmanager
36 | async def lifespan(app: FastAPI):
   |                    ^^^ ARG001
37 |     """Hanterar startup och shutdown för applikationen."""
38 |     # Startup
   |

rest\active_orders.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import json
 9 | | from typing import Any, Dict, List, Optional
10 | |
11 | | import httpx
12 | | from models.api_models import OrderResponse, OrderSide, OrderType
13 | | from utils.logger import get_logger
14 | |
15 | | from config.settings import Settings
16 | | from rest.auth import build_auth_headers
17 | |
18 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

rest\auth.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import hashlib
 9 | | import hmac
10 | | import json
11 | | import os
12 | | from datetime import datetime
13 | | from typing import Optional
14 | |
15 | | from fastapi.security import HTTPBearer
16 | | from utils.logger import get_logger
17 | |
18 | | from config.settings import Settings
19 | |
20 | | security = HTTPBearer()
   | |_^ I001
21 |   logger = get_logger(__name__)
   |
   = help: Organize imports

rest\funding.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / from __future__ import annotations
 9 | |
10 | | import json
11 | | from typing import Any, Dict, List, Optional
12 | |
13 | | import httpx
14 | | from utils.logger import get_logger
15 | |
16 | | from config.settings import Settings
17 | | from rest.auth import build_auth_headers
18 | |
19 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

rest\margin.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / from typing import Any, Dict, List, Optional
 9 | |
10 | | import httpx
11 | | from pydantic import BaseModel
12 | | from utils.bitfinex_rate_limiter import get_bitfinex_rate_limiter
13 | | from utils.logger import get_logger
14 | |
15 | | from config.settings import Settings
16 | | from rest.auth import build_auth_headers
17 | |
18 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

rest\order_history.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import asyncio
 9 | | import json
10 | | import random
11 | | import time
12 | | from datetime import datetime
13 | | from typing import Any, Dict, List, Optional
14 | |
15 | | import httpx
16 | | from pydantic import BaseModel
17 | | from services.metrics import record_http_result
18 | | from utils.advanced_rate_limiter import get_advanced_rate_limiter
19 | | from utils.logger import get_logger
20 | | from utils.private_concurrency import get_private_rest_semaphore
21 | |
22 | | from config.settings import Settings
23 | | from rest.auth import build_auth_headers
24 | |
25 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

rest\order_history.py:315:1: I001 [*] Import block is un-sorted or un-formatted
    |
313 |                                   logger.error(f"🚨 Nonce-fel detekterat: {error_data}")
314 |                                   try:
315 | /                                     from utils.nonce_manager import bump_nonce
316 | |
317 | |                                     from config.settings import Settings as _S
318 | |
    | |_^ I001
319 |                                       api_key =_S().BITFINEX_API_KEY or "default_key"
320 |                                       bump_nonce(api_key)
    |
    = help: Organize imports

rest\positions.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import asyncio
 9 | | import time
10 | | from typing import Any, Dict, List, Optional
11 | |
12 | | import httpx
13 | | from pydantic import BaseModel
14 | | from services.metrics import record_http_result
15 | | from utils.advanced_rate_limiter import get_advanced_rate_limiter
16 | | from utils.logger import get_logger
17 | | from utils.private_concurrency import get_private_rest_semaphore
18 | |
19 | | from config.settings import Settings
20 | | from rest.auth import build_auth_headers
21 | |
22 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

rest\positions_history.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / from datetime import datetime
 9 | | from typing import Any, Dict, List, Optional
10 | |
11 | | import httpx
12 | | from pydantic import BaseModel
13 | | from utils.logger import get_logger
14 | |
15 | | from config.settings import Settings
16 | | from rest.auth import build_auth_headers
17 | |
18 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

rest\routes.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import asyncio
 9 | | from datetime import datetime, timedelta
10 | | from typing import Any, Dict, List, Optional
11 | |
12 | | import jwt
13 | | from fastapi import APIRouter, Depends, HTTPException, Response
14 | | from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
15 | | from indicators.atr import calculate_atr
16 | | from pydantic import BaseModel
17 | | from services.backtest import BacktestService
18 | | from services.bitfinex_data import BitfinexDataService
19 | | from services.bitfinex_websocket import bitfinex_ws
20 | | from services.bracket_manager import bracket_manager
21 | | from services.metrics import get_metrics_summary, inc_labeled, render_prometheus_text
22 | | from services.metrics import inc as metrics_inc
23 | | from services.notifications import notification_service
24 | | from services.performance import PerformanceService
25 | | from services.prob_model import prob_model
26 | | from services.prob_validation import validate_on_candles
27 | | from services.risk_manager import RiskManager
28 | | from services.runtime_mode import (
29 | |     get_validation_on_start,
30 | |     get_ws_connect_on_start,
31 | |     get_ws_strategy_enabled,
32 | |     set_validation_on_start,
33 | |     set_ws_connect_on_start,
34 | |     set_ws_strategy_enabled,
35 | | )
36 | | from services.strategy import evaluate_weighted_strategy
37 | | from services.strategy_settings import StrategySettings, StrategySettingsService
38 | | from services.symbols import SymbolService
39 | | from services.templates import OrderTemplatesService
40 | | from services.trading_integration import trading_integration
41 | | from services.trading_window import TradingWindowService
42 | | from utils.candle_cache import candle_cache
43 | | from utils.logger import get_logger
44 | | from utils.rate_limiter import get_rate_limiter
45 | |
46 | | # WebSocket Autentisering endpoints
47 | | from ws.auth import generate_token
48 | |
49 | | from config.settings import Settings
50 | | from rest import auth as rest_auth
51 | | from rest.active_orders import ActiveOrdersService
52 | | from rest.funding import FundingService
53 | | from rest.margin import MarginService
54 | | from rest.order_history import (
55 | |     LedgerEntry,
56 | |     OrderHistoryItem,
57 | |     OrderHistoryService,
58 | |     TradeItem,
59 | | )
60 | | from rest.order_validator import order_validator
61 | | from rest.positions import Position, PositionsService
62 | | from rest.wallet import WalletBalance, WalletService
63 | |
64 | | logger = get_logger(__name__)
   | |_^ I001
65 |
66 |   router = APIRouter(prefix="/api/v2")
   |
   = help: Organize imports

rest\routes.py:2215:1: I001 [*] Import block is un-sorted or un-formatted
     |
2213 |           # Feature/decision‑loggning (ringbuffer)
2214 |           try:
2215 | /             from services.metrics import metrics_store as_ms
2216 | |
2217 | |             from config.settings import Settings as _S2
2218 | |
     | |_^ I001
2219 |               s2 = _S2()
2220 |               if bool(getattr(s2, "PROB_FEATURE_LOG_ENABLED", False)):
     |
     = help: Organize imports

rest\routes.py:3883:1: I001 [*] Import block is un-sorted or un-formatted
     |
3881 |   async def metrics_acceptance(_: bool = Depends(require_auth)):
3882 |       try:
3883 | /         from services.metrics import get_metrics_summary as_get
3884 | |
3885 | |         from config.settings import Settings as _S
3886 | |
     | |_^ I001
3887 |           s = _S()
3888 |           m =_get()
     |
     = help: Organize imports

rest\routes.py:5213:1: I001 [*] Import block is un-sorted or un-formatted
     |
5211 |       """Hämta prestanda-statistik."""
5212 |       try:
5213 | /         import asyncio
5214 | |
5215 | |         import psutil
5216 | |         from services.data_coordinator import data_coordinator
5217 | |
     | |_^ I001
5218 |           # System-resurser
5219 |           cpu_percent = psutil.cpu_percent(interval=1)
     |
     = help: Organize imports

rest\wallet.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import asyncio
 9 | | import time
10 | | from typing import List, Optional
11 | |
12 | | import httpx
13 | | from pydantic import BaseModel
14 | | from services.metrics import record_http_result
15 | | from utils.advanced_rate_limiter import get_advanced_rate_limiter
16 | | from utils.logger import get_logger
17 | | from utils.private_concurrency import get_private_rest_semaphore
18 | |
19 | | from config.settings import Settings
20 | | from rest.auth import build_auth_headers
21 | |
22 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

scripts\test_ws_subs.py:1:1: I001 [*] Import block is un-sorted or un-formatted
   |
 1 | / import asyncio
 2 | | from typing import Dict, List
 3 | |
 4 | | from services.bitfinex_websocket import bitfinex_ws
 5 | |
 6 | | from config.settings import Settings
 7 | |
 8 | |
 9 | | async def run_test() -> dict[str, dict[str, str]]:
   | |_^ I001
10 |       settings = Settings()
11 |       raw = (settings.WS_SUBSCRIBE_SYMBOLS or "").strip()
   |
   = help: Organize imports

services\backtest.py:5:1: I001 [*] Import block is un-sorted or un-formatted
   |
 3 |   """
 4 |
 5 | / from __future__ import annotations
 6 | |
 7 | | import math
 8 | | from datetime import UTC, datetime, timedelta, timezone
 9 | | from typing import Any, Dict, List
10 | |
11 | | from utils.logger import get_logger
12 | |
13 | | from services.bitfinex_data import BitfinexDataService
14 | | from services.strategy import evaluate_strategy
15 | |
16 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\bitfinex_data.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import asyncio
 9 | | import random
10 | | import time
11 | | from typing import Dict, List, Optional, Tuple
12 | |
13 | | import httpx
14 | | from utils.advanced_rate_limiter import get_advanced_rate_limiter
15 | | from utils.candle_cache import candle_cache
16 | | from utils.logger import get_logger
17 | |
18 | | from config.settings import Settings
19 | | from services.bitfinex_websocket import bitfinex_ws
20 | | from services.metrics import record_http_result
21 | |
22 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\bitfinex_websocket.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import asyncio
 9 | | import json
10 | | import time
11 | | from collections.abc import Callable
12 | | from datetime import datetime
13 | | from typing import Any, Dict, List, Optional
14 | |
15 | | from utils.logger import get_logger
16 | | from websockets.client import connect as ws_connect  # type: ignore[attr-defined]
17 | | from websockets.exceptions import ConnectionClosed  # type: ignore[attr-defined]
18 | | from ws.auth import build_ws_auth_payload
19 | |
20 | | from config.settings import Settings
21 | |
22 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\bracket_manager.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / from __future__ import annotations
 9 | |
10 | | import json
11 | | import os
12 | | from dataclasses import dataclass
13 | | from typing import Any, Dict, Optional, Tuple
14 | |
15 | | from rest.auth import cancel_order
16 | | from utils.logger import get_logger
17 | |
18 | | from config.settings import Settings
19 | |
20 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\cost_aware_backtest.py:12:1: I001 [*] Import block is un-sorted or un-formatted
   |
10 |   """
11 |
12 | / import math
13 | | import random
14 | | from dataclasses import dataclass
15 | | from datetime import datetime, timedelta
16 | | from typing import Any, Dict, List, Optional, Tuple
17 | |
18 | | from utils.logger import get_logger
19 | |
20 | | from services.bitfinex_data import BitfinexDataService
21 | | from services.strategy import evaluate_strategy
22 | |
23 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\enhanced_auto_trader.py:1:1: I001 [*] Import block is un-sorted or un-formatted
   |
 1 | / import asyncio
 2 | | import logging
 3 | | from datetime import datetime, timedelta
 4 | | from typing import Callable, Dict, List, Optional
 5 | |
 6 | | from models.signal_models import SignalResponse, SignalThresholds
 7 | | from utils.logger import get_logger
 8 | |
 9 | | from services.performance_tracker import get_performance_tracker
10 | | from services.realtime_strategy import RealtimeStrategyService
11 | | from services.signal_generator import SignalGeneratorService
12 | | from services.trading_integration import TradingIntegrationService
13 | |
14 | | logger = get_logger(__name__)
   | |_^ I001
15 |
16 |   # Singleton instance
   |
   = help: Organize imports

services\health_watchdog.py:11:1: I001 [*] Import block is un-sorted or un-formatted
   |
 9 |   """
10 |
11 | / import asyncio
12 | | import json
13 | | import os
14 | | import time
15 | | from dataclasses import dataclass
16 | | from datetime import datetime, timedelta
17 | | from typing import Any, Dict, List, Optional, Tuple
18 | |
19 | | from utils.logger import get_logger
20 | |
21 | | from config.settings import Settings
22 | | from services.bitfinex_websocket import bitfinex_ws
23 | | from services.metrics import metrics_store
24 | |
25 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\notifications.py:5:1: I001 [*] Import block is un-sorted or un-formatted
   |
 3 |   """
 4 |
 5 | / from __future__ import annotations
 6 | |
 7 | | from typing import Any, Dict, Optional
 8 | |
 9 | | import httpx
10 | | from utils.logger import get_logger
11 | |
12 | | from config.settings import Settings
13 | |
14 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\performance.py:25:1: I001 [*] Import block is un-sorted or un-formatted
   |
23 |       ZoneInfo = None  # Fallback; använder naive tider
24 |
25 | / from rest.order_history import OrderHistoryService, TradeItem
26 | | from rest.positions import PositionsService
27 | | from rest.wallet import WalletService
28 | | from utils.logger import get_logger
29 | |
30 | | from config.settings import Settings
31 | | from services.bitfinex_data import BitfinexDataService
32 | |
33 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\realtime_strategy.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / from collections.abc import Callable
 9 | | from typing import Dict, List, Optional
10 | |
11 | | from utils.logger import get_logger
12 | |
13 | | from services.bitfinex_websocket import bitfinex_ws
14 | |
15 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\regime_ablation.py:11:1: I001 [*] Import block is un-sorted or un-formatted
   |
 9 |   """
10 |
11 | / import json
12 | | import os
13 | | from dataclasses import dataclass
14 | | from datetime import datetime, timedelta
15 | | from typing import Any, Dict, List, Optional, Tuple
16 | |
17 | | from utils.logger import get_logger
18 | |
19 | | from config.settings import Settings
20 | | from services.metrics import metrics_store
21 | | from services.performance import PerformanceService
22 | |
23 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\regime_ablation.py:365:27: RUF015 Prefer `next(...)` over single element slice
    |
363 |             # Jämför resultat
364 |             best_performance = max(test_results.values(), key=lambda x: x.get("total_pnl", 0))
365 |             best_config = [k for k, v in test_results.items() if v == best_performance][0]
    |                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ RUF015
366 |
367 |             return {
    |
    = help: Replace with `next(...)`

services\risk_guards.py:11:1: I001 [*] Import block is un-sorted or un-formatted
   |
 9 |   """
10 |
11 | / import json
12 | | import os
13 | | from datetime import datetime, timedelta
14 | | from typing import Any, Dict, Optional, Tuple
15 | |
16 | | from utils.logger import get_logger
17 | |
18 | | from config.settings import Settings
19 | | from services.performance import PerformanceService
20 | |
21 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\risk_guards.py:201:37: ARG002 Unused method argument: `symbol`
    |
199 |         return False, None
200 |
201 |     def check_exposure_limits(self, symbol: str, amount: float, price: float) -> tuple[bool, str | None]:
    |                                     ^^^^^^ ARG002
202 |         """
203 |         Kontrollera exposure limits för en ny position.
    |

services\risk_manager.py:5:1: I001 [*] Import block is un-sorted or un-formatted
   |
 3 |   """
 4 |
 5 | / from __future__ import annotations
 6 | |
 7 | | from collections import deque
 8 | | from datetime import datetime, timedelta
 9 | | from typing import Any, Dict, Optional, Tuple
10 | |
11 | | from utils.logger import get_logger
12 | |
13 | | from config.settings import Settings
14 | | from services.metrics import metrics_store
15 | | from services.risk_guards import risk_guards
16 | | from services.trade_counter import TradeCounterService
17 | | from services.trading_window import TradingWindowService
18 | |
19 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\scheduler.py:11:1: I001 [*] Import block is un-sorted or un-formatted
   |
 9 |   """
10 |
11 | / from __future__ import annotations
12 | |
13 | | import asyncio
14 | | import re
15 | | from datetime import UTC, datetime, timedelta, timezone
16 | | from typing import List, Optional
17 | |
18 | | from utils.candle_cache import candle_cache
19 | | from utils.logger import get_logger
20 | |
21 | | from config.settings import Settings
22 | |
23 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\signal_generator.py:1:1: I001 [*] Import block is un-sorted or un-formatted
   |
 1 | / import asyncio
 2 | | import logging
 3 | | import uuid
 4 | | from datetime import datetime, timedelta
 5 | | from typing import Dict, List, Optional
 6 | |
 7 | | from models.signal_models import (
 8 | |     LiveSignalsResponse,
 9 | |     SignalHistory,
10 | |     SignalResponse,
11 | |     SignalStrength,
12 | |     SignalThresholds,
13 | | )
14 | | from utils.logger import get_logger
15 | |
16 | | from services.bitfinex_data import BitfinexDataService
17 | | from services.symbols import SymbolService
18 | |
19 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\signal_service.py:10:1: I001 [*] Import block is un-sorted or un-formatted
   |
 8 |   """
 9 |
10 | / import asyncio
11 | | from datetime import datetime, timedelta
12 | | from typing import Any, Callable, Dict, List, Optional
13 | |
14 | | from models.signal_models import LiveSignalsResponse, SignalResponse
15 | | from utils.logger import get_logger
16 | |
17 | | from services.bitfinex_websocket import BitfinexWebSocketService
18 | | from services.enhanced_auto_trader import EnhancedAutoTrader
19 | | from services.signal_generator import SignalGeneratorService
20 | |
21 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\strategy.py:323:1: I001 [*] Import block is un-sorted or un-formatted
    |
321 |       """
322 |       try:
323 | /         from indicators.regime import detect_regime
324 | |         from strategy.weights import PRESETS, clamp_simplex
325 | |
326 | |         from services.bitfinex_data import BitfinexDataService
327 | |         from services.strategy_settings import StrategySettingsService
328 | |
    | |_^ I001
329 |           # Läs aktuella settings och auto-flaggor
330 |           settings_service = StrategySettingsService()
    |
    = help: Organize imports

services\strategy.py:492:1: I001 [*] Import block is un-sorted or un-formatted
    |
490 |       """
491 |       try:
492 | /         import asyncio
493 | |
494 | |         from indicators.regime import detect_regime
495 | |         from strategy.weights import PRESETS, clamp_simplex
496 | |
497 | |         from services.bitfinex_data import BitfinexDataService
498 | |         from services.strategy_settings import StrategySettingsService
499 | |
    | |_^ I001
500 |           # Läs aktuella settings och auto-flaggor
501 |           settings_service = StrategySettingsService()
    |
    = help: Organize imports

services\strategy_settings.py:7:1: I001 [*] Import block is un-sorted or un-formatted
   |
 5 |   """
 6 |
 7 | / from __future__ import annotations
 8 | |
 9 | | import json
10 | | import os
11 | | from dataclasses import asdict, dataclass
12 | | from typing import Any, Dict, Optional
13 | |
14 | | from utils.logger import get_logger
15 | |
16 | | from config.settings import Settings
17 | |
18 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\trade_counter.py:5:1: I001 [*] Import block is un-sorted or un-formatted
   |
 3 |   """
 4 |
 5 | / from __future__ import annotations
 6 | |
 7 | | import json
 8 | | import os
 9 | | from dataclasses import dataclass
10 | | from datetime import date, datetime
11 | | from typing import Dict, Optional
12 | |
13 | | from utils.logger import get_logger
14 | |
15 | | from config.settings import Settings
16 | | from services.trading_window import TradingWindowService
17 | |
18 | | try:
   | |_^ I001
19 |       from zoneinfo import ZoneInfo  # type: ignore
20 |   except Exception:  # pragma: no cover
   |
   = help: Organize imports

services\trading_integration.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import asyncio
 9 | | from collections.abc import Callable
10 | | from datetime import datetime
11 | | from typing import Any, Dict, Optional
12 | |
13 | | from rest.auth import place_order
14 | | from rest.margin import get_leverage, get_margin_info, get_margin_status
15 | | from rest.positions import get_positions
16 | | from rest.wallet import get_total_balance_usd, get_wallets
17 | | from utils.logger import get_logger
18 | |
19 | | from services.bitfinex_data import bitfinex_data
20 | | from services.metrics import inc
21 | | from services.realtime_strategy import realtime_strategy
22 | | from services.risk_manager import RiskManager
23 | | from services.strategy import evaluate_strategy
24 | |
25 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\trading_service.py:10:1: I001 [*] Import block is un-sorted or un-formatted
   |
 8 |   """
 9 |
10 | / import asyncio
11 | | from datetime import datetime
12 | | from typing import Any, Dict, List, Optional
13 | |
14 | | from models.signal_models import SignalResponse
15 | | from utils.logger import get_logger
16 | |
17 | | from services.bitfinex_websocket import BitfinexWebSocketService
18 | | from services.enhanced_auto_trader import EnhancedAutoTrader
19 | | from services.trading_integration import TradingIntegrationService
20 | |
21 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

services\trading_window.py:5:1: I001 [*] Import block is un-sorted or un-formatted
   |
 3 |   """
 4 |
 5 | / from __future__ import annotations
 6 | |
 7 | | import json
 8 | | import os
 9 | | import re
10 | | from dataclasses import dataclass
11 | | from datetime import datetime, time, timedelta
12 | | from typing import Dict, List, Optional, Tuple
13 | |
14 | | from utils.logger import get_logger
15 | |
16 | | from config.settings import Settings
17 | |
18 | | try:
   | |_^ I001
19 |       from zoneinfo import ZoneInfo  # py3.9+
20 |   except Exception:  # pragma: no cover
   |
   = help: Organize imports

services\ws_first_data_service.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / import asyncio
 9 | | import time
10 | | from collections import defaultdict, deque
11 | | from dataclasses import dataclass
12 | | from datetime import datetime, timedelta
13 | | from typing import Any, Callable, Optional
14 | |
15 | | from utils.advanced_rate_limiter import get_advanced_rate_limiter
16 | | from utils.logger import get_logger
17 | |
18 | | from services.bitfinex_data import BitfinexDataService
19 | | from services.bitfinex_websocket import bitfinex_ws
20 | | from services.incremental_indicators import ATRState, EMAState, RSIState
21 | |
22 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

utils\bitfinex_client.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / from typing import Any, Dict
 9 | |
10 | | import httpx
11 | | from rest.auth import build_auth_headers
12 | | from ws.auth import build_ws_auth_payload
13 | |
14 | | from utils.logger import get_logger
15 | |
16 | | logger = get_logger(__name__)
   | |_^ I001
   |
   = help: Organize imports

utils\json_optimizer.py:43:43: ANN401 Dynamically typed expressions (typing.Any) are disallowed in `loads`
   |
41 |                 self.use_orjson = False
42 |
43 |     def loads(self, data: str | bytes) -> Any:
   |                                           ^^^ ANN401
44 |         """
45 |         Snabb JSON parsing.
   |

utils\json_optimizer.py:62:26: ANN401 Dynamically typed expressions (typing.Any) are disallowed in `obj`
   |
60 |             raise
61 |
62 |     def dumps(self, obj: Any, **kwargs) -> str:
   |                          ^^^ ANN401
63 |         """
64 |         Snabb JSON serialisering.
   |

utils\json_optimizer.py:62:31: ANN003 Missing type annotation for `**kwargs`
   |
60 |             raise
61 |
62 |     def dumps(self, obj: Any, **kwargs) -> str:
   |                               ^^^^^^^^ ANN003
63 |         """
64 |         Snabb JSON serialisering.
   |

utils\json_optimizer.py:83:5: B019 Use of `functools.lru_cache` or `functools.cache` on methods can lead to memory leaks
   |
81 |             raise
82 |
83 |     @lru_cache(maxsize=1000)
   |     ^^^^^^^^^^^^^^^^^^^^^^^^ B019
84 |     def parse_cached(self, data: str) -> Any:
85 |         """
   |

utils\json_optimizer.py:84:42: ANN401 Dynamically typed expressions (typing.Any) are disallowed in `parse_cached`
   |
83 |     @lru_cache(maxsize=1000)
84 |     def parse_cached(self, data: str) -> Any:
   |                                          ^^^ ANN401
85 |         """
86 |         Cached JSON parsing för ofta använd data.
   |

utils\json_optimizer.py:106:37: ANN401 Dynamically typed expressions (typing.Any) are disallowed in `data`
    |
104 |             raise
105 |
106 |     def validate_schema(self, data: Any, schema: BaseModel) -> Any:
    |                                     ^^^ ANN401
107 |         """
108 |         Validera data mot Pydantic schema.
    |

utils\json_optimizer.py:106:64: ANN401 Dynamically typed expressions (typing.Any) are disallowed in `validate_schema`
    |
104 |             raise
105 |
106 |     def validate_schema(self, data: Any, schema: BaseModel) -> Any:
    |                                                                ^^^ ANN401
107 |         """
108 |         Validera data mot Pydantic schema.
    |

utils\json_optimizer.py:169:25: PLW2901 `for` loop variable `value` overwritten by assignment target
    |
167 |                 try:
168 |                     if "." in value:
169 |                         value = float(value)
    |                         ^^^^^ PLW2901
170 |                     else:
171 |                         value = int(value)
    |

utils\json_optimizer.py:171:25: PLW2901 `for` loop variable `value` overwritten by assignment target
    |
169 |                         value = float(value)
170 |                     else:
171 |                         value = int(value)
    |                         ^^^^^ PLW2901
172 |                 except ValueError:
173 |                     pass
    |

utils\json_optimizer.py:177:17: PLW2901 `for` loop variable `value` overwritten by assignment target
    |
175 |             # Rekursiv optimering för nested dictionaries
176 |             elif isinstance(value, dict):
177 |                 value = self.optimize_dict(value)
    |                 ^^^^^ PLW2901
178 |
179 |             # Optimera listor
    |

utils\json_optimizer.py:181:17: PLW2901 `for` loop variable `value` overwritten by assignment target
    |
179 |             # Optimera listor
180 |             elif isinstance(value, list):
181 |                 value = [self.optimize_dict(item) if isinstance(item, dict) else item for item in value]
    |                 ^^^^^ PLW2901
182 |
183 |             optimized[key] = value
    |

Found 57 errors.
[*] 43 fixable with the `--fix` option (1 hidden fix can be enabled with the `--unsafe-fixes` option).
=== Pytest ===
sss..............sssssssssss...........s..ssssssssss...FF............... [ 77%]
...........sssssss...                                                    [100%]
================================== FAILURES ===================================
__________ TestRiskGuardsService.test_check_max_daily_loss_triggered __________

self = <tests.test_risk_guards.TestRiskGuardsService object at 0x00000288DB73CAD0>
mock_equity = <MagicMock name='_get_current_equity' id='2786800980752'>

    @patch('services.risk_guards.RiskGuardsService._get_current_equity')
    def test_check_max_daily_loss_triggered(self, mock_equity):
        """Test max daily loss n�r triggad."""
        mock_equity.return_value = 9400.0  # 6% f�rlust

        # S�tt start equity
        self.service.guards["max_daily_loss"]["daily_start_equity"] = 10000.0
        self.service.guards["max_daily_loss"]["enabled"] = True
        self.service.guards["max_daily_loss"]["percentage"] = 5.0

        # Test - f�rlust �ver gr�nsen
        blocked, reason = self.service.check_max_daily_loss()
>       assert blocked is True
E       assert False is True

tests\test_risk_guards.py:117: AssertionError
---------------------------- Captured stdout setup ----------------------------
2025-08-29 09:05:40 - services.risk_guards - INFO - \U0001f4cb Laddade riskvakter fr\xe5n config/risk_guards.json\n2025-08-29 09:05:40 - services.risk_guards - INFO - \U0001f6e1\ufe0f RiskGuardsService initialiserad
----------------------------- Captured log setup ------------------------------
INFO     services.risk_guards:risk_guards.py:43 \U0001f4cb Laddade riskvakter fr\xe5n config/risk_guards.json\nINFO     services.risk_guards:risk_guards.py:35 \U0001f6e1\ufe0f RiskGuardsService initialiserad
---------------------------- Captured stdout call -----------------------------
2025-08-29 09:05:40 - services.risk_guards - INFO - \U0001f4c5 Ny dag initialiserad: 2025-08-29
------------------------------ Captured log call ------------------------------
INFO     services.risk_guards:risk_guards.py:114 \U0001f4c5 Ny dag initialiserad: 2025-08-29
__________ TestRiskGuardsService.test_check_max_daily_loss_cooldown ___________

self = <tests.test_risk_guards.TestRiskGuardsService object at 0x00000288DB73DA10>
mock_equity = <MagicMock name='_get_current_equity' id='2786802984784'>

    @patch('services.risk_guards.RiskGuardsService._get_current_equity')
    def test_check_max_daily_loss_cooldown(self, mock_equity):
        """Test max daily loss cooldown."""
        mock_equity.return_value = 9400.0

        # S�tt triggad status med nyligen timestamp
        self.service.guards["max_daily_loss"]["triggered"] = True
        self.service.guards["max_daily_loss"]["triggered_at"] = datetime.now().isoformat()
        self.service.guards["max_daily_loss"]["cooldown_hours"] = 24

        # Test - cooldown aktiv
        blocked, reason = self.service.check_max_daily_loss()
>       assert blocked is True
E       assert False is True

tests\test_risk_guards.py:133: AssertionError
---------------------------- Captured stdout setup ----------------------------
2025-08-29 09:05:41 - services.risk_guards - INFO - \U0001f4cb Laddade riskvakter fr\xe5n config/risk_guards.json\n2025-08-29 09:05:41 - services.risk_guards - INFO - \U0001f6e1\ufe0f RiskGuardsService initialiserad
----------------------------- Captured log setup ------------------------------
INFO     services.risk_guards:risk_guards.py:43 \U0001f4cb Laddade riskvakter fr\xe5n config/risk_guards.json\nINFO     services.risk_guards:risk_guards.py:35 \U0001f6e1\ufe0f RiskGuardsService initialiserad
---------------------------- Captured stdout call -----------------------------
2025-08-29 09:05:41 - services.risk_guards - INFO - \U0001f4c5 Ny dag initialiserad: 2025-08-29
------------------------------ Captured log call ------------------------------
INFO     services.risk_guards:risk_guards.py:114 \U0001f4c5 Ny dag initialiserad: 2025-08-29
============================== warnings summary ===============================
services\bitfinex_websocket.py:16
  D:\a\Genesis\Genesis\tradingbot-backend\services\bitfinex_websocket.py:16: DeprecationWarning: websockets.client.connect is deprecated
    from websockets.client import connect as ws_connect  # type: ignore[attr-defined]

C:\hostedtoolcache\windows\Python\3.11.9\x64\Lib\site-packages\websockets\legacy\__init__.py:6
  C:\hostedtoolcache\windows\Python\3.11.9\x64\Lib\site-packages\websockets\legacy\__init__.py:6: DeprecationWarning: websockets.legacy is deprecated; see <https://websockets.readthedocs.io/en/stable/howto/upgrade.html> for upgrade instructions
    warnings.warn(  # deprecated in 14.0 - 2024-11-09

-- Docs: <https://docs.pytest.org/en/stable/how-to/capture-warnings.html>
=========================== short test summary info ===========================
FAILED tests/test_risk_guards.py::TestRiskGuardsService::test_check_max_daily_loss_triggered - assert False is True
FAILED tests/test_risk_guards.py::TestRiskGuardsService::test_check_max_daily_loss_cooldown - assert False is True
=== Bandit (exclude tests via bandit.yaml) ===
Traceback (most recent call last):
  File "C:\hostedtoolcache\windows\Python\3.11.9\x64\Lib\site-packages\bandit\core\manager.py", line 186, in output_results
    report_func(
  File "C:\hostedtoolcache\windows\Python\3.11.9\x64\Lib\site-packages\bandit\formatters\text.py", line 195, in report
    wrapped_file.write(result)
  File "C:\hostedtoolcache\windows\Python\3.11.9\x64\Lib\encodings\cp1252.py", line 19, in encode
    return codecs.charmap_encode[input,self.errors,encoding_table](0)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f501' in position 67876: character maps to <undefined>

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\hostedtoolcache\windows\Python\3.11.9\x64\Lib\site-packages\bandit\__main__.py", line 17, in <module>
    main.main()
  File "C:\hostedtoolcache\windows\Python\3.11.9\x64\Lib\site-packages\bandit\cli\main.py", line 678, in main
    b_mgr.output_results(
  File "C:\hostedtoolcache\windows\Python\3.11.9\x64\Lib\site-packages\bandit\core\manager.py", line 195, in output_results
    raise RuntimeError(
RuntimeError: Unable to output report using 'txt' formatter: 'charmap' codec can't encode character '\U0001f501' in position 67876: character maps to <undefined>
=== Pylint (report only) ===
************* Module services.backtest
services\backtest.py:61:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\backtest.py:20:4: R0912: Too many branches (28/12) (too-many-branches)
services\backtest.py:20:4: R0915: Too many statements (113/50) (too-many-statements)
services\backtest.py:8:0: W0611: Unused timezone imported from datetime (unused-import)
services\backtest.py:9:0: W0611: Unused Dict imported from typing (unused-import)
services\backtest.py:9:0: W0611: Unused List imported from typing (unused-import)
************* Module services.bitfinex_data
services\bitfinex_data.py:569:0: C0301: Line too long (159/120) (line-too-long)
services\bitfinex_data.py:51:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:53:8: W0404: Reimport 'asyncio' (imported line 8) (reimported)
services\bitfinex_data.py:53:8: C0415: Import outside toplevel (asyncio) (import-outside-toplevel)
services\bitfinex_data.py:201:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:80:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:75:16: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\bitfinex_data.py:178:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:123:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:145:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:130:24: E1123: Unexpected keyword argument 'retry_after' in function call (unexpected-keyword-arg)
services\bitfinex_data.py:157:31: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:169:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:71:8: R1702: Too many nested blocks (6/5) (too-many-nested-blocks)
services\bitfinex_data.py:175:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:189:31: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:59:4: R0912: Too many branches (18/12) (too-many-branches)
services\bitfinex_data.py:59:4: R0915: Too many statements (82/50) (too-many-statements)
services\bitfinex_data.py:509:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:222:12: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_data.py:222:12: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_data.py:224:12: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\bitfinex_data.py:366:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:262:16: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_data.py:262:16: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_data.py:275:34: W0212: Access to a protected member_last_tick_ts of a client class (protected-access)
services\bitfinex_data.py:364:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:326:73: W0212: Access to a protected member _handle_ticker_with_strategy of a client class (protected-access)
services\bitfinex_data.py:327:71: W0212: Access to a protected member_handle_ticker_with_strategy of a client class (protected-access)
services\bitfinex_data.py:221:8: R1702: Too many nested blocks (7/5) (too-many-nested-blocks)
services\bitfinex_data.py:221:8: R1702: Too many nested blocks (8/5) (too-many-nested-blocks)
services\bitfinex_data.py:221:8: R1702: Too many nested blocks (7/5) (too-many-nested-blocks)
services\bitfinex_data.py:487:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:412:35: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:434:35: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:419:32: E1123: Unexpected keyword argument 'retry_after' in function call (unexpected-keyword-arg)
services\bitfinex_data.py:445:39: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:478:35: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:484:35: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:497:35: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:211:4: R0911: Too many return statements (8/6) (too-many-return-statements)
services\bitfinex_data.py:211:4: R0912: Too many branches (40/12) (too-many-branches)
services\bitfinex_data.py:211:4: R0915: Too many statements (170/50) (too-many-statements)
services\bitfinex_data.py:615:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:598:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:545:31: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:558:35: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:589:31: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:587:39: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:595:31: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:604:31: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:513:4: R0912: Too many branches (18/12) (too-many-branches)
services\bitfinex_data.py:513:4: R0915: Too many statements (69/50) (too-many-statements)
services\bitfinex_data.py:631:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:677:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:641:12: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_data.py:641:12: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_data.py:671:39: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:663:16: R1702: Too many nested blocks (6/5) (too-many-nested-blocks)
services\bitfinex_data.py:726:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:689:12: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_data.py:689:12: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_data.py:815:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:743:12: C0415: Import outside toplevel (sqlite3.Row) (import-outside-toplevel)
services\bitfinex_data.py:757:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:748:16: C0415: Import outside toplevel (sqlite3) (import-outside-toplevel)
services\bitfinex_data.py:785:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:802:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:811:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_data.py:730:4: R0912: Too many branches (13/12) (too-many-branches)
services\bitfinex_data.py:730:4: R0915: Too many statements (61/50) (too-many-statements)
services\bitfinex_data.py:11:0: W0611: Unused Dict imported from typing (unused-import)
services\bitfinex_data.py:11:0: W0611: Unused List imported from typing (unused-import)
services\bitfinex_data.py:11:0: W0611: Unused Optional imported from typing (unused-import)
services\bitfinex_data.py:11:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module services.bitfinex_websocket
services\bitfinex_websocket.py:830:0: C0301: Line too long (122/120) (line-too-long)
services\bitfinex_websocket.py:1:0: C0302: Too many lines in module (1817/1000) (too-many-lines)
services\bitfinex_websocket.py:16:0: E0611: No name 'connect' in module 'websockets.client' (no-name-in-module)
services\bitfinex_websocket.py:25:0: R0902: Too many instance attributes (52/7) (too-many-instance-attributes)
services\bitfinex_websocket.py:54:8: W0404: Reimport 'asyncio' (imported line 8) (reimported)
services\bitfinex_websocket.py:54:8: C0415: Import outside toplevel (asyncio) (import-outside-toplevel)
services\bitfinex_websocket.py:93:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:28:4: R0915: Too many statements (53/50) (too-many-statements)
services\bitfinex_websocket.py:137:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:154:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:145:12: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_websocket.py:145:12: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_websocket.py:200:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:171:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:186:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:230:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:223:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:228:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:262:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:259:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:255:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:294:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:269:12: C0415: Import outside toplevel (re) (import-outside-toplevel)
services\bitfinex_websocket.py:267:4: R0911: Too many return statements (7/6) (too-many-return-statements)
services\bitfinex_websocket.py:370:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:320:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:311:16: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\bitfinex_websocket.py:330:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:327:16: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_websocket.py:327:16: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_websocket.py:348:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:343:20: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\bitfinex_websocket.py:366:31: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:297:4: R0912: Too many branches (17/12) (too-many-branches)
services\bitfinex_websocket.py:297:4: R0915: Too many statements (52/50) (too-many-statements)
services\bitfinex_websocket.py:385:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:415:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:400:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:412:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:406:16: C0415: Import outside toplevel (os) (import-outside-toplevel)
services\bitfinex_websocket.py:433:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:431:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:445:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:482:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:480:24: W1309: Using an f-string that does not have any interpolated variables (f-string-without-interpolation)
services\bitfinex_websocket.py:501:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:520:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:565:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:562:31: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:575:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:524:4: R0912: Too many branches (15/12) (too-many-branches)
services\bitfinex_websocket.py:588:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:604:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:614:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:631:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:627:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:657:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:675:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:673:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:693:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:691:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:684:20: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_websocket.py:684:20: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_websocket.py:705:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:716:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:722:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:719:20: C0415: Import outside toplevel (random) (import-outside-toplevel)
services\bitfinex_websocket.py:734:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:732:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:744:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:742:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:696:4: R0912: Too many branches (13/12) (too-many-branches)
services\bitfinex_websocket.py:711:16: W0612: Unused variable 'attempt' (unused-variable)
services\bitfinex_websocket.py:826:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:770:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:762:16: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\bitfinex_websocket.py:785:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:797:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:816:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:821:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:749:4: R0912: Too many branches (13/12) (too-many-branches)
services\bitfinex_websocket.py:749:4: R0915: Too many statements (51/50) (too-many-statements)
services\bitfinex_websocket.py:853:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:843:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:880:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:859:12: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\bitfinex_websocket.py:877:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:875:35: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:941:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:858:8: R1702: Too many nested blocks (6/5) (too-many-nested-blocks)
services\bitfinex_websocket.py:904:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:896:16: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\bitfinex_websocket.py:923:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:936:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:964:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1021:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:982:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:974:16: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\bitfinex_websocket.py:1000:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1013:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1018:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1084:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1046:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1038:16: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\bitfinex_websocket.py:1070:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1155:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1121:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1127:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1124:16: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_websocket.py:1124:16: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_websocket.py:1147:16: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_websocket.py:1147:16: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_websocket.py:1212:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1166:12: C0415: Import outside toplevel (services.strategy.evaluate_strategy) (import-outside-toplevel)
services\bitfinex_websocket.py:1192:12: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_websocket.py:1192:12: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_websocket.py:1252:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1240:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1229:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1226:24: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_websocket.py:1226:24: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_websocket.py:1245:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1352:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1269:20: R1705: Unnecessary "elif" after "return", remove the leading "el" from "elif" (no-else-return)
services\bitfinex_websocket.py:1256:4: R0911: Too many return statements (9/6) (too-many-return-statements)
services\bitfinex_websocket.py:1256:4: R0912: Too many branches (18/12) (too-many-branches)
services\bitfinex_websocket.py:1355:42: W0613: Unused argument 'channel_id' (unused-argument)
services\bitfinex_websocket.py:1428:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1401:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1362:4: R0912: Too many branches (19/12) (too-many-branches)
services\bitfinex_websocket.py:1362:4: R0915: Too many statements (54/50) (too-many-statements)
services\bitfinex_websocket.py:1463:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1445:12: W0404: Reimport 'time' (imported line 10) (reimported)
services\bitfinex_websocket.py:1445:12: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\bitfinex_websocket.py:1495:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1525:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1548:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1597:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1565:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1560:16: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\bitfinex_websocket.py:1680:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1628:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1623:20: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\bitfinex_websocket.py:1673:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1601:4: R0912: Too many branches (14/12) (too-many-branches)
services\bitfinex_websocket.py:1732:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1698:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1693:16: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\bitfinex_websocket.py:1767:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:1802:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bitfinex_websocket.py:217:20: W0201: Attribute '_current_incoming_ws' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:227:24: W0201: Attribute '_current_incoming_ws' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:1223:20: W0201: Attribute '_current_incoming_ws' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:1244:24: W0201: Attribute '_current_incoming_ws' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:347:20: W0201: Attribute '_pairs_cache' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:1483:16: W0201: Attribute 'positions' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:1513:16: W0201: Attribute 'wallets' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:1543:20: W0201: Attribute 'funding_rates' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:1578:16: W0201: Attribute '_calc_cache' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:1641:20: W0201: Attribute '_calc_cache' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:1711:16: W0201: Attribute '_calc_cache' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:1752:16: W0201: Attribute '_calc_cache' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:1787:16: W0201: Attribute '_calc_cache' defined outside __init__ (attribute-defined-outside-init)
services\bitfinex_websocket.py:25:0: R0904: Too many public methods (26/20) (too-many-public-methods)
services\bitfinex_websocket.py:16:0: C0411: third party import "websockets.client.connect" should be placed before first party import "utils.logger.get_logger"  (wrong-import-order)
services\bitfinex_websocket.py:17:0: C0411: third party import "websockets.exceptions.ConnectionClosed" should be placed before first party import "utils.logger.get_logger"  (wrong-import-order)
services\bitfinex_websocket.py:13:0: W0611: Unused Dict imported from typing (unused-import)
services\bitfinex_websocket.py:13:0: W0611: Unused List imported from typing (unused-import)
services\bitfinex_websocket.py:13:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.bracket_manager
services\bracket_manager.py:75:0: C0301: Line too long (121/120) (line-too-long)
services\bracket_manager.py:44:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:78:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:150:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:107:39: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:85:8: R1702: Too many nested blocks (8/5) (too-many-nested-blocks)
services\bracket_manager.py:116:43: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:85:8: R1702: Too many nested blocks (8/5) (too-many-nested-blocks)
services\bracket_manager.py:138:47: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:83:4: R0912: Too many branches (22/12) (too-many-branches)
services\bracket_manager.py:83:4: R0915: Too many statements (53/50) (too-many-statements)
services\bracket_manager.py:93:20: W0612: Unused variable 'exec_price' (unused-variable)
services\bracket_manager.py:185:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:85:8: R1702: Too many nested blocks (9/5) (too-many-nested-blocks)
services\bracket_manager.py:167:12: C0415: Import outside toplevel (rest.active_orders.ActiveOrdersService) (import-outside-toplevel)
services\bracket_manager.py:200:8: C0415: Import outside toplevel (rest.active_orders.ActiveOrdersService) (import-outside-toplevel)
services\bracket_manager.py:216:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:261:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:278:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:326:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:337:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\bracket_manager.py:13:0: W0611: Unused Dict imported from typing (unused-import)
services\bracket_manager.py:13:0: W0611: Unused Optional imported from typing (unused-import)
services\bracket_manager.py:13:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module services.cost_aware_backtest
services\cost_aware_backtest.py:39:0: R0902: Too many instance attributes (11/7) (too-many-instance-attributes)
services\cost_aware_backtest.py:56:0: R0902: Too many instance attributes (17/7) (too-many-instance-attributes)
services\cost_aware_backtest.py:423:12: W0612: Unused variable 'latency' (unused-variable)
services\cost_aware_backtest.py:530:34: W0612: Unused variable 'spread_cost' (unused-variable)
services\cost_aware_backtest.py:15:0: W0611: Unused timedelta imported from datetime (unused-import)
services\cost_aware_backtest.py:16:0: W0611: Unused Dict imported from typing (unused-import)
services\cost_aware_backtest.py:16:0: W0611: Unused List imported from typing (unused-import)
services\cost_aware_backtest.py:16:0: W0611: Unused Optional imported from typing (unused-import)
services\cost_aware_backtest.py:16:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module services.data_coordinator
services\data_coordinator.py:111:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\data_coordinator.py:117:8: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\data_coordinator.py:121:0: W0613: Unused argument 'kwargs' (unused-argument)
services\data_coordinator.py:128:8: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\data_coordinator.py:139:8: C0415: Import outside toplevel (rest.margin.margin_service) (import-outside-toplevel)
services\data_coordinator.py:150:8: C0415: Import outside toplevel (rest.margin.margin_service) (import-outside-toplevel)
services\data_coordinator.py:200:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\data_coordinator.py:172:12: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\data_coordinator.py:241:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\data_coordinator.py:215:12: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\data_coordinator.py:11:0: W0611: Unused timedelta imported from datetime (unused-import)
services\data_coordinator.py:12:0: W0611: Unused Dict imported from typing (unused-import)
services\data_coordinator.py:12:0: W0611: Unused List imported from typing (unused-import)
services\data_coordinator.py:12:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.enhanced_auto_trader
services\enhanced_auto_trader.py:112:0: C0301: Line too long (131/120) (line-too-long)
services\enhanced_auto_trader.py:17:0: C0103: Constant name "_enhanced_trader_instance" doesn't conform to UPPER_CASE naming style (invalid-name)
services\enhanced_auto_trader.py:20:0: R0902: Too many instance attributes (9/7) (too-many-instance-attributes)
services\enhanced_auto_trader.py:47:8: W0603: Using the global statement (global-statement)
services\enhanced_auto_trader.py:73:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\enhanced_auto_trader.py:89:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\enhanced_auto_trader.py:119:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\enhanced_auto_trader.py:135:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\enhanced_auto_trader.py:161:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\enhanced_auto_trader.py:201:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\enhanced_auto_trader.py:227:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\enhanced_auto_trader.py:240:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\enhanced_auto_trader.py:269:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\enhanced_auto_trader.py:282:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\enhanced_auto_trader.py:1:0: W0611: Unused import asyncio (unused-import)
services\enhanced_auto_trader.py:2:0: W0611: Unused import logging (unused-import)
services\enhanced_auto_trader.py:4:0: W0611: Unused Dict imported from typing (unused-import)
services\enhanced_auto_trader.py:4:0: W0611: Unused List imported from typing (unused-import)
services\enhanced_auto_trader.py:4:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.health_watchdog
services\health_watchdog.py:42:0: R0902: Too many instance attributes (8/7) (too-many-instance-attributes)
services\health_watchdog.py:86:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:157:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:175:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:193:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:220:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:202:12: C0415: Import outside toplevel (rest.auth.get_auth_headers) (import-outside-toplevel)
services\health_watchdog.py:202:12: E0611: No name 'get_auth_headers' in module 'rest.auth' (no-name-in-module)
services\health_watchdog.py:208:12: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
services\health_watchdog.py:248:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:232:12: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
services\health_watchdog.py:281:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:257:12: C0415: Import outside toplevel (sqlite3) (import-outside-toplevel)
services\health_watchdog.py:261:12: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
services\health_watchdog.py:313:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:287:12: C0415: Import outside toplevel (psutil) (import-outside-toplevel)
services\health_watchdog.py:344:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:319:12: C0415: Import outside toplevel (psutil) (import-outside-toplevel)
services\health_watchdog.py:389:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:351:12: C0415: Import outside toplevel (services.performance.PerformanceService) (import-outside-toplevel)
services\health_watchdog.py:356:28: E1101: Instance of 'PerformanceService' has no 'get_recent_trades' member (no-member)
services\health_watchdog.py:369:12: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
services\health_watchdog.py:485:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:392:4: R0912: Too many branches (19/12) (too-many-branches)
services\health_watchdog.py:392:4: R0915: Too many statements (51/50) (too-many-statements)
services\health_watchdog.py:523:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:511:22: E1101: Instance of 'BitfinexWebSocketService' has no 'reconnect' member (no-member)
services\health_watchdog.py:516:16: C0415: Import outside toplevel (rest.auth.clear_auth_cache) (import-outside-toplevel)
services\health_watchdog.py:516:16: E0611: No name 'clear_auth_cache' in module 'rest.auth' (no-name-in-module)
services\health_watchdog.py:534:8: C0206: Consider iterating with .items() (consider-using-dict-items)
services\health_watchdog.py:578:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:626:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\health_watchdog.py:16:0: W0611: Unused timedelta imported from datetime (unused-import)
services\health_watchdog.py:17:0: W0611: Unused Dict imported from typing (unused-import)
services\health_watchdog.py:17:0: W0611: Unused List imported from typing (unused-import)
services\health_watchdog.py:17:0: W0611: Unused Optional imported from typing (unused-import)
services\health_watchdog.py:17:0: W0611: Unused Tuple imported from typing (unused-import)
services\health_watchdog.py:23:0: W0611: Unused metrics_store imported from services.metrics (unused-import)
************* Module services.incremental_indicators
services\incremental_indicators.py:10:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.metrics
services\metrics.py:59:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:90:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:139:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:137:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:127:16: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\metrics.py:149:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:196:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:194:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:206:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:219:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:217:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:245:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:310:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:258:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:264:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:271:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:280:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:287:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:308:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:306:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:153:0: R0912: Too many branches (30/12) (too-many-branches)
services\metrics.py:153:0: R0915: Too many statements (132/50) (too-many-statements)
services\metrics.py:332:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:325:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:324:16: W0612: Unused variable 'method' (unused-variable)
services\metrics.py:324:30: W0612: Unused variable 'status' (unused-variable)
services\metrics.py:368:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:349:8: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\metrics.py:395:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:388:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\metrics.py:385:23: W0718: Catching too general exception Exception (broad-exception-caught)
************* Module services.notifications
services\notifications.py:34:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\notifications.py:47:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\notifications.py:41:12: C0415: Import outside toplevel (ws.manager.socket_app) (import-outside-toplevel)
services\notifications.py:53:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\notifications.py:7:0: W0611: Unused Dict imported from typing (unused-import)
services\notifications.py:7:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.performance
services\performance.py:22:7: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:23:4: C0103: Constant name "ZoneInfo" doesn't conform to UPPER_CASE naming style (invalid-name)
services\performance.py:44:0: R0902: Too many instance attributes (8/7) (too-many-instance-attributes)
services\performance.py:123:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:132:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:143:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:152:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:93:4: R0911: Too many return statements (9/6) (too-many-return-statements)
services\performance.py:93:4: R0912: Too many branches (13/12) (too-many-branches)
services\performance.py:171:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:189:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:208:15: R1716: Simplify chained comparison between the operands (chained-comparison)
services\performance.py:210:17: R1716: Simplify chained comparison between the operands (chained-comparison)
services\performance.py:218:18: R1716: Simplify chained comparison between the operands (chained-comparison)
services\performance.py:218:58: R1716: Simplify chained comparison between the operands (chained-comparison)
services\performance.py:238:19: C0201: Consider iterating the dictionary directly instead of calling .keys() (consider-iterating-dictionary)
services\performance.py:241:23: C0201: Consider iterating the dictionary directly instead of calling .keys() (consider-iterating-dictionary)
services\performance.py:247:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:278:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:159:4: R0912: Too many branches (21/12) (too-many-branches)
services\performance.py:159:4: R0915: Too many statements (70/50) (too-many-statements)
services\performance.py:303:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:325:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:335:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:343:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance.py:17:0: W0611: Unused Dict imported from typing (unused-import)
services\performance.py:17:0: W0611: Unused List imported from typing (unused-import)
services\performance.py:17:0: W0611: Unused Optional imported from typing (unused-import)
services\performance.py:17:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module services.performance_tracker
services\performance_tracker.py:35:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance_tracker.py:30:21: W1514: Using open without explicitly specifying an encoding (unspecified-encoding)
services\performance_tracker.py:52:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance_tracker.py:42:17: W1514: Using open without explicitly specifying an encoding (unspecified-encoding)
services\performance_tracker.py:87:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance_tracker.py:125:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance_tracker.py:191:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance_tracker.py:244:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance_tracker.py:288:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance_tracker.py:296:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance_tracker.py:310:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\performance_tracker.py:316:0: C0103: Constant name "_performance_tracker_instance" doesn't conform to UPPER_CASE naming style (invalid-name)
services\performance_tracker.py:321:4: W0603: Using the global statement (global-statement)
services\performance_tracker.py:1:0: W0611: Unused import asyncio (unused-import)
services\performance_tracker.py:5:0: W0611: Unused Any imported from typing (unused-import)
services\performance_tracker.py:5:0: W0611: Unused Dict imported from typing (unused-import)
services\performance_tracker.py:5:0: W0611: Unused List imported from typing (unused-import)
services\performance_tracker.py:5:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.prob_features
services\prob_features.py:105:4: C0200: Consider using enumerate instead of iterating with range and len (consider-using-enumerate)
services\prob_features.py:11:0: W0611: Unused Dict imported from typing (unused-import)
services\prob_features.py:11:0: W0611: Unused List imported from typing (unused-import)
services\prob_features.py:11:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module services.prob_model
services\prob_model.py:33:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\prob_model.py:42:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\prob_model.py:87:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\prob_model.py:60:16: C0415: Import outside toplevel (math) (import-outside-toplevel)
services\prob_model.py:10:0: W0611: Unused Dict imported from typing (unused-import)
services\prob_model.py:10:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.prob_train
services\prob_train.py:19:0: C0103: Function name "_to_Xy" doesn't conform to snake_case naming style (invalid-name)
services\prob_train.py:23:4: C0103: Variable name "X" doesn't conform to snake_case naming style (invalid-name)
services\prob_train.py:29:12: C0103: Argument name "X" doesn't conform to snake_case naming style (invalid-name)
services\prob_train.py:44:21: C0103: Argument name "X" doesn't conform to snake_case naming style (invalid-name)
services\prob_train.py:68:4: C0103: Variable name "X" doesn't conform to snake_case naming style (invalid-name)
services\prob_train.py:69:4: C0103: Variable name "Xb_tr" doesn't conform to snake_case naming style (invalid-name)
services\prob_train.py:69:18: C0103: Variable name "Xb_va" doesn't conform to snake_case naming style (invalid-name)
services\prob_train.py:70:4: C0103: Variable name "Xs_tr" doesn't conform to snake_case naming style (invalid-name)
services\prob_train.py:70:18: C0103: Variable name "Xs_va" doesn't conform to snake_case naming style (invalid-name)
services\prob_train.py:12:0: W0611: Unused Dict imported from typing (unused-import)
services\prob_train.py:12:0: W0611: Unused List imported from typing (unused-import)
************* Module services.prob_train_runner
services\prob_train_runner.py:40:4: W0612: Unused variable 'model' (unused-variable)
services\prob_train_runner.py:13:0: W0611: Unused List imported from typing (unused-import)
************* Module services.prob_validation
services\prob_validation.py:12:0: W0611: Unused Dict imported from typing (unused-import)
services\prob_validation.py:12:0: W0611: Unused List imported from typing (unused-import)
services\prob_validation.py:12:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module services.realtime_strategy
services\realtime_strategy.py:52:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\realtime_strategy.py:74:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\realtime_strategy.py:102:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\realtime_strategy.py:118:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\realtime_strategy.py:114:12: C0415: Import outside toplevel (ws.manager.socket_app) (import-outside-toplevel)
services\realtime_strategy.py:161:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\realtime_strategy.py:9:0: W0611: Unused Dict imported from typing (unused-import)
services\realtime_strategy.py:9:0: W0611: Unused List imported from typing (unused-import)
services\realtime_strategy.py:9:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.regime_ablation
services\regime_ablation.py:40:0: R0902: Too many instance attributes (12/7) (too-many-instance-attributes)
services\regime_ablation.py:85:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\regime_ablation.py:138:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\regime_ablation.py:154:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\regime_ablation.py:170:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\regime_ablation.py:233:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\regime_ablation.py:255:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\regime_ablation.py:376:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\regime_ablation.py:439:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\regime_ablation.py:477:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\regime_ablation.py:14:0: W0611: Unused timedelta imported from datetime (unused-import)
services\regime_ablation.py:15:0: W0611: Unused Dict imported from typing (unused-import)
services\regime_ablation.py:15:0: W0611: Unused List imported from typing (unused-import)
services\regime_ablation.py:15:0: W0611: Unused Optional imported from typing (unused-import)
services\regime_ablation.py:15:0: W0611: Unused Tuple imported from typing (unused-import)
services\regime_ablation.py:20:0: W0611: Unused metrics_store imported from services.metrics (unused-import)
************* Module services.risk_guards
services\risk_guards.py:45:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_guards.py:89:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_guards.py:99:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_guards.py:139:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_guards.py:180:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_guards.py:237:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_guards.py:201:36: W0613: Unused argument 'symbol' (unused-argument)
services\risk_guards.py:297:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_guards.py:329:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_guards.py:351:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_guards.py:14:0: W0611: Unused Dict imported from typing (unused-import)
services\risk_guards.py:14:0: W0611: Unused Optional imported from typing (unused-import)
services\risk_guards.py:14:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module services.risk_manager
services\risk_manager.py:58:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_manager.py:35:4: R0911: Too many return statements (8/6) (too-many-return-statements)
services\risk_manager.py:75:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_manager.py:95:35: W0613: Unused argument 'now' (unused-argument)
services\risk_manager.py:131:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_manager.py:105:12: W0603: Using the global statement (global-statement)
services\risk_manager.py:110:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_manager.py:129:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_manager.py:114:20: C0415: Import outside toplevel (asyncio) (import-outside-toplevel)
services\risk_manager.py:116:20: C0415: Import outside toplevel (services.notifications.notification_service) (import-outside-toplevel)
services\risk_manager.py:188:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_manager.py:160:12: W0603: Using the global statement (global-statement)
services\risk_manager.py:164:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_manager.py:169:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_manager.py:186:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\risk_manager.py:173:20: C0415: Import outside toplevel (ws.manager.socket_app) (import-outside-toplevel)
services\risk_manager.py:201:8: C0415: Import outside toplevel (os) (import-outside-toplevel)
services\risk_manager.py:9:0: W0611: Unused Dict imported from typing (unused-import)
services\risk_manager.py:9:0: W0611: Unused Optional imported from typing (unused-import)
services\risk_manager.py:9:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module services.runtime_mode
services\runtime_mode.py:20:4: W0603: Using the global statement (global-statement)
services\runtime_mode.py:29:4: W0603: Using the global statement (global-statement)
services\runtime_mode.py:38:4: W0603: Using the global statement (global-statement)
************* Module services.scheduler
services\scheduler.py:26:0: R0902: Too many instance attributes (9/7) (too-many-instance-attributes)
services\scheduler.py:86:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:93:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:128:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:142:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:172:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:148:12: C0415: Import outside toplevel (services.performance.PerformanceService) (import-outside-toplevel)
services\scheduler.py:170:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:158:16: C0415: Import outside toplevel (ws.manager.socket_app) (import-outside-toplevel)
services\scheduler.py:193:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:298:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:203:12: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\scheduler.py:204:12: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
services\scheduler.py:205:12: C0415: Import outside toplevel (services.prob_validation.validate_on_candles) (import-outside-toplevel)
services\scheduler.py:255:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:291:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:270:20: C0415: Import outside toplevel (time.time) (import-outside-toplevel)
services\scheduler.py:196:4: R0912: Too many branches (17/12) (too-many-branches)
services\scheduler.py:196:4: R0915: Too many statements (62/50) (too-many-statements)
services\scheduler.py:373:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:308:12: C0415: Import outside toplevel (os) (import-outside-toplevel)
services\scheduler.py:310:12: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\scheduler.py:311:12: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
services\scheduler.py:312:12: C0415: Import outside toplevel (services.prob_model.prob_model) (import-outside-toplevel)
services\scheduler.py:313:12: C0415: Import outside toplevel (services.prob_train.train_and_export) (import-outside-toplevel)
services\scheduler.py:337:12: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\scheduler.py:364:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:356:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:370:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:301:4: R0915: Too many statements (54/50) (too-many-statements)
services\scheduler.py:452:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:385:12: C0415: Import outside toplevel (services.strategy.update_settings_from_regime) (import-outside-toplevel)
services\scheduler.py:386:12: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
services\scheduler.py:407:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:397:16: C0415: Import outside toplevel (json) (import-outside-toplevel)
services\scheduler.py:398:16: C0415: Import outside toplevel (os) (import-outside-toplevel)
services\scheduler.py:447:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:418:16: C0415: Import outside toplevel (services.strategy.update_settings_from_regime_batch) (import-outside-toplevel)
services\scheduler.py:444:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\scheduler.py:428:24: C0415: Import outside toplevel (ws.manager.socket_app) (import-outside-toplevel)
services\scheduler.py:385:12: W0611: Unused update_settings_from_regime imported from services.strategy (unused-import)
services\scheduler.py:122:20: W0201: Attribute '_last_task_cleanup' defined outside __init__ (attribute-defined-outside-init)
services\scheduler.py:15:0: W0611: Unused timezone imported from datetime (unused-import)
services\scheduler.py:16:0: W0611: Unused List imported from typing (unused-import)
services\scheduler.py:16:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.signal_generator
services\signal_generator.py:22:0: R0902: Too many instance attributes (8/7) (too-many-instance-attributes)
services\signal_generator.py:122:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:166:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:161:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:191:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:186:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:236:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:266:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:244:12: C0415: Import outside toplevel (rest.routes.get_strategy_regime) (import-outside-toplevel)
services\signal_generator.py:299:8: R1705: Unnecessary "elif" after "return", remove the leading "el" from "elif" (no-else-return)
services\signal_generator.py:343:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:334:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:315:16: C0415: Import outside toplevel (services.ws_first_data_service.get_ws_first_data_service) (import-outside-toplevel)
services\signal_generator.py:320:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:364:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:355:12: R1705: Unnecessary "elif" after "return", remove the leading "el" from "elif" (no-else-return)
services\signal_generator.py:390:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:381:12: R1705: Unnecessary "elif" after "return", remove the leading "el" from "elif" (no-else-return)
services\signal_generator.py:408:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:401:12: R1705: Unnecessary "elif" after "return", remove the leading "el" from "elif" (no-else-return)
services\signal_generator.py:432:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:418:12: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
services\signal_generator.py:483:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:506:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:522:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:540:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_generator.py:2:0: W0611: Unused import logging (unused-import)
services\signal_generator.py:5:0: W0611: Unused Dict imported from typing (unused-import)
services\signal_generator.py:5:0: W0611: Unused List imported from typing (unused-import)
services\signal_generator.py:5:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.signal_service
services\signal_service.py:64:8: R1705: Unnecessary "elif" after "return", remove the leading "el" from "elif" (no-else-return)
services\signal_service.py:87:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_service.py:81:31: W0212: Access to a protected member _get_enhanced_signal of a client class (protected-access)
services\signal_service.py:110:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_service.py:126:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\signal_service.py:119:27: W0212: Access to a protected member _generate_signal_for_symbol of a client class (protected-access)
services\signal_service.py:135:12: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
services\signal_service.py:10:0: W0611: Unused import asyncio (unused-import)
services\signal_service.py:12:0: W0611: Unused Callable imported from typing (unused-import)
services\signal_service.py:12:0: W0611: Unused Dict imported from typing (unused-import)
services\signal_service.py:12:0: W0611: Unused List imported from typing (unused-import)
services\signal_service.py:12:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.strategy
services\strategy.py:466:0: C0301: Line too long (166/120) (line-too-long)
services\strategy.py:69:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:62:12: C0415: Import outside toplevel (services.strategy_settings.StrategySettingsService) (import-outside-toplevel)
services\strategy.py:164:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:144:8: C0415: Import outside toplevel (services.strategy_settings.StrategySettingsService) (import-outside-toplevel)
services\strategy.py:285:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:207:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:196:16: C0415: Import outside toplevel (services.prob_model.prob_model) (import-outside-toplevel)
services\strategy.py:259:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:214:20: C0415: Import outside toplevel (indicators.regime.detect_regime) (import-outside-toplevel)
services\strategy.py:215:20: C0415: Import outside toplevel (strategy.weights.PRESETS, strategy.weights.clamp_simplex) (import-outside-toplevel)
services\strategy.py:244:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:229:24: C0415: Import outside toplevel (json) (import-outside-toplevel)
services\strategy.py:230:24: W0404: Reimport 'os' (imported line 8) (reimported)
services\strategy.py:230:24: C0415: Import outside toplevel (os) (import-outside-toplevel)
services\strategy.py:239:33: C0201: Consider iterating the dictionary directly instead of calling .keys() (consider-iterating-dictionary)
services\strategy.py:283:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:108:0: R0912: Too many branches (26/12) (too-many-branches)
services\strategy.py:108:0: R0915: Too many statements (112/50) (too-many-statements)
services\strategy.py:475:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:323:8: C0415: Import outside toplevel (indicators.regime.detect_regime) (import-outside-toplevel)
services\strategy.py:324:8: C0415: Import outside toplevel (strategy.weights.PRESETS, strategy.weights.clamp_simplex) (import-outside-toplevel)
services\strategy.py:326:8: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\strategy.py:327:8: C0415: Import outside toplevel (services.strategy_settings.StrategySettingsService) (import-outside-toplevel)
services\strategy.py:347:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:335:12: C0415: Import outside toplevel (json) (import-outside-toplevel)
services\strategy.py:336:12: W0404: Reimport 'os' (imported line 8) (reimported)
services\strategy.py:336:12: C0415: Import outside toplevel (os) (import-outside-toplevel)
services\strategy.py:364:8: C0415: Import outside toplevel (asyncio) (import-outside-toplevel)
services\strategy.py:377:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:370:16: C0415: Import outside toplevel (concurrent.futures) (import-outside-toplevel)
services\strategy.py:428:8: C0415: Import outside toplevel (services.strategy_settings.StrategySettings) (import-outside-toplevel)
services\strategy.py:462:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:443:12: C0415: Import outside toplevel (json) (import-outside-toplevel)
services\strategy.py:444:12: W0404: Reimport 'os' (imported line 8) (reimported)
services\strategy.py:444:12: C0415: Import outside toplevel (os) (import-outside-toplevel)
services\strategy.py:312:0: R0915: Too many statements (68/50) (too-many-statements)
services\strategy.py:324:8: W0611: Unused clamp_simplex imported from strategy.weights (unused-import)
services\strategy.py:630:11: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:492:8: C0415: Import outside toplevel (asyncio) (import-outside-toplevel)
services\strategy.py:494:8: C0415: Import outside toplevel (indicators.regime.detect_regime) (import-outside-toplevel)
services\strategy.py:495:8: C0415: Import outside toplevel (strategy.weights.PRESETS, strategy.weights.clamp_simplex) (import-outside-toplevel)
services\strategy.py:497:8: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\strategy.py:498:8: C0415: Import outside toplevel (services.strategy_settings.StrategySettingsService) (import-outside-toplevel)
services\strategy.py:517:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:505:12: C0415: Import outside toplevel (json) (import-outside-toplevel)
services\strategy.py:506:12: W0404: Reimport 'os' (imported line 8) (reimported)
services\strategy.py:506:12: C0415: Import outside toplevel (os) (import-outside-toplevel)
services\strategy.py:552:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:545:16: C0415: Import outside toplevel (concurrent.futures) (import-outside-toplevel)
services\strategy.py:619:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy.py:610:16: E1101: Instance of 'StrategySettingsService' has no 'update_settings' member (no-member)
services\strategy.py:480:0: R0915: Too many statements (57/50) (too-many-statements)
services\strategy.py:619:12: W0612: Unused variable 'e' (unused-variable)
************* Module services.strategy_settings
services\strategy_settings.py:78:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy_settings.py:100:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy_settings.py:115:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\strategy_settings.py:12:0: W0611: Unused Dict imported from typing (unused-import)
services\strategy_settings.py:12:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.symbols
services\symbols.py:61:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\symbols.py:130:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\symbols.py:88:12: C0415: Import outside toplevel (time) (import-outside-toplevel)
services\symbols.py:110:16: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
services\symbols.py:158:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\symbols.py:192:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\symbols.py:16:0: W0611: Unused Dict imported from typing (unused-import)
services\symbols.py:16:0: W0611: Unused List imported from typing (unused-import)
services\symbols.py:16:0: W0611: Unused Optional imported from typing (unused-import)
services\symbols.py:16:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module services.templates
services\templates.py:34:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\templates.py:48:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\templates.py:71:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\templates.py:86:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\templates.py:9:0: W0611: Unused Dict imported from typing (unused-import)
services\templates.py:9:0: W0611: Unused List imported from typing (unused-import)
************* Module services.trade_counter
services\trade_counter.py:20:7: W0718: Catching too general exception Exception (broad-exception-caught)
services\trade_counter.py:21:4: C0103: Constant name "ZoneInfo" doesn't conform to UPPER_CASE naming style (invalid-name)
services\trade_counter.py:118:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trade_counter.py:114:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\trade_counter.py:133:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trade_counter.py:144:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trade_counter.py:155:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trade_counter.py:11:0: W0611: Unused Dict imported from typing (unused-import)
services\trade_counter.py:11:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.trading_integration
services\trading_integration.py:28:0: R0902: Too many instance attributes (8/7) (too-many-instance-attributes)
services\trading_integration.py:58:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:85:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:102:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:119:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:145:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:193:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:264:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:214:12: W0612: Unused variable 'current_price' (unused-variable)
services\trading_integration.py:365:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:308:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:341:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:353:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:286:12: W0612: Unused variable 'risk_level' (unused-variable)
services\trading_integration.py:417:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:445:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:470:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:510:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:559:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:575:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_integration.py:11:0: W0611: Unused Dict imported from typing (unused-import)
services\trading_integration.py:11:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.trading_service
services\trading_service.py:73:8: R1705: Unnecessary "elif" after "return", remove the leading "el" from "elif" (no-else-return)
services\trading_service.py:98:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_service.py:118:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_service.py:112:27: W0212: Access to a protected member_execute_enhanced_trade of a client class (protected-access)
services\trading_service.py:138:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_service.py:130:27: W0212: Access to a protected member _handle_ticker_with_strategy of a client class (protected-access)
services\trading_service.py:10:0: W0611: Unused import asyncio (unused-import)
services\trading_service.py:12:0: W0611: Unused Dict imported from typing (unused-import)
services\trading_service.py:12:0: W0611: Unused List imported from typing (unused-import)
services\trading_service.py:12:0: W0611: Unused Optional imported from typing (unused-import)
************* Module services.trading_window
services\trading_window.py:248:0: C0325: Unnecessary parens after 'not' keyword (superfluous-parens)
services\trading_window.py:20:7: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_window.py:21:4: C0103: Constant name "ZoneInfo" doesn't conform to UPPER_CASE naming style (invalid-name)
services\trading_window.py:70:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_window.py:98:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_window.py:219:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_window.py:229:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\trading_window.py:12:0: W0611: Unused Dict imported from typing (unused-import)
services\trading_window.py:12:0: W0611: Unused List imported from typing (unused-import)
services\trading_window.py:12:0: W0611: Unused Optional imported from typing (unused-import)
services\trading_window.py:12:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module services.ws_first_data_service
services\ws_first_data_service.py:35:0: R0902: Too many instance attributes (19/7) (too-many-instance-attributes)
services\ws_first_data_service.py:133:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:91:12: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
services\ws_first_data_service.py:102:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:120:27: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:130:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:244:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:195:22: E1136: Value 'last' is unsubscriptable (unsubscriptable-object)
services\ws_first_data_service.py:196:20: E1136: Value 'last' is unsubscriptable (unsubscriptable-object)
services\ws_first_data_service.py:197:20: E1136: Value 'last' is unsubscriptable (unsubscriptable-object)
services\ws_first_data_service.py:198:20: E1136: Value 'last' is unsubscriptable (unsubscriptable-object)
services\ws_first_data_service.py:199:26: E1136: Value 'last' is unsubscriptable (unsubscriptable-object)
services\ws_first_data_service.py:207:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:202:20: C0415: Import outside toplevel (services.strategy_settings.StrategySettingsService) (import-outside-toplevel)
services\ws_first_data_service.py:233:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:136:4: R0912: Too many branches (21/12) (too-many-branches)
services\ws_first_data_service.py:136:4: R0915: Too many statements (62/50) (too-many-statements)
services\ws_first_data_service.py:196:16: W0612: Unused variable 'o' (unused-variable)
services\ws_first_data_service.py:273:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:313:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:422:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:353:19: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:417:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:387:31: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:378:28: C0415: Import outside toplevel (services.strategy_settings.StrategySettingsService) (import-outside-toplevel)
services\ws_first_data_service.py:332:8: R1702: Too many nested blocks (6/5) (too-many-nested-blocks)
services\ws_first_data_service.py:332:8: R1702: Too many nested blocks (6/5) (too-many-nested-blocks)
services\ws_first_data_service.py:317:4: R0912: Too many branches (18/12) (too-many-branches)
services\ws_first_data_service.py:317:4: R0915: Too many statements (58/50) (too-many-statements)
services\ws_first_data_service.py:334:12: W0612: Unused variable 'cache_key' (unused-variable)
services\ws_first_data_service.py:332:8: R1702: Too many nested blocks (6/5) (too-many-nested-blocks)
services\ws_first_data_service.py:456:15: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:452:23: W0718: Catching too general exception Exception (broad-exception-caught)
services\ws_first_data_service.py:514:4: W0603: Using the global statement (global-statement)
services\ws_first_data_service.py:12:0: W0611: Unused datetime imported from datetime (unused-import)
services\ws_first_data_service.py:12:0: W0611: Unused timedelta imported from datetime (unused-import)
services\ws_first_data_service.py:13:0: W0611: Unused Callable imported from typing (unused-import)
services\ws_first_data_service.py:13:0: W0611: Unused Optional imported from typing (unused-import)
************* Module rest.active_orders
rest\active_orders.py:65:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\active_orders.py:108:8: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
rest\active_orders.py:250:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\active_orders.py:303:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\active_orders.py:299:24: W0612: Unused variable 'result' (unused-variable)
rest\active_orders.py:9:0: W0611: Unused Dict imported from typing (unused-import)
rest\active_orders.py:9:0: W0611: Unused List imported from typing (unused-import)
rest\active_orders.py:9:0: W0611: Unused Optional imported from typing (unused-import)
************* Module rest.auth
rest\auth.py:347:1: W0511: TODO: Implementera JWT autentiseringslogik f�r applikationen (fixme)
rest\auth.py:58:4: C0415: Import outside toplevel (utils.nonce_manager) (import-outside-toplevel)
rest\auth.py:261:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\auth.py:146:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\auth.py:152:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\auth.py:157:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\auth.py:181:12: C0415: Import outside toplevel (httpx) (import-outside-toplevel)
rest\auth.py:199:12: C0415: Import outside toplevel (asyncio) (import-outside-toplevel)
rest\auth.py:200:12: C0415: Import outside toplevel (random) (import-outside-toplevel)
rest\auth.py:202:12: C0415: Import outside toplevel (httpx) (import-outside-toplevel)
rest\auth.py:225:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\auth.py:227:20: R1724: Unnecessary "else" after "continue", remove the "else" and de-indent the code inside it (no-else-continue)
rest\auth.py:257:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\auth.py:253:16: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\auth.py:95:0: R0912: Too many branches (22/12) (too-many-branches)
rest\auth.py:95:0: R0915: Too many statements (98/50) (too-many-statements)
rest\auth.py:208:12: W0612: Unused variable 'last_exc' (unused-variable)
rest\auth.py:341:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\auth.py:299:8: C0415: Import outside toplevel (asyncio) (import-outside-toplevel)
rest\auth.py:300:8: C0415: Import outside toplevel (random) (import-outside-toplevel)
rest\auth.py:302:8: C0415: Import outside toplevel (httpx) (import-outside-toplevel)
rest\auth.py:318:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\auth.py:320:16: R1724: Unnecessary "else" after "continue", remove the "else" and de-indent the code inside it (no-else-continue)
rest\auth.py:308:8: W0612: Unused variable 'last_exc' (unused-variable)
rest\auth.py:13:0: W0611: Unused Optional imported from typing (unused-import)
************* Module rest.funding
rest\funding.py:65:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\funding.py:107:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\funding.py:11:0: W0611: Unused Dict imported from typing (unused-import)
rest\funding.py:11:0: W0611: Unused List imported from typing (unused-import)
rest\funding.py:11:0: W0611: Unused Optional imported from typing (unused-import)
************* Module rest.margin
rest\margin.py:118:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:181:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:169:31: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:223:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:260:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:372:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:327:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:322:16: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
rest\margin.py:347:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:332:16: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\margin.py:361:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:502:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:388:12: C0415: Import outside toplevel (time) (import-outside-toplevel)
rest\margin.py:403:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:398:20: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
rest\margin.py:442:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:420:16: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\margin.py:480:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:487:31: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:510:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\margin.py:376:4: R0912: Too many branches (18/12) (too-many-branches)
rest\margin.py:376:4: R0915: Too many statements (67/50) (too-many-statements)
rest\margin.py:8:0: W0611: Unused Dict imported from typing (unused-import)
rest\margin.py:8:0: W0611: Unused List imported from typing (unused-import)
rest\margin.py:8:0: W0611: Unused Optional imported from typing (unused-import)
************* Module rest.order_history
rest\order_history.py:93:0: C0301: Line too long (125/120) (line-too-long)
rest\order_history.py:183:0: C0301: Line too long (125/120) (line-too-long)
rest\order_history.py:103:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_history.py:190:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_history.py:217:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_history.py:179:4: R0912: Too many branches (15/12) (too-many-branches)
rest\order_history.py:360:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_history.py:301:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_history.py:329:39: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_history.py:315:36: C0415: Import outside toplevel (utils.nonce_manager.bump_nonce) (import-outside-toplevel)
rest\order_history.py:317:36: W0404: Reimport 'Settings' (imported line 22) (reimported)
rest\order_history.py:317:36: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
rest\order_history.py:351:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_history.py:356:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_history.py:381:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_history.py:255:4: R0912: Too many branches (19/12) (too-many-branches)
rest\order_history.py:255:4: R0915: Too many statements (77/50) (too-many-statements)
rest\order_history.py:558:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_history.py:13:0: W0611: Unused Dict imported from typing (unused-import)
rest\order_history.py:13:0: W0611: Unused List imported from typing (unused-import)
rest\order_history.py:13:0: W0611: Unused Optional imported from typing (unused-import)
************* Module rest.order_validator
rest\order_validator.py:13:7: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_validator.py:14:4: C0103: Constant name "BitfinexDocsScraper" doesn't conform to UPPER_CASE naming style (invalid-name)
rest\order_validator.py:56:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_validator.py:153:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_validator.py:145:12: C0415: Import outside toplevel (asyncio) (import-outside-toplevel)
rest\order_validator.py:147:12: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
rest\order_validator.py:233:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\order_validator.py:164:4: R0911: Too many return statements (10/6) (too-many-return-statements)
rest\order_validator.py:164:4: R0912: Too many branches (15/12) (too-many-branches)
rest\order_validator.py:67:8: W0201: Attribute 'order_types' defined outside __init__ (attribute-defined-outside-init)
rest\order_validator.py:157:8: W0201: Attribute 'symbols' defined outside __init__ (attribute-defined-outside-init)
rest\order_validator.py:158:8: W0201: Attribute 'symbol_names' defined outside __init__ (attribute-defined-outside-init)
rest\order_validator.py:161:8: W0201: Attribute 'paper_symbols' defined outside __init__ (attribute-defined-outside-init)
rest\order_validator.py:162:8: W0201: Attribute 'paper_symbol_names' defined outside __init__ (attribute-defined-outside-init)
rest\order_validator.py:9:0: W0611: Unused Dict imported from typing (unused-import)
rest\order_validator.py:9:0: W0611: Unused Optional imported from typing (unused-import)
rest\order_validator.py:9:0: W0611: Unused Tuple imported from typing (unused-import)
************* Module rest.positions
rest\positions.py:197:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\positions.py:97:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\positions.py:101:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\positions.py:129:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\positions.py:114:24: E1123: Unexpected keyword argument 'retry_after' in function call (unexpected-keyword-arg)
rest\positions.py:151:31: W0718: Catching too general exception Exception (broad-exception-caught)
rest\positions.py:149:39: W0718: Catching too general exception Exception (broad-exception-caught)
rest\positions.py:143:36: C0415: Import outside toplevel (utils.nonce_manager.bump_nonce) (import-outside-toplevel)
rest\positions.py:167:31: W0718: Catching too general exception Exception (broad-exception-caught)
rest\positions.py:176:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\positions.py:181:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\positions.py:77:4: R0912: Too many branches (19/12) (too-many-branches)
rest\positions.py:77:4: R0915: Too many statements (74/50) (too-many-statements)
rest\positions.py:285:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\positions.py:287:20: R1724: Unnecessary "else" after "continue", remove the "else" and de-indent the code inside it (no-else-continue)
rest\positions.py:288:24: W0404: Reimport 'asyncio' (imported line 8) (reimported)
rest\positions.py:288:24: C0415: Import outside toplevel (asyncio) (import-outside-toplevel)
rest\positions.py:289:24: C0415: Import outside toplevel (random) (import-outside-toplevel)
rest\positions.py:267:12: W0612: Unused variable 'last_exc' (unused-variable)
rest\positions.py:10:0: W0611: Unused Dict imported from typing (unused-import)
rest\positions.py:10:0: W0611: Unused List imported from typing (unused-import)
rest\positions.py:10:0: W0611: Unused Optional imported from typing (unused-import)
************* Module rest.positions_history
rest\positions_history.py:9:0: W0611: Unused Dict imported from typing (unused-import)
rest\positions_history.py:9:0: W0611: Unused List imported from typing (unused-import)
rest\positions_history.py:9:0: W0611: Unused Optional imported from typing (unused-import)
************* Module rest.routes
rest\routes.py:1:0: C0302: Too many lines in module (5276/1000) (too-many-lines)
rest\routes.py:85:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:77:8: C0415: Import outside toplevel (ws.manager.socket_app) (import-outside-toplevel)
rest\routes.py:220:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:290:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:276:16: C0415: Import outside toplevel (time.time) (import-outside-toplevel)
rest\routes.py:278:16: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:329:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:326:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:299:20: W0404: Reimport 'inc_labeled' (imported line 21) (reimported)
rest\routes.py:299:20: C0415: Import outside toplevel (services.metrics.inc_labeled) (import-outside-toplevel)
rest\routes.py:324:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:310:24: C0415: Import outside toplevel (time.time) (import-outside-toplevel)
rest\routes.py:312:24: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:332:8: C0415: Import outside toplevel (time) (import-outside-toplevel)
rest\routes.py:353:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:373:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:359:16: C0415: Import outside toplevel (time.time) (import-outside-toplevel)
rest\routes.py:361:16: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:401:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:391:12: W0404: Reimport 'Any' (imported line 10) (reimported)
rest\routes.py:391:12: C0415: Import outside toplevel (typing.Any) (import-outside-toplevel)
rest\routes.py:392:12: W0404: Reimport 'Dict' (imported line 10) (reimported)
rest\routes.py:392:12: C0415: Import outside toplevel (typing.Dict) (import-outside-toplevel)
rest\routes.py:462:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:405:12: W0404: Reimport 'inc_labeled' (imported line 21) (reimported)
rest\routes.py:405:12: C0415: Import outside toplevel (services.metrics.inc_labeled) (import-outside-toplevel)
rest\routes.py:460:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:441:16: C0415: Import outside toplevel (time.time) (import-outside-toplevel)
rest\routes.py:443:16: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:450:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:271:0: R0912: Too many branches (20/12) (too-many-branches)
rest\routes.py:271:0: R0915: Too many statements (95/50) (too-many-statements)
rest\routes.py:734:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:505:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:519:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:516:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:532:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:541:8: C0415: Import outside toplevel (os) (import-outside-toplevel)
rest\routes.py:568:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:557:12: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:585:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:577:16: W0404: Reimport 'SymbolService' (imported line 38) (reimported)
rest\routes.py:577:16: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
rest\routes.py:622:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:596:16: C0415: Import outside toplevel (os) (import-outside-toplevel)
rest\routes.py:608:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:619:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:688:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:627:16: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:627:16: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:640:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:653:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:661:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:658:24: C0415: Import outside toplevel (time) (import-outside-toplevel)
rest\routes.py:670:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:685:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:700:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:711:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:729:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:488:0: R0911: Too many return statements (11/6) (too-many-return-statements)
rest\routes.py:488:0: R0912: Too many branches (42/12) (too-many-branches)
rest\routes.py:488:0: R0915: Too many statements (146/50) (too-many-statements)
rest\routes.py:783:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:756:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:753:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:771:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:834:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:811:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:830:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:814:16: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:814:16: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:854:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:843:8: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:843:8: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:868:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:862:8: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:862:8: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:882:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:876:8: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:876:8: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:920:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:907:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:904:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:901:24: W0404: Reimport 'inc' (imported line 22) (reimported)
rest\routes.py:901:24: C0415: Import outside toplevel (services.metrics.inc) (import-outside-toplevel)
rest\routes.py:943:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1099:8: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
rest\routes.py:1278:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1349:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1365:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1404:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1399:8: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
rest\routes.py:1440:26: W0212: Access to a protected member_cache of a client class (protected-access)
rest\routes.py:1445:12: W0212: Access to a protected member _cache of a client class (protected-access)
rest\routes.py:1457:8: W0212: Access to a protected member_cache of a client class (protected-access)
rest\routes.py:1491:26: W0212: Access to a protected member _cache of a client class (protected-access)
rest\routes.py:1496:12: W0212: Access to a protected member_cache of a client class (protected-access)
rest\routes.py:1502:8: W0212: Access to a protected member _cache of a client class (protected-access)
rest\routes.py:1507:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1532:12: W0212: Access to a protected member _cache of a client class (protected-access)
rest\routes.py:1554:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1537:12: W0404: Reimport 'asyncio' (imported line 8) (reimported)
rest\routes.py:1537:12: C0415: Import outside toplevel (asyncio) (import-outside-toplevel)
rest\routes.py:1539:12: C0415: Import outside toplevel (ws.manager.socket_app) (import-outside-toplevel)
rest\routes.py:1559:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1571:8: C0415: Import outside toplevel (json) (import-outside-toplevel)
rest\routes.py:1572:8: C0415: Import outside toplevel (os) (import-outside-toplevel)
rest\routes.py:1581:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1590:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1596:8: C0415: Import outside toplevel (json) (import-outside-toplevel)
rest\routes.py:1597:8: C0415: Import outside toplevel (os) (import-outside-toplevel)
rest\routes.py:1607:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1626:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1662:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1656:16: W0404: Reimport 'Settings' (imported line 49) (reimported)
rest\routes.py:1656:16: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
rest\routes.py:1723:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1681:16: C0415: Import outside toplevel (re) (import-outside-toplevel)
rest\routes.py:1683:16: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:1683:16: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:1642:4: R1702: Too many nested blocks (7/5) (too-many-nested-blocks)
rest\routes.py:1712:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1745:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1758:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1750:20: W0404: Reimport 'candle_cache' (imported line 42) (reimported)
rest\routes.py:1750:20: C0415: Import outside toplevel (utils.candle_cache.candle_cache) (import-outside-toplevel)
rest\routes.py:1797:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:1825:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1641:0: R0912: Too many branches (39/12) (too-many-branches)
rest\routes.py:1641:0: R0915: Too many statements (122/50) (too-many-statements)
rest\routes.py:1838:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1863:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1885:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1901:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1905:32: W0622: Redefining built-in 'format' (redefined-builtin)
rest\routes.py:1917:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1921:31: W0622: Redefining built-in 'format' (redefined-builtin)
rest\routes.py:1964:8: C0415: Import outside toplevel (services.strategy.evaluate_strategy) (import-outside-toplevel)
rest\routes.py:1978:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:1986:51: W0212: Access to a protected member_handle_ticker_with_strategy of a client class (protected-access)
rest\routes.py:1993:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:2000:8: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:2000:8: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:2011:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:2017:8: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:2017:8: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:2022:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:2030:8: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:2030:8: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:2033:52: W0212: Access to a protected member_handle_ticker_with_strategy of a client class (protected-access)
rest\routes.py:2036:52: W0212: Access to a protected member_handle_ticker_with_strategy of a client class (protected-access)
rest\routes.py:2040:57: W0212: Access to a protected member_handle_ticker_with_strategy of a client class (protected-access)
rest\routes.py:2049:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:2055:8: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:2055:8: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:2075:8: W0707: Consider explicitly re-raising using 'raise HTTPException(status_code=500, detail=str(e)) from e' (raise-missing-from)
rest\routes.py:2081:8: C0415: Import outside toplevel (time) (import-outside-toplevel)
rest\routes.py:2110:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2117:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2129:8: W0404: Reimport 'Settings' (imported line 49) (reimported)
rest\routes.py:2129:8: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
rest\routes.py:2196:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2239:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2215:12: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:2217:12: W0404: Reimport 'Settings' (imported line 49) (reimported)
rest\routes.py:2217:12: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
rest\routes.py:2079:0: R0915: Too many statements (75/50) (too-many-statements)
rest\routes.py:2250:8: W0404: Reimport 'Settings' (imported line 49) (reimported)
rest\routes.py:2250:8: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
rest\routes.py:2316:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2384:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2370:16: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:2393:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2387:12: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:2332:0: R0912: Too many branches (13/12) (too-many-branches)
rest\routes.py:2412:8: C0415: Import outside toplevel (os) (import-outside-toplevel)
rest\routes.py:2414:8: C0415: Import outside toplevel (services.prob_train.train_and_export) (import-outside-toplevel)
rest\routes.py:2415:8: W0404: Reimport 'SymbolService' (imported line 38) (reimported)
rest\routes.py:2415:8: C0415: Import outside toplevel (services.symbols.SymbolService) (import-outside-toplevel)
rest\routes.py:2452:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2449:16: C0415: Import outside toplevel (re) (import-outside-toplevel)
rest\routes.py:2465:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2538:8: C0415: Import outside toplevel (os) (import-outside-toplevel)
rest\routes.py:2548:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2588:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2536:0: R0912: Too many branches (21/12) (too-many-branches)
rest\routes.py:2536:0: R0915: Too many statements (51/50) (too-many-statements)
rest\routes.py:2600:8: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:2612:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2622:50: W0622: Redefining built-in 'format' (redefined-builtin)
rest\routes.py:2628:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2638:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2660:26: W0212: Access to a protected member_cache of a client class (protected-access)
rest\routes.py:2662:29: W1309: Using an f-string that does not have any interpolated variables (f-string-without-interpolation)
rest\routes.py:2665:12: W0212: Access to a protected member _cache of a client class (protected-access)
rest\routes.py:2672:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2686:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2679:16: W0404: Reimport 'Settings' (imported line 49) (reimported)
rest\routes.py:2679:16: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
rest\routes.py:2693:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2701:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2698:12: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:2698:12: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:2705:8: C0415: Import outside toplevel (services.ws_first_data_service.get_ws_first_data_service) (import-outside-toplevel)
rest\routes.py:2710:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2734:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2779:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2748:12: W0404: Reimport 'MarginService' (imported line 53) (reimported)
rest\routes.py:2748:12: C0415: Import outside toplevel (rest.margin.MarginService) (import-outside-toplevel)
rest\routes.py:2776:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2764:20: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:2764:20: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:2788:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2798:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2793:16: W0404: Reimport 'Settings' (imported line 49) (reimported)
rest\routes.py:2793:16: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
rest\routes.py:2830:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2834:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2838:16: C0415: Import outside toplevel (services.strategy.evaluate_strategy) (import-outside-toplevel)
rest\routes.py:2847:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2852:16: C0415: Import outside toplevel (services.strategy.evaluate_strategy) (import-outside-toplevel)
rest\routes.py:2861:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2933:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2886:20: W0404: Reimport 'BitfinexDataService' (imported line 18) (reimported)
rest\routes.py:2886:20: C0415: Import outside toplevel (services.bitfinex_data.BitfinexDataService) (import-outside-toplevel)
rest\routes.py:2887:20: W0404: Reimport 'prob_model' (imported line 25) (reimported)
rest\routes.py:2887:20: C0415: Import outside toplevel (services.prob_model.prob_model) (import-outside-toplevel)
rest\routes.py:2908:31: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:2916:24: W0404: Reimport 'Settings' (imported line 49) (reimported)
rest\routes.py:2916:24: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
rest\routes.py:2940:8: W0212: Access to a protected member _cache of a client class (protected-access)
rest\routes.py:2649:0: R0912: Too many branches (38/12) (too-many-branches)
rest\routes.py:2649:0: R0915: Too many statements (185/50) (too-many-statements)
rest\routes.py:2740:8: W0612: Unused variable 'all_results' (unused-variable)
rest\routes.py:2767:20: W0612: Unused variable 'calc_results' (unused-variable)
rest\routes.py:3035:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3193:11: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3063:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3060:27: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3057:24: W0404: Reimport 'inc' (imported line 22) (reimported)
rest\routes.py:3057:24: C0415: Import outside toplevel (services.metrics.inc) (import-outside-toplevel)
rest\routes.py:3080:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3110:19: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3105:16: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:3105:16: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:3138:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3133:20: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:3133:20: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:3162:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3157:20: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:3157:20: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:3190:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3183:16: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:3047:0: R0911: Too many return statements (10/6) (too-many-return-statements)
rest\routes.py:3047:0: R0912: Too many branches (28/12) (too-many-branches)
rest\routes.py:3047:0: R0915: Too many statements (87/50) (too-many-statements)
rest\routes.py:3271:23: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3447:8: C0415: Import outside toplevel (services.risk_guards.risk_guards) (import-outside-toplevel)
rest\routes.py:3460:8: C0415: Import outside toplevel (services.risk_guards.risk_guards) (import-outside-toplevel)
rest\routes.py:3463:8: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
rest\routes.py:3481:8: C0415: Import outside toplevel (services.risk_guards.risk_guards) (import-outside-toplevel)
rest\routes.py:3484:8: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
rest\routes.py:3497:0: E0102: class already defined line 2949 (function-redefined)
rest\routes.py:3510:8: C0415: Import outside toplevel (services.cost_aware_backtest.TradeCosts, services.cost_aware_backtest.cost_aware_backtest) (import-outside-toplevel)
rest\routes.py:3573:8: C0415: Import outside toplevel (services.cost_aware_backtest.TradeCosts) (import-outside-toplevel)
rest\routes.py:3602:8: C0415: Import outside toplevel (services.regime_ablation.regime_ablation) (import-outside-toplevel)
rest\routes.py:3615:8: C0415: Import outside toplevel (services.regime_ablation.regime_ablation) (import-outside-toplevel)
rest\routes.py:3618:8: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
rest\routes.py:3634:8: C0415: Import outside toplevel (services.regime_ablation.regime_ablation) (import-outside-toplevel)
rest\routes.py:3637:8: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
rest\routes.py:3654:8: C0415: Import outside toplevel (services.regime_ablation.regime_ablation) (import-outside-toplevel)
rest\routes.py:3667:8: C0415: Import outside toplevel (services.regime_ablation.regime_ablation) (import-outside-toplevel)
rest\routes.py:3682:8: C0415: Import outside toplevel (services.health_watchdog.health_watchdog) (import-outside-toplevel)
rest\routes.py:3695:8: C0415: Import outside toplevel (services.health_watchdog.health_watchdog) (import-outside-toplevel)
rest\routes.py:3708:8: C0415: Import outside toplevel (services.health_watchdog.health_watchdog) (import-outside-toplevel)
rest\routes.py:3724:8: C0415: Import outside toplevel (services.health_watchdog.health_watchdog) (import-outside-toplevel)
rest\routes.py:3726:8: R1705: Unnecessary "else" after "return", remove the "else" and de-indent the code inside it (no-else-return)
rest\routes.py:3740:8: C0415: Import outside toplevel (services.health_watchdog.health_watchdog) (import-outside-toplevel)
rest\routes.py:3754:8: C0415: Import outside toplevel (utils.json_optimizer.json_optimizer) (import-outside-toplevel)
rest\routes.py:3767:8: C0415: Import outside toplevel (utils.json_optimizer.json_optimizer) (import-outside-toplevel)
rest\routes.py:3785:8: C0415: Import outside toplevel (utils.json_optimizer.benchmark_json_parsing) (import-outside-toplevel)
rest\routes.py:3824:16: C0415: Import outside toplevel (os) (import-outside-toplevel)
rest\routes.py:3848:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3832:12: W0404: Reimport 'bitfinex_ws' (imported line 19) (reimported)
rest\routes.py:3832:12: C0415: Import outside toplevel (services.bitfinex_websocket.bitfinex_ws) (import-outside-toplevel)
rest\routes.py:3833:12: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:3860:15: W0718: Catching too general exception Exception (broad-exception-caught)
rest\routes.py:3853:12: C0415: Import outside toplevel (services.metrics.metrics_store) (import-outside-toplevel)
rest\routes.py:3857:16: C0415: Import outside toplevel (json) (import-outside-toplevel)
rest\routes.py:3871:8: C0415: Import outside toplevel (fastapi.responses.JSONResponse) (import-outside-toplevel)
rest\routes.py:3883:8: W0404: Reimport 'get_metrics_summary' (imported line 21) (reimported)
rest\routes.py:3883:8: C0415: Import outside toplevel (services.metrics.get_metrics_summary) (import-outside-toplevel)
rest\routes.py:3885:8: W0404: Reimport 'Settings' (imported line 49) (reimported)
rest\routes.py:3885:8: C0415: Import outside toplevel (config.settings.Settings) (import-outside-toplevel)
rest\routes.py:3918:8: W0404: Reimport 'Settings' (imported line 49) (reimported)
rest\routes.py:3918:8:
