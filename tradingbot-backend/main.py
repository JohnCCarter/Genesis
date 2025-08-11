"""
TradingBot Backend - Huvudapplikation

Denna fil innehåller huvudapplikationen för tradingbot-backend med FastAPI och Socket.IO.
Hanterar startup, shutdown och routing till olika moduler.
"""

from contextlib import asynccontextmanager
from datetime import datetime

import socketio
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config.settings import Settings
from rest.routes import router as rest_router
from services.bitfinex_websocket import bitfinex_ws
from services.metrics import observe_latency, render_prometheus_text
from utils.logger import get_logger
from ws.manager import socket_app

# Kommenterar ut för att undvika cirkulära imports
# from tests.test_backend_order import test_backend_limit_order

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hanterar startup och shutdown för applikationen."""
    # Startup
    logger.info("🚀 TradingBot Backend startar...")

    # Starta Bitfinex WebSocket-anslutning (behålls även i CORE_MODE)
    try:
        await bitfinex_ws.connect()
        logger.info("✅ WebSocket-anslutning etablerad")
    except Exception as e:
        logger.warning(f"⚠️ WebSocket-anslutning misslyckades: {e}")

    # Starta scheduler endast om ej CORE_MODE
    try:
        if not Settings().CORE_MODE:
            from services.scheduler import scheduler

            scheduler.start()
        else:
            logger.info("CORE_MODE aktivt: hoppar över scheduler")
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
        if not Settings().CORE_MODE:
            from services.scheduler import scheduler

            await scheduler.stop()
    except Exception as e:
        logger.warning(f"⚠️ Fel vid stopp av scheduler: {e}")


# Skapa FastAPI-applikation


# Skapa FastAPI-applikation – flytta inställningsloggningen UTANFÖR app=FastAPI(...)
settings = Settings()

logger.info("🔑 Kontroll vid startup:")
logger.info("    BITFINEX_API_KEY: %s", "✅" if settings.BITFINEX_API_KEY else "❌")
logger.info("    API_SECRET status: %s", "✅" if settings.BITFINEX_API_SECRET else "❌")

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
@app.get("/ws-test")
async def ws_test_page() -> FileResponse:
    import os

    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "ws_test.html")
    return FileResponse(path)


@app.get("/risk-panel")
async def risk_panel_page() -> FileResponse:
    import os

    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "risk_panel.html")
    return FileResponse(path)


@app.get("/metrics")
async def metrics() -> Response:
    txt = render_prometheus_text()
    return Response(content=txt, media_type="text/plain; version=0.0.4")


# Enkel ASGI-middleware för latens per endpoint
@app.middleware("http")
async def latency_middleware(request: Request, call_next):
    import time

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    try:
        # path-template fås enklast via scope/route (kan vara None i root-asgi)
        path_template = getattr(getattr(request, "scope", {}), "get", lambda *_: None)(
            "path"
        )
        # Försök att hämta route.path_params/template från request.scope["route"].path
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


# Wrappar endast Socket.IO när Core Mode inte är aktivt
if not settings.CORE_MODE:
    app = socketio.ASGIApp(
        socket_app, other_asgi_app=app, socketio_path="/ws/socket.io"
    )
    logger.info("Socket.IO UI aktiverad")
else:
    logger.info("CORE_MODE: Socket.IO UI avstängd")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
