# Socket.IO Setup Guide - TradingBot Backend

## ✅ **Vad som fungerar:**

### **Socket.IO Installation:**
- ✅ Socket.IO är installerat korrekt
- ✅ Socket.IO server kan skapas framgångsrikt
- ✅ Event handlers kan registreras korrekt
- ✅ Socket.IO client kan skapas framgångsrikt

### **WebSocket Events:**
- ✅ `connect` - Hanterar anslutning
- ✅ `disconnect` - Hanterar frånkoppling
- ✅ `evaluate_strategy_ws` - Strategiutvärdering
- ✅ `start_realtime_monitoring` - Starta realtids övervakning
- ✅ `stop_realtime_monitoring` - Stoppa realtids övervakning
- ✅ `get_active_signals` - Hämta aktiva signaler

## 🚀 **Starta Socket.IO Server:**

### **Alternativ 1: Använd huvudservern**
```bash
cd tradingbot-backend
python main.py
```

### **Alternativ 2: Använd enkel test-server**
```bash
cd tradingbot-backend
python simple_socketio_server.py
```

## 🔧 **Testa Socket.IO:**

### **Test 1: Kontrollera server status**
```bash
curl http://localhost:8000/
```

### **Test 2: Testa Socket.IO handshake**
```bash
curl http://localhost:8000/ws/socket.io/?EIO=4&transport=polling
```

### **Test 3: Använd Socket.IO client**
```bash
python test_socketio_fix.py
```

## 📋 **WebSocket Events som är tillgängliga:**

### **Strategiutvärdering:**
```javascript
// Skicka data för strategiutvärdering
socket.emit('evaluate_strategy_ws', {
    "closes": [100, 101, 102, 103, 104, 105],
    "highs": [102, 103, 104, 105, 106, 107],
    "lows": [98, 99, 100, 101, 102, 103]
});

// Lyssna på resultat
socket.on('strategy_result', function(data) {
    console.log('Strategi resultat:', data);
});
```

### **Realtids övervakning:**
```javascript
// Starta övervakning
socket.emit('start_realtime_monitoring', {
    "symbol": "tBTCUSD"
});

// Lyssna på start
socket.on('monitoring_started', function(data) {
    console.log('Övervakning startad:', data);
});

// Stoppa övervakning
socket.emit('stop_realtime_monitoring', {
    "symbol": "tBTCUSD"
});

// Lyssna på stopp
socket.on('monitoring_stopped', function(data) {
    console.log('Övervakning stoppad:', data);
});
```

### **Aktiva signaler:**
```javascript
// Hämta aktiva signaler
socket.emit('get_active_signals');

// Lyssna på aktiva signaler
socket.on('active_signals', function(data) {
    console.log('Aktiva signaler:', data);
});
```

## ⚠️ **Viktigt:**

- **Servern måste vara igång** för att WebSocket ska fungera
- **Använd rätt endpoint:** `/ws` för Socket.IO
- **CORS är konfigurerat** för alla origins
- **Event handlers är registrerade** och redo

## 🎯 **Nästa steg:**

1. Starta servern: `python main.py`
2. Testa WebSocket: `python test_socketio_fix.py`
3. Använd WebSocket events i din frontend
