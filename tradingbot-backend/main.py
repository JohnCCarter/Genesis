"""
TradingBot Backend - Huvudapplikation

Denna fil innehåller huvudapplikationen för tradingbot-backend med FastAPI och
Socket.IO. Hanterar startup, shutdown och routing till olika moduler.
"""

import importlib
import sys as _sys
import asyncio as _asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import fastapi as _fastapi
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Initialize logger early to catch startup errors
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    from config.settings import settings
except Exception as e:
    logger.error(f"❌ Critical startup error - cannot import Settings: {e}")
    logger.error("This error will also appear in uvicorn.out.txt")
    raise

try:
    from ws.manager import socket_app
except Exception as e:
    logger.error(f"❌ Critical startup error - cannot import socket_app: {e}")
    raise

try:
    # MCP routes removed - MCP functionality disabled
    # from rest.mcp_routes import router as mcp_router  # type: ignore
    mcp_router = None  # type: ignore
except Exception:
    mcp_router = None  # type: ignore

trading_service: Any = None
try:
    from rest.routes import router as rest_router
    from rest.debug_routes import router as debug_router
    from services.bitfinex_websocket import bitfinex_ws
    from services.metrics_client import get_metrics_client
    from services.metrics import get_metrics_summary
    from utils.feature_flags import is_ws_connect_on_start
    from services.signal_service import signal_service

    try:
        from services.trading_service import trading_service as _trading_service  # type: ignore

        trading_service = _trading_service
    except Exception:
        trading_service = None
    # Importera WS bridge-events (subscribe/unsubscribe/pool_status)
    import ws.subscription_events  # noqa: F401
except Exception as e:
    logger.error(f"❌ Critical startup error - cannot import core modules: {e}")
    raise

# Kommenterar ut för att undvika cirkulära imports
# from tests.test_backend_order import test_backend_limit_order

# Windows event loop policy: avoid Proactor issues with websockets
try:
    if _sys.platform.startswith("win"):
        _asyncio.set_event_loop_policy(_asyncio.WindowsSelectorEventLoopPolicy())
except Exception:
    pass

# Asyncio debug support
try:
    if getattr(settings, "DEBUG_ASYNC", False):
        _asyncio.get_event_loop().set_debug(True)
        _asyncio.get_event_loop().slow_callback_duration = 0.05  # Log callbacks > 50ms
        logger.info("🔍 Asyncio debug aktiverat")
except Exception as e:
    logger.warning(f"⚠️ Could not configure asyncio debug: {e}")

