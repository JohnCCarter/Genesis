"""
En enkel självständig Socket.IO testserver för att isolera WebSocket-problem
"""

import socketio
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import os
import logging

# Konfigurera loggning
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("simple_ws_test")

# Skapa en Socket.IO server med detaljerad loggning
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=['*'],  # Tillåt alla ursprung för test
    logger=True,
    engineio_logger=True
)

# Skapa FastAPI app
app = FastAPI(title="SimpleWebSocket Test Server")

# CORS-middleware - mycket tillåtande för test
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Skapa ASGI app
socket_app = socketio.ASGIApp(
    sio,
    socketio_path='/socket.io',
    static_files={
        '/': './ws_test.html'  # Servera testsidan på root
    }
)

# Montera Socket.IO app
app.mount("/ws", socket_app)

# Socket.IO-händelser
@sio.event
async def connect(sid, environ):
    """Hantera anslutning - utan autentisering för test."""
    logger.info(f"Socket.IO anslutning för sid: {sid}")
    logger.info(f"QUERY_STRING: {environ.get('QUERY_STRING', 'okänd')}")
    
    # Svara med authenticated-händelse
    await sio.emit('authenticated', {'status': 'success', 'user': 'test_user'}, room=sid)
    logger.info(f"✅ Användare autentiserad")
    return True

@sio.event
async def disconnect(sid):
    """Hantera frånkoppling av klient."""
    logger.info(f"Socket.IO-klient frånkopplad: {sid}")

@sio.event
async def request_token(sid, data):
    """Testhändelse för token-generering."""
    logger.info(f"Token-begäran från {sid}: {data}")
    
    token = "test-token-123"
    await sio.emit('token_generated', {'token': token}, room=sid)
    logger.info(f"Token genererad för klient {sid}")

@app.get("/")
async def root():
    """Root endpoint för API."""
    return {
        "message": "Simple WebSocket Test Server",
        "endpoints": {
            "websocket": "/ws",
            "test_page": "/"
        }
    }

# Skapa en enkel token-endpoint
@app.get("/api/v2/auth/ws-token-test")
async def get_test_token():
    """Enkel test-endpoint för token-generering."""
    return {
        "success": True,
        "token": "test-token-123",
        "message": "Detta är en test-token - används bara för testsyften"
    }

if __name__ == "__main__":
    port = 8080  # Använd en annan port än huvudservern
    logger.info(f"🚀 Startar Simple WebSocket Test Server på port {port}")
    logger.info(f"⚠️ Endast för testning - inte för produktion!")
    logger.info(f"📝 Testsida tillgänglig på http://localhost:{port}/ws/")
    uvicorn.run(app, host="0.0.0.0", port=port)
