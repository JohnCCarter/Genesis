"""
Simple Socket.IO Server - TradingBot Backend

En enkel Socket.IO server för att testa WebSocket funktionalitet.
"""

import socketio
import uvicorn
from fastapi import FastAPI

# Skapa Socket.IO server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio)

# Skapa FastAPI app
app = FastAPI()

# Mount Socket.IO
app.mount("/ws", socket_app)

@sio.event
async def connect(sid, environ):
    """Hanterar anslutning."""
    print(f"✅ Client ansluten: {sid}")
    await sio.emit('connected', {'message': 'Ansluten till TradingBot!'}, room=sid)

@sio.event
async def disconnect(sid):
    """Hanterar frånkoppling."""
    print(f"❌ Client frånkopplad: {sid}")

@sio.event
async def evaluate_strategy_ws(sid, data):
    """Test event för strategiutvärdering."""
    print(f"📊 Strategiutvärdering begärd av {sid}: {data}")
    
    # Mock resultat
    result = {
        "signal": "BUY",
        "confidence": 0.75,
        "timestamp": "2025-08-05T00:45:00Z"
    }
    
    await sio.emit('strategy_result', result, room=sid)
    print(f"📤 Strategiutvärdering skickad: {result}")

@sio.event
async def start_realtime_monitoring(sid, data):
    """Test event för realtids övervakning."""
    print(f"🔍 Realtids övervakning begärd av {sid}: {data}")
    
    result = {
        "symbol": data.get('symbol', 'tBTCUSD'),
        "status": "started"
    }
    
    await sio.emit('monitoring_started', result, room=sid)
    print(f"📤 Realtids övervakning startad: {result}")

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "TradingBot Socket.IO Test Server",
        "version": "1.0.0",
        "websocket": "/ws"
    }

@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

if __name__ == "__main__":
    print("🚀 Startar Socket.IO test server på port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000) 