# WS_CONNECT_ON_START hanteras via FeatureFlagsService; env fallback sker i utils/feature_flags


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hanterar startup och shutdown för applikationen."""
    # Startup
    logger.info("🚀 TradingBot Backend startar...")

    # Starta Bitfinex WebSocket-anslutning endast om flagga är på
    try:
        if bool(is_ws_connect_on_start()):
            import time as _t

            _t0 = _t.perf_counter()
            try:
                await _asyncio.wait_for(bitfinex_ws.connect(), timeout=5.0)
                _t1 = _t.perf_counter()
                logger.info("✅ WebSocket-anslutning etablerad (%.0f ms)", (_t1 - _t0) * 1000)

                # Koppla WebSocket service till enhetliga services (guarded)
                try:
                    fn = getattr(signal_service, "set_websocket_service", None)
                    if callable(fn):
                        fn(bitfinex_ws)
                except Exception:
                    pass
                try:
                    fn2 = getattr(trading_service, "set_websocket_service", None)
                    if callable(fn2):
                        fn2(bitfinex_ws)
                except Exception:
                    pass
                logger.info("🔗 Enhetliga services kopplade till WebSocket")

                # WS‑auth direkt om nycklar finns så att privata flöden fungerar
                try:
                    _ta = _t.perf_counter()
                    await _asyncio.wait_for(bitfinex_ws.ensure_authenticated(), timeout=3.0)
                    _tb = _t.perf_counter()
                    logger.info("🔐 WS‑auth klar (%.0f ms)", (_tb - _ta) * 1000)
                except TimeoutError:
                    logger.warning("⚠️ WS‑auth timeout – fortsätter utan auth vid startup")
                except Exception as e:
                    logger.warning(f"⚠️ WS‑auth misslyckades: {e}")
            except TimeoutError:
                logger.warning("⚠️ WS‑connect timeout – hoppar över WS vid startup")
            except Exception as e:
                logger.warning(f"⚠️ WebSocket-anslutning misslyckades: {e}")
        else:
            logger.info("WS‑connect vid start är AV. Kan startas via WS‑test sidan eller API.")
    except Exception as e:
        logger.warning(f"⚠️ WebSocket-anslutning block misslyckades: {e}")

    # Aktivera komponenter baserat på miljövariabler
    try:
        from config.startup_config import (
            enable_components_on_startup,
            log_startup_status,
        )

        enable_components_on_startup()
        log_startup_status()
    except Exception as e:
        logger.warning(f"⚠️ Kunde inte aktivera komponenter vid startup: {e}")

    # Starta scheduler om aktiverat
    try:
        from services.scheduler import scheduler
        from utils.feature_flags import is_scheduler_enabled

        if is_scheduler_enabled():
            scheduler.start()
            logger.info("🗓️ Scheduler startad")
        else:
            logger.info("🚫 Scheduler inaktiverat (aktivera med ENABLE_SCHEDULER=true eller DEV_MODE=true)")
    except Exception as e:
        logger.warning(f"⚠️ Kunde inte starta scheduler: {e}")

    # Starta circuit breaker recovery service
    try:
        from services.circuit_breaker_recovery import get_circuit_breaker_recovery

        recovery_service = get_circuit_breaker_recovery()
        await recovery_service.start()
        logger.info("🔄 Circuit breaker recovery service startad")
    except Exception as e:
        logger.warning(f"⚠️ Kunde inte starta circuit breaker recovery: {e}")

    yield

    # Shutdown
    logger.info("🛑 TradingBot Backend stängs av...")

    # Stäng WebSocket-anslutning
    try:
        await bitfinex_ws.disconnect()
        logger.info("✅ WebSocket-anslutning stängd")
    except Exception as e:
        logger.warning(f"⚠️ Fel vid stängning av WebSocket: {e}")

    # Stoppa scheduler om den körs
    try:
        from services.scheduler import scheduler

        await scheduler.stop()
        logger.info("✅ Scheduler stoppad")
    except Exception as e:
        logger.warning(f"⚠️ Fel vid stopp av scheduler: {e}")

    # Stoppa circuit breaker recovery service
    try:
        from services.circuit_breaker_recovery import get_circuit_breaker_recovery

        recovery_service = get_circuit_breaker_recovery()
        await recovery_service.stop()
        logger.info("✅ Circuit breaker recovery service stoppad")
    except Exception as e:
        logger.warning(f"⚠️ Fel vid stopp av circuit breaker recovery: {e}")

    # Stäng delade HTTP-klienter via helper (per event loop)
    try:
        from services.http import close_http_clients

        await close_http_clients()
        logger.info("✅ Delade async HTTP‑klienter stängda")
    except Exception as e:
        logger.warning(f"⚠️ Fel vid stängning av HTTP‑klienter: {e}")

    # Rensa alla aktiva tasks
    try:
        import asyncio

        all_tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        if all_tasks:
            logger.info(f"🔄 Avbryter {len(all_tasks)} aktiva tasks...")
            for task in all_tasks:
                task.cancel()

            # Vänta på att tasks avslutas (max 3 sekunder)
            try:
                await asyncio.wait_for(asyncio.gather(*all_tasks, return_exceptions=True), timeout=3.0)
                logger.info("✅ Alla tasks avbrutna")
            except TimeoutError:
                logger.warning("⚠️ Timeout vid avbrytning av tasks - fortsätter shutdown")
    except Exception as e:
        logger.warning(f"⚠️ Fel vid task cleanup: {e}")

    # Stäng HTTP-klienter via facade (respektera WS-first design)
    try:
        from services.market_data_facade import get_market_data

        facade = get_market_data()
        # Om underliggande REST-klient existerar, stäng den säkert
        rest = getattr(facade.ws_first, "rest_service", None)
        client = getattr(rest, "_client", None)
        if client is not None:
            await client.aclose()
            logger.info("✅ HTTP-klient stängd (via MarketDataFacade)")
    except Exception as e:
        logger.warning(f"⚠️ Fel vid stängning av HTTP-klient (via facade): {e}")

    logger.info("✅ Shutdown komplett")


# Skapa FastAPI-applikation


# Skapa FastAPI-applikation – loggning före app-instans för tydlighet
try:
    pass
except Exception as e:
    logger.error(f"❌ Critical startup error - cannot create Settings instance: {e}")
    raise

logger.info("🔑 Kontroll vid startup:")
logger.info(
    "    BITFINEX_API_KEY: %s",
    "✅" if settings.BITFINEX_API_KEY else "❌",
)
logger.info(
    "    API_SECRET status: %s",
    "✅" if settings.BITFINEX_API_SECRET else "❌",
)

app = FastAPI(
    title="TradingBot Backend",
    description="Skalbar tradingbot-backend med FastAPI och Socket.IO",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS middleware
try:
    import json as _json

    _raw_origins = getattr(settings, "ALLOWED_ORIGINS", "[]")
    if isinstance(_raw_origins, str):
        try:
            _origins = _json.loads(_raw_origins)
        except Exception:
            _origins = [_raw_origins]
    else:
        _origins = list(_raw_origins) if _raw_origins else []
    if not _origins:
        _origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
except Exception:
    _origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mitigera DoS-relaterade risker i multipart/stora svar
app.add_middleware(GZipMiddleware, minimum_size=1024)


# HTTP-protokollfelhantering middleware
@app.middleware("http")
async def http_protocol_error_handler(request: Request, call_next):
    """Hantera HTTP-protokollfel och connection errors gracefully."""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        # Logga HTTP-protokollfel utan att krascha applikationen
        error_msg = str(e)
        if "ConnectionClosed" in error_msg or "LocalProtocolError" in error_msg:
            logger.warning(f"⚠️ HTTP-protokollfel hanterat: {error_msg}")
            return Response(status_code=499, content="Connection closed by client")  # Client Closed Request
        elif "timeout" in error_msg.lower():
            logger.warning(f"⚠️ HTTP-timeout hanterat: {error_msg}")
            return Response(status_code=504, content="Request timeout")  # Gateway Timeout
        else:
            # Logga andra fel men låt dem propagera
            logger.error(f"❌ Ohanterat HTTP-fel: {error_msg}")
            raise


# Förbättrad uvicorn-konfiguration för att minska HTTP-protokollfel
@app.on_event("startup")
async def startup_event():
    """Startup event för att konfigurera servern."""
    try:
        host = getattr(settings, "HOST", "127.0.0.1")
        port = getattr(settings, "PORT", 8000)
    except Exception:
        host = "127.0.0.1"
        port = 8000
    logger.info("🚀 Genesis Trading Bot Backend startar...")
    logger.info(f"📡 Server körs på http://{host}:{port}")
    logger.info("🔧 HTTP-protokollfelhantering aktiverad")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event för att stänga servern gracefully."""
    logger.info("🛑 Genesis Trading Bot Backend stänger...")


