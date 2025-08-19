"""
TradingBot Backend - Huvudapplikation

Denna fil innehåller huvudapplikationen för tradingbot-backend med FastAPI och
Socket.IO. Hanterar startup, shutdown och routing till olika moduler.
"""

import importlib
import os
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.settings import Settings
from rest.routes import router as rest_router
from services.bitfinex_websocket import bitfinex_ws
from services.metrics import observe_latency, render_prometheus_text
from services.runtime_mode import get_validation_on_start, get_ws_connect_on_start
from utils.logger import get_logger
from ws.manager import socket_app

# Kommenterar ut för att undvika cirkulära imports
# from tests.test_backend_order import test_backend_limit_order

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Hanterar startup och shutdown för applikationen."""
    # Startup
    logger.info("🚀 TradingBot Backend startar...")

    # Starta Bitfinex WebSocket-anslutning endast om flagga är på
    try:
        if bool(get_ws_connect_on_start()):
            import time as _t

            _t0 = _t.perf_counter()
            await bitfinex_ws.connect()
            _t1 = _t.perf_counter()
            logger.info("✅ WebSocket-anslutning etablerad (%.0f ms)", (_t1 - _t0) * 1000)
            # WS‑auth direkt om nycklar finns så att privata flöden (t.ex. margin miu) fungerar
            try:
                _ta = _t.perf_counter()
                await bitfinex_ws.ensure_authenticated()
                _tb = _t.perf_counter()
                logger.info("🔐 WS‑auth klar (%.0f ms)", (_tb - _ta) * 1000)
            except Exception as e:
                logger.warning(f"⚠️ WS‑auth misslyckades: {e}")
        else:
            logger.info("WS‑connect vid start är AV. Kan startas via WS‑test sidan eller API.")
    except Exception as e:
        logger.warning(f"⚠️ WebSocket-anslutning misslyckades: {e}")

    # Starta scheduler
    try:
        from services.scheduler import scheduler

        scheduler.start()
        # Valfri warm-up av probabilistisk validering vid start baserat på runtime-flagga
        try:
            if bool(get_validation_on_start()):
                import asyncio as _asyncio

                _asyncio.create_task(scheduler.run_prob_validation_once())
                logger.info("🟡 Validation warm-up schemalagd vid startup")
        except Exception as _e:
            logger.debug("%s", f"Warm-up init fel: {_e}")
    except Exception as e:
        logger.warning(f"⚠️ Kunde inte starta scheduler: {e}")

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
    except Exception as e:
        logger.warning(f"⚠️ Fel vid stopp av scheduler: {e}")


# Skapa FastAPI-applikation


# Skapa FastAPI-applikation – loggning före app-instans för tydlighet
settings = Settings()

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # I produktion, specificera dina domäner
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inkludera REST endpoints
app.include_router(rest_router)

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
_WS_TEST_DIR = os.path.join(_FRONTEND_DIR, "ws-test")
_RISK_PANEL_DIR = os.path.join(_FRONTEND_DIR, "risk-panel")
_SHARED_DIR = os.path.join(_FRONTEND_DIR, "shared")
app.mount("/ws-test", StaticFiles(directory=_WS_TEST_DIR, html=True), name="ws-test")
app.mount("/risk-panel", StaticFiles(directory=_RISK_PANEL_DIR, html=True), name="risk-panel")
app.mount("/shared", StaticFiles(directory=_SHARED_DIR, html=False), name="shared")


@app.get("/risk-panel-legacy")
async def risk_panel_legacy() -> FileResponse:
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "risk_panel.html")
    return FileResponse(path)


@app.get("/ws-test-legacy")
async def ws_test_legacy() -> FileResponse:
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "ws_test.html")
    return FileResponse(path)


@app.get("/prob-test")
async def prob_test_page() -> FileResponse:
    import os

    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "prob_test.html")
    return FileResponse(path)


@app.get("/prob_test.html")
async def prob_test_html_alias() -> FileResponse:
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

    txt = render_prometheus_text()
    return Response(
        content=txt,
        media_type="text/plain; version=0.0.4",
    )


# Enkel ASGI-middleware för latens per endpoint
@app.middleware("http")
async def latency_middleware(request: Request, call_next):
    import time

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
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
        observe_latency(
            path=path_template or request.url.path,
            method=request.method,
            status_code=getattr(response, "status_code", 0),
            duration_ms=duration_ms,
        )
    except Exception:
        pass
    return response


# Wrappar alltid Socket.IO UI
_socketio = importlib.import_module("socketio")
app = _socketio.ASGIApp(
    socket_app,
    other_asgi_app=app,
    socketio_path="/ws/socket.io",
)
logger.info("Socket.IO UI aktiverad")

if __name__ == "__main__":
    from config.settings import Settings as _S

    _s = _S()
    uvicorn.run(
        "main:app",
        host=_s.HOST,
        port=_s.PORT,
        reload=True,
        log_level="info",
    )
