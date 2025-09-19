# Genesis Trading Bot

En avancerad trading bot för Bitfinex med live signals, regime detection och enhanced auto-trading.

## 🚀 Snabbstart

### 1. Klona projektet

```bash
git clone https://github.com/JohnCCarter/Genesis.git
cd Genesis
git checkout Genesis
```

### 2. Konfigurera environment

**Windows PowerShell:**

```powershell
# Skapa virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Installera dependencies med pip-tools
pip install pip-tools
pip-sync tradingbot-backend/requirements.txt
```

**Windows Command Prompt:**

```cmd
# Skapa virtual environment
python -m venv .venv
.venv\Scripts\activate

# Installera dependencies med pip-tools
pip install pip-tools
pip-sync tradingbot-backend/requirements.txt
```

### 3. Konfigurera config-filer

```bash
# Kör setup script för att skapa config-filer från templates
python setup_config.py
```

### 4. Konfigurera API-nycklar

Skapa `.env` fil i root-mappen:

```env
BITFINEX_API_KEY=din_api_key
BITFINEX_API_SECRET=din_api_secret
```

### 5. Starta systemet

**Windows PowerShell:**

```powershell
# Backend (förhindra WebSocket-hängning vid start)
cd tradingbot-backend
$env:WS_CONNECT_ON_START='False'
python -m uvicorn main:app --reload

# Frontend (nytt PowerShell-fönster)
cd frontend/dashboard
npm install
npm run dev
```

**Windows Command Prompt:**

```cmd
# Backend (förhindra WebSocket-hängning vid start)
cd tradingbot-backend
set WS_CONNECT_ON_START=False
python -m uvicorn main:app --reload

# Frontend (nytt Command Prompt-fönster)
cd frontend/dashboard
npm install
npm run dev
```

**OBS:** `WS_CONNECT_ON_START=False` förhindrar att backend hänger sig vid start. WebSocket kan aktiveras senare via API eller genom att sätta miljövariabeln till `True`.

## 📁 Config-filer

Efter setup skapas följande config-filer från templates:

- `tradingbot-backend/config/strategy_settings.json` - Strategi-inställningar
- `tradingbot-backend/config/trading_rules.json` - Trading-regler och tider
- `tradingbot-backend/config/performance_history.json` - Performance-historik

**Viktigt:** Redigera `trading_rules.json` och sätt `"paused": false` när du är redo att handla.

## 🎯 Funktioner

- **Live Trading Signals** med confidence scores och probabilities
- **Enhanced Auto-Trading** som kombinerar signals med befintligt system
- **Regime Detection** för automatisk strategi-anpassning
- **Performance Tracking** för enhanced trading
- **TTL-baserad Cache** för live data-uppdateringar
- **Risk Management** med circuit breakers och trading windows
- **WebSocket-first Data Service** med intelligent REST-fallback
- **Unified Market Data Facade** för konsistent dataåtkomst

## 🔧 Felsökning

### Backend hänger sig vid start

Om backend hänger sig vid start, kontrollera:

**Windows PowerShell:**

```powershell
# Stoppa alla Python-processer
taskkill /F /IM python.exe

# Starta med inaktiverad WebSocket-anslutning
$env:WS_CONNECT_ON_START='False'
cd tradingbot-backend
python -m uvicorn main:app --reload
```

**Windows Command Prompt:**

```cmd
# Stoppa alla Python-processer
taskkill /F /IM python.exe

# Starta med inaktiverad WebSocket-anslutning
set WS_CONNECT_ON_START=False
cd tradingbot-backend
python -m uvicorn main:app --reload
```

### Frontend får inte token

Om frontend inte kan få JWT-token:

**Windows PowerShell:**

```powershell
# Kontrollera att backend körs
curl http://127.0.0.1:8000/health

# Testa token-endpoint
curl -X POST http://127.0.0.1:8000/api/v2/auth/ws-token -H "Content-Type: application/json" -d '{"user_id":"test","scope":"read","expiry_hours":1}'
```

**Windows Command Prompt:**

```cmd
# Kontrollera att backend körs
curl http://127.0.0.1:8000/health

# Testa token-endpoint
curl -X POST http://127.0.0.1:8000/api/v2/auth/ws-token -H "Content-Type: application/json" -d "{\"user_id\":\"test\",\"scope\":\"read\",\"expiry_hours\":1}"
```

1. Kontrollera CORS-inställningar i backend

### Dependencies-konflikter

Om du får dependency-konflikter:

**Windows PowerShell/Command Prompt:**

```powershell
# Använd pip-tools för kontrollerad installation
pip install pip-tools
pip-compile tradingbot-backend/requirements.in
pip-sync tradingbot-backend/requirements.txt
```

## 📚 Dokumentation

Se `tradingbot-backend/IMPLEMENTATION_TODO_LIVE_TRADING.md` för detaljerad implementation guide.