# Enkel RequestGuard: blockera multipart och cap Content-Length
@app.middleware("http")
async def request_guard(request: Request, call_next):
    try:
        # Blockera multipart/form-data helt (kan öppnas vid behov via vitlista)
        ctype = request.headers.get("content-type", "").lower()
        if "multipart/form-data" in ctype:
            return Response(status_code=413)

        # Cap Content-Length (t.ex. 2 MB)
        try:
            clen = int(request.headers.get("content-length", "0"))
        except Exception:
            clen = 0
        if clen and clen > 2 * 1024 * 1024:
            return Response(status_code=413)
    except Exception:
        # Falla tillbaka till normal hantering
        pass
    return await call_next(request)


# Inkludera REST endpoints
app.include_router(rest_router)
app.include_router(debug_router)

# MCP kan stängas av via settings
try:
    # MCP functionality disabled
    # if getattr(settings, "MCP_ENABLED", False) and mcp_router is not None:
    #     app.include_router(mcp_router)
    #     logger.info("MCP routes aktiverade")
    # else:
    logger.info("MCP routes avstängda")
except Exception:
    logger.info("MCP routes avstängda")

# --- Lokala Swagger‑assets för /docs (undvik CDN‑beroende) ---
try:
    import os as _os

    _FASTAPI_STATIC = _os.path.join(_os.path.dirname(_fastapi.__file__), "static")
    # Montera under egen path för att inte krocka
    app.mount("/_docs_static", StaticFiles(directory=_FASTAPI_STATIC), name="_docs_static")

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="TradingBot API Docs",
            swagger_js_url="/_docs_static/swagger-ui-bundle.js",
            swagger_css_url="/_docs_static/swagger-ui.css",
            swagger_favicon_url="/_docs_static/favicon.png",
        )

    @app.get("/docs/oauth2-redirect", include_in_schema=False)
    async def swagger_ui_redirect():
        return get_swagger_ui_oauth2_redirect_html()

