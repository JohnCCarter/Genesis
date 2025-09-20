# Genesis Trading Bot

> **🚧 UNDER AKTIV UTVECKLING** - Detta projekt är i beta-fas och under kontinuerlig utveckling. Använd endast i testmiljö och på egen risk.

En modulär trading-plattform för Bitfinex med realtids-signaler, regime detection, riskkontroller och dashboard för övervakning.

> **⚠️ VIKTIGT:** Använd i testmiljö innan verklig handel. Ingen garanti för avkastning eller vinst.

[![Development Status](https://img.shields.io/badge/Status-Beta%20Development-orange.svg)](README.md)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-blue.svg)](.github/workflows/ci.yml)
[![Contributors](https://img.shields.io/badge/Contributors-Welcome-green.svg)](CONTRIBUTING.md)

## 📋 Innehåll

1. [Översikt](#översikt)
2. [Arkitektur](#arkitektur)
3. [Funktioner](#funktioner)
4. [Teknisk Stack](#teknisk-stack)
5. [Snabbstart](#snabbstart)
6. [Detaljerad Installation](#detaljerad-installation)
7. [Konfiguration](#konfiguration)
8. [Körning & Utveckling](#körning--utveckling)
9. [Trading-säkerhet & Ansvarsfriskrivning](#trading-säkerhet--ansvarsfriskrivning)
10. [Felsökning](#felsökning)
11. [Roadmap](#roadmap)
12. [Contributing](#contributing)
13. [Security](#security)
14. [License](#license)
15. [Appendix](#appendix)

## 🏗️ Översikt

Genesis kombinerar:

- **Signalgenerering** med probabilities & confidence scores
- **Regime detection** (trend / range / balanced) för dynamisk strategi
- **Riskkontroller** (circuit breakers, trading windows, pausläge)
- **Unified data layer** + caching för snabb responstid
- **Frontend dashboard** (React + Vite) för övervakning och styrning

## 🏛️ Arkitektur

```
┌─────────────────────────────────────────────────────────────┐
│                    Genesis Trading Bot                      │
├─────────────────────────────────────────────────────────────┤
│  Frontend (React + Vite + Socket.IO Client)                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Dashboard │  Trading │  Risk │  Market │  History      │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────▲───────────────────────────────────────┘
                      │ WebSocket + REST
┌─────────────────────┴───────────────────────────────────────┐
│  Backend (FastAPI / Uvicorn)                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Signals │  Regime │  Trading Flow │  Risk Control      │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────▲───────────────────────────────────────┘
                      │ Bitfinex API
┌─────────────────────┴───────────────────────────────────────┐
│  Exchange / External Data                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Bitfinex REST │  Bitfinex WebSocket │  Market Data     │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

Konfigurationsfiler (JSON) styr strategi, regler och ackumulerad historik.

## ✨ Funktioner

| Kategori | Beskrivning |
|----------|-------------|
| **🤖 Signals** | Realtids-trading-signaler med confidence/probabilities |
| **🔄 Auto-Trading** | Integrerad exekveringsmotor med orderhantering |
| **📊 Regime Detection** | Dynamisk anpassning av strategi baserat på marknadsregime |
| **🛡️ Risk Management** | Circuit breakers, trading windows, pausläge |
| **📈 Performance Tracking** | Historik + resultatsparande med backtesting |
| **⚡ Cache & Data Facade** | TTL-cache + enhetlig datatjänst |
| **🔌 WebSocket-first** | Push-uppdateringar + REST fallback |
| **📱 Dashboard** | Paneler för trading, risk, market, history, system |

## 🛠️ Teknisk Stack

### Backend
- **Python 3.11+** - Huvudspråk
- **FastAPI** - Web framework med automatisk OpenAPI
- **Uvicorn** - ASGI server
- **SQLite/Redis** - Data storage & caching
- **WebSocket** - Realtidskommunikation

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Socket.IO** - Realtidskommunikation

### DevOps & Kvalitet
- **GitHub Actions** - CI/CD
- **Black/Ruff** - Code formatting & linting
- **Bandit** - Security scanning
- **Pytest** - Testing
- **pip-tools** - Dependency management

## 🚀 Snabbstart

### Backend
```powershell
# 1. Klona och aktivera miljö
git clone https://github.com/JohnCCarter/Genesis.git
cd Genesis
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Installera dependencies
pip install pip-tools
pip-sync tradingbot-backend/requirements.txt

# 3. Konfigurera
cp tradingbot-backend/env.example tradingbot-backend/.env
# Redigera .env med dina API-nycklar

# 4. Starta backend
cd tradingbot-backend
python -m uvicorn main:app --reload
```

### Frontend
```powershell
# 1. Installera dependencies
cd frontend/dashboard
npm install

# 2. Starta utvecklingsserver
npm run dev
```

**🎯 Resultat:** Backend på `http://127.0.0.1:8000`, Frontend på `http://localhost:5173`

## 📦 Detaljerad Installation

### Förutsättningar

- **Python 3.11+** (rekommenderat)
- **Node.js 18+**
- **pip, pip-tools**
- (Valfritt) Docker för containerisering

### Backend

#### Windows PowerShell
```powershell
# Skapa virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Installera dependencies med pip-tools
pip install -U pip pip-tools
pip-sync tradingbot-backend/requirements.txt
```

#### Windows Command Prompt
```cmd
# Skapa virtual environment
python -m venv .venv
.venv\Scripts\activate

# Installera dependencies med pip-tools
pip install -U pip pip-tools
pip-sync tradingbot-backend/requirements.txt
```

#### Linux/macOS
```bash
# Skapa virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Installera dependencies med pip-tools
pip install -U pip pip-tools
pip-sync tradingbot-backend/requirements.txt
```

### Frontend

```bash
# Installera Node.js dependencies
cd frontend/dashboard
npm install

# Starta utvecklingsserver
npm run dev
```

## ⚙️ Konfiguration

### Miljövariabler (.env)

Skapa `tradingbot-backend/.env` från `env.example`:

```env
# Bitfinex API REST/WS
BITFINEX_API_KEY=din_api_nyckel
BITFINEX_API_SECRET=din_api_hemlighet
BITFINEX_PUBLIC_API_URL=https://api-pub.bitfinex.com/v2
BITFINEX_AUTH_API_URL=https://api.bitfinex.com/v2

# WebSocket
BITFINEX_WS_API_KEY=din_api_nyckel
BITFINEX_WS_API_SECRET=din_api_hemlighet
BITFINEX_WS_PUBLIC_URI=wss://api-pub.bitfinex.com/ws/2
BITFINEX_WS_AUTH_URI=wss://api.bitfinex.com/ws/2

# Backend JWT
JWT_SECRET_KEY=byt_till_en_stark_hemlighet
SOCKETIO_JWT_SECRET=byt_till_en_stark_hemlighet
ACCESS_TOKEN_EXPIRE_MINUTES=30
AUTH_REQUIRED=True

# WebSocket vid start (rekommenderas False i utveckling)
WS_CONNECT_ON_START=False

# Telegram (valfritt)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

### Config-filer

| Fil | Funktion | Viktiga fält |
|-----|----------|--------------|
| `strategy_settings.json` | Parametrar för indikatorer och modell | `enabled`, `timeframes`, `indicators` |
| `trading_rules.json` | Tidsfönster, pausflagga, riskgränser | `paused`, `max_trades_per_day`, `windows` |
| `risk_guards.json` | Riskhantering | `max_daily_loss`, `kill_switch`, `exposure_limits` |
| `order_templates.json` | Ordermallar | Bracket order templates |

**Aktivera handel:** Sätt `"paused": false` i `trading_rules.json`.

## 🏃‍♂️ Körning & Utveckling

### Utvecklingsläge

```powershell
# Backend (förhindra WebSocket-hängning)
cd tradingbot-backend
$env:WS_CONNECT_ON_START='False'
python -m uvicorn main:app --reload

# Frontend (nytt terminal)
cd frontend/dashboard
npm run dev
```

### Produktionsläge

```powershell
# Backend
cd tradingbot-backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Frontend (bygg för produktion)
cd frontend/dashboard
npm run build
npm run preview
```

### Kodkvalitet

```powershell
# Formatering
python -m black .

# Linting
python -m ruff check . --fix

# Säkerhet
python -m bandit -r . -c bandit.yaml

# Tester
python -m pytest tests/ -v
```

## ⚠️ Trading-säkerhet & Ansvarsfriskrivning

### Viktiga varningar

- **🚨 RISK:** All handel med verkliga pengar medför risk för förluster
- **🧪 TESTA:** Använd alltid testnet/simulerad miljö först
- **💰 BEGRÄNSA:** Sätt aldrig mer pengar än du kan förlora
- **📊 ÖVERVAKA:** Systemet kräver aktiv övervakning
- **🔒 SÄKERHET:** Skydda dina API-nycklar och privata nycklar

### Ansvarsfriskrivning

Detta program tillhandahålls "som det är" utan garantier. Användaren ansvarar för:

- Alla trading-beslut och deras konsekvenser
- Säkerheten för API-nycklar och privata nycklar
- Övervakning av systemets prestanda
- Compliance med lokala lagar och regler
- Testning i säker miljö innan verklig handel

**Ingen garanti för avkastning eller vinst.**

## 🔧 Felsökning

### Backend hänger sig vid start

```powershell
# Stoppa alla Python-processer
taskkill /F /IM python.exe

# Starta med inaktiverad WebSocket
$env:WS_CONNECT_ON_START='False'
cd tradingbot-backend
python -m uvicorn main:app --reload
```

### Frontend får inte token

```powershell
# 1. Kontrollera att backend körs
curl http://127.0.0.1:8000/health

# 2. Testa token-endpoint
curl -X POST http://127.0.0.1:8000/api/v2/auth/ws-token \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","scope":"read","expiry_hours":1}'

# 3. Kontrollera CORS-konfiguration
```

### Dependencies-konflikter

```powershell
# Använd pip-tools för kontrollerad installation
pip install pip-tools
pip-compile tradingbot-backend/requirements.in
pip-sync tradingbot-backend/requirements.txt
```

## 🗺️ Roadmap

Se [tradingbot-backend/IMPLEMENTATION_TODO_LIVE_TRADING.md](tradingbot-backend/IMPLEMENTATION_TODO_LIVE_TRADING.md) för detaljerad roadmap.

### Kommande funktioner
- [ ] Machine Learning model training
- [ ] Advanced portfolio management
- [ ] Multi-exchange support
- [ ] Mobile app
- [ ] Advanced analytics dashboard

## 🤝 Contributing

Vi välkomnar bidrag! Se [CONTRIBUTING.md](CONTRIBUTING.md) för detaljerade riktlinjer.

### Snabbstart för bidragsgivare

1. Forka repositoryt
2. Skapa en feature branch (`git checkout -b feature/amazing-feature`)
3. Commita dina ändringar (`git commit -m 'Add some amazing feature'`)
4. Pusha till branchen (`git push origin feature/amazing-feature`)
5. Öppna en Pull Request

### Utvecklingsstandarder
- Följ PEP 8 (Black formatering)
- Skriv tester för nya funktioner
- Uppdatera dokumentation
- Använd tydliga commit-meddelanden

## 🔒 Security

### Rapportera sårbarheter

Om du upptäcker en säkerhetsbrist:

1. **INTE** skapa en public issue
2. Skicka e-post till: [security@example.com](mailto:security@example.com)
3. Inkludera detaljerad beskrivning
4. Vi svarar inom 48 timmar

### Säkerhetsåtgärder

- API-nycklar lagras säkert i miljövariabler
- JWT-tokens med kort livslängd
- Rate limiting på alla endpoints
- Input validation med Pydantic
- Security scanning med Bandit

## 📄 License

Detta projekt är licensierat under MIT License - se [LICENSE](LICENSE) filen för detaljer.

## 📚 Appendix

### API Endpoints

| Endpoint | Beskrivning |
|----------|-------------|
| `GET /health` | Hälsokontroll |
| `POST /api/v2/auth/ws-token` | Hämta JWT token |
| `GET /api/v2/config/keys` | Lista konfigurationsnycklar |
| `GET /api/v2/risk/status` | Riskstatus |
| `POST /api/v2/order` | Placera order |

### Health Check

```bash
curl http://127.0.0.1:8000/health
```

### Projektstruktur

```
Genesis/
├── tradingbot-backend/     # Backend (FastAPI)
│   ├── services/          # Core services
│   ├── rest/             # REST API
│   ├── ws/               # WebSocket
│   ├── config/           # Configuration
│   └── tests/            # Tests
├── frontend/dashboard/    # Frontend (React)
└── scripts/              # Utility scripts
```

### Dokumentation

- **Backend:** [tradingbot-backend/README.md](tradingbot-backend/README.md)
- **Implementation:** [tradingbot-backend/IMPLEMENTATION_TODO_LIVE_TRADING.md](tradingbot-backend/IMPLEMENTATION_TODO_LIVE_TRADING.md)
- **Unified Config:** [TODO_UNIFIED_CONFIG_V2.md](TODO_UNIFIED_CONFIG_V2.md)
- **Agent Collaboration:** [AGENT_PLAN.md](AGENT_PLAN.md)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)