except Exception as _e:
    logger.warning(f"Kunde inte konfigurera lokala Swagger-assets: {_e}")

# OBS: Socket.IO hanteras via toppnivå-wrapper längre ned


@app.get("/")
async def root():
    """Root endpoint för API."""
    return {
        "message": "TradingBot Backend API",
        "version": "1.0.0",
        "endpoints": {
            "strategy": "/api/v2/strategy/evaluate",
            "order": "/api/v2/order",
            "websocket": "/ws",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/time")
async def server_time():
    """Returnerar serverns tid för NTP-synkronisering."""
    import time

    return {"timestamp": int(time.time()), "timezone": time.tzname}


# Alternativ test-sida för Socket.IO (undviker 307->/ws/ som kan ge 404)
# Statisk montering för nya UI-sidor
# Montera statiska sidor från ../frontend
_BASE_DIR = os.path.dirname(__file__)
_FRONTEND_DIR = os.path.abspath(os.path.join(_BASE_DIR, "..", "frontend"))
# ws-test directory removed
# _WS_TEST_DIR = os.path.join(_FRONTEND_DIR, "ws-test")
# risk-panel and shared directories removed
# _RISK_PANEL_DIR = os.path.join(_FRONTEND_DIR, "risk-panel")
# _SHARED_DIR = os.path.join(_FRONTEND_DIR, "shared")
# ws-test directory removed
# app.mount("/ws-test", StaticFiles(directory=_WS_TEST_DIR, html=True), name="ws-test")
# app.mount("/risk-panel", StaticFiles(directory=_RISK_PANEL_DIR, html=True), name="risk-panel")
# app.mount("/shared", StaticFiles(directory=_SHARED_DIR, html=False), name="shared")


@app.get("/prob-test")
async def prob_test_page() -> FileResponse:
    """Probability test page - endast en endpoint för prob-testing"""
    import os

    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "prob_test.html")
    return FileResponse(path)


@app.get("/metrics")
async def metrics(request: Request) -> Response:
    """Prometheus metrics (root) med valfritt skydd via miljövariabler.

    Mekanismer (någon räcker):
    - METRICS_ACCESS_TOKEN: Bearer-token eller query-param ?token
    - METRICS_BASIC_AUTH_USER/PASS: HTTP Basic Auth
    - METRICS_IP_ALLOWLIST: kommaseparerad lista av tillåtna IP

    Om ingen är satt: endpointen är publik (för tester/bakåtkompatibilitet).
    """

    # Läs settings vid request-time så test kan styra via env
    import base64
    import hmac

    # Läs direkt från processens miljö (inte via Settings/.env) för att
    # möjliggöra testernas monkeypatch av env-variabler.
    import os as _os

    ip_allowlist_raw = (_os.getenv("METRICS_IP_ALLOWLIST", "") or "").strip()
    basic_user = _os.getenv("METRICS_BASIC_AUTH_USER")
    basic_pass = _os.getenv("METRICS_BASIC_AUTH_PASS")
    access_token = _os.getenv("METRICS_ACCESS_TOKEN")

    restrictions_configured = bool(ip_allowlist_raw or (basic_user and basic_pass) or access_token)

    if restrictions_configured:
        client_ip = None
        try:
            client_ip = request.client.host if request.client else None
        except Exception:
            client_ip = None

        allowed = False

        # 1) IP allowlist
        if ip_allowlist_raw and client_ip:
            allowed_ips = {ip.strip() for ip in ip_allowlist_raw.split(",") if ip.strip()}
            if client_ip in allowed_ips:
                allowed = True

        # 2) Bearer token eller query-param token
        if not allowed and access_token:
            auth_header = request.headers.get(
                "authorization",
                "",
            )
            bearer_token = None
            if auth_header.lower().startswith("bearer "):
                bearer_token = auth_header.split(" ", 1)[1].strip()
            query_token = request.query_params.get("token")
            token_match = False
            if query_token:
                token_match = hmac.compare_digest(
                    str(query_token),
                    str(access_token),
                )
            if not token_match and bearer_token:
                token_match = hmac.compare_digest(
                    str(bearer_token),
                    str(access_token),
                )
            if token_match:
                allowed = True

        # 3) Basic auth
        if not allowed and basic_user and basic_pass:
            auth_header = request.headers.get(
                "authorization",
                "",
            )
            if auth_header.lower().startswith("basic "):
                b64 = auth_header.split(" ", 1)[1].strip()
                try:
                    decoded = base64.b64decode(b64).decode("utf-8")
                    username, password = decoded.split(":", 1)
                    if hmac.compare_digest(username, str(basic_user)) and hmac.compare_digest(
                        password, str(basic_pass)
                    ):
                        allowed = True
                except Exception:
                    pass

        if not allowed:
            # 401 om Basic Auth är konfigurerat, annars 403
            status_code = 401 if (basic_user and basic_pass) else 403
            return Response(status_code=status_code)

    # Uppdatera dynamiska metrics (best effort)
    try:
        from utils.advanced_rate_limiter import get_advanced_rate_limiter
        from services.market_data_facade import get_market_data

        # Exportera limiter-stats
        get_advanced_rate_limiter().export_metrics()
        # Pinga market data stats (kan uppdatera cache/metrics)
        _ = get_market_data().stats()
    except Exception:
        pass

    txt = get_metrics_client().render_prometheus_text()
    return Response(
        content=txt,
        media_type="text/plain; version=0.0.4",
    )


@app.get("/metrics/summary")
async def metrics_summary(_: Request) -> dict:
    """JSON-sammanfattning av nyckelmetrik (latency, errors) för snabb hälsokontroll."""
    try:
        # Uppdatera limiter-stats innan summering
        from utils.advanced_rate_limiter import get_advanced_rate_limiter

        get_advanced_rate_limiter().export_metrics()
    except Exception:
        pass
    return get_metrics_summary()


# Förbättrad ASGI-middleware för latens och prestanda-monitoring
@app.middleware("http")
async def latency_middleware(request: Request, call_next):
    import time

    start = time.perf_counter()

    try:
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)

        # Logga långsamma requests (>500ms)
        if duration_ms > 500:
            logger.warning(
                "🐌 Långsam request: %s %s - %dms (status: %d)",
                request.method,
                request.url.path,
                duration_ms,
                getattr(response, "status_code", 0),
            )

        # Logga mycket långsamma requests (>2000ms) som potentiella hängningar
        if duration_ms > 2000:
            logger.error(
                "🚨 POTENTIELL HÄNGNING: %s %s - %dms (status: %d)",
                request.method,
                request.url.path,
                duration_ms,
                getattr(response, "status_code", 0),
            )

        try:
            # path-template fås enklast via scope/route (kan vara None i root-asgi)
            path_template = getattr(
                getattr(request, "scope", {}),
                "get",
                lambda *_: None,
            )("path")
            # Försök att hämta route.path_params/template från
            # request.scope["route"].path
            route = request.scope.get("route")
            if route is not None:
                path_template = getattr(route, "path", path_template)
            # AI Change: use MetricsClient.observe_latency (Agent: Codex, Date: 2025-09-11)
            from services.metrics_client import get_metrics_client

            get_metrics_client().observe_latency(
                path=path_template or request.url.path,
                method=request.method,
                status_code=getattr(response, "status_code", 0),
                duration_ms=duration_ms,
            )
        except Exception:
            pass
        return response

    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(
            "❌ Request failed: %s %s - %dms - %s",
            request.method,
            request.url.path,
            duration_ms,
            str(e),
        )
        raise


# Wrappar alltid Socket.IO UI
_socketio = importlib.import_module("socketio")
app = _socketio.ASGIApp(
    socket_app,
    other_asgi_app=app,
    socketio_path="/ws/socket.io",
)
logger.info("Socket.IO UI aktiverad")

if __name__ == "__main__":
    import asyncio
    import signal
    import sys

    def signal_handler(signum, _frame):
        """Hantera shutdown-signaler."""
        logger.info(f"📡 Mottog signal {signum}, startar shutdown...")
        # Stoppa event loop om den körs
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.stop()
        except Exception:
            pass
        sys.exit(0)

    # Registrera signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Terminate

    try:
        uvicorn.run(
            "main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=True,
            log_level="info",
            timeout_keep_alive=15,  # 15s keep-alive timeout (minskat från 30s)
            timeout_graceful_shutdown=5,  # 5s graceful shutdown (minskat från 10s)
            limit_max_requests=500,  # Begränsa antal requests per worker (minskat från 1000)
            limit_concurrency=100,  # Begränsa samtidiga anslutningar
            backlog=50,  # Begränsa backlog för nya anslutningar
        )
    except Exception as e:
        logger.error(f"❌ Kritiskt startfel - kan inte starta uvicorn: {e}", exc_info=True)
        raise
