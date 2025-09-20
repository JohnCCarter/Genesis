# Genesis Trading Bot - Backend

> **Högpresterande FastAPI-backend för automatiserad trading med Bitfinex API, AI-driven signalgenerering och omfattande riskhantering.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/Tests-Pytest-green.svg)](tests/)
[![Security](https://img.shields.io/badge/Security-Bandit-red.svg)](bandit.yaml)

## 📋 Innehållsförteckning

1. [Översikt & Arkitektur](#översikt--arkitektur)
2. [Funktioner](#funktioner)
3. [Teknisk Stack](#teknisk-stack)
4. [Snabbstart](#snabbstart)
5. [Detaljerad Installation](#detaljerad-installation)
6. [Konfiguration](#konfiguration)
7. [Körning & Utveckling](#körning--utveckling)
8. [API-dokumentation](#api-dokumentation)
9. [Moduler & Arkitektur](#moduler--arkitektur)
10. [Tester](#tester)
11. [Kodkvalitet & Säkerhet](#kodkvalitet--säkerhet)
12. [Felsökning](#felsökning)
13. [Roadmap](#roadmap)
14. [Contributing](#contributing)
15. [Security](#security)
16. [License](#license)
17. [Appendix](#appendix)

## 🏗️ Översikt & Arkitektur

Backend-delen av Genesis Trading Bot är en skalbar, säker och högpresterande FastAPI-applikation som hanterar:

- **🤖 AI-driven signalgenerering** med sannolikhetsmodeller och regime detection
- **📊 WebSocket-first marknadsdata** med intelligent REST-fallback
- **🛡️ Omfattande riskhantering** med circuit breakers och trading windows
- **🔧 Unified Configuration Management** med central store och rollback
- **⚡ Högpresterande trading** med optimerad orderhantering
- **📈 Avancerad backtesting** och performance tracking

### Arkitektur

```
┌─────────────────────────────────────────────────────────────┐
│                    Genesis Backend                          │
├─────────────────────────────────────────────────────────────┤
│  FastAPI Application (main.py)                             │
├─────────────────────────────────────────────────────────────┤
│  REST API          │  WebSocket API    │  Unified Config   │
│  ├── auth.py       │  ├── manager.py   │  ├── config_store │
│  ├── routes.py     │  ├── auth.py      │  ├── key_registry │
│  ├── wallet.py     │  └── handlers/    │  └── rollback     │
│  └── positions.py  │                   │                   │
├─────────────────────────────────────────────────────────────┤
│  Services Layer                                             │
│  ├── Market Data   │  ├── Risk Mgmt    │  ├── Trading      │
│  ├── Signals       │  ├── Circuit Br.  │  └── Analytics    │
│  └── Config Mgmt   │  └── Monitoring   │                   │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                │
│  ├── SQLite (Config)  │  ├── Redis (Cache)  │  ├── Files   │
│  └── Bitfinex API     │  └── WebSocket      │  └── Logs    │
└─────────────────────────────────────────────────────────────┘
```

## ✨ Funktioner

| Kategori | Funktioner |
|----------|------------|
| **🤖 AI & Signals** | Sannolikhetsmodeller, Regime detection, Unified signal service |
| **📊 Marknadsdata** | WebSocket-first, REST fallback, TTL-baserad cache, Market data facade |
| **🛡️ Riskhantering** | Circuit breakers, Trading windows, Max trades per dag/symbol, Risk guards |
| **🔧 Konfiguration** | Central store, Rollback, Observability, Key registry, Priority profiles |
| **📈 Trading** | Enhanced auto-trading, Bracket orders, Order templates, Order validation |
| **📊 Analytics** | Backtesting, Performance tracking, Heatmaps, Cost-aware analysis |
| **🛠️ Utveckling** | CI/CD, Kodkvalitet, Agent collaboration, Comprehensive testing |

## 🛠️ Teknisk Stack

### Core Framework
- **Python 3.11+** - Huvudspråk
- **FastAPI 0.104+** - Web framework med automatisk OpenAPI
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation och serialization

### Data & Storage
- **SQLite** - Konfigurationsdata och metadata
- **Redis** - Caching och pub/sub
- **JSON** - Konfigurationsfiler
- **SQLAlchemy** - ORM (framtida utökning)

### External APIs
- **Bitfinex API v2** - REST och WebSocket
- **WebSocket** - Realtidskommunikation
- **HTTP/HTTPS** - REST API calls

### Development & Quality
- **Black** - Code formatting
- **Ruff** - Linting och import sorting
- **Bandit** - Security scanning
- **Pytest** - Testing framework
- **MyPy** - Type checking
- **pip-tools** - Dependency management

## 🚀 Snabbstart

```powershell
# 1. Aktivera miljö och installera dependencies
cd tradingbot-backend
pip install -r requirements.txt

# 2. Konfigurera miljövariabler
cp env.example .env
# Redigera .env med dina API-nycklar

# 3. Starta servern
python -m uvicorn main:app --reload
```

**🎯 Resultat:** Backend på `http://127.0.0.1:8000` med automatisk API-dokumentation på `/docs`

## 📦 Detaljerad Installation

### Förutsättningar

- Python 3.8+
- pip
- virtualenv (rekommenderas)

### Steg för installation

1. Klona repositoryt:

```bash
git clone https://github.com/yourusername/genesis-trading-bot.git
cd genesis-trading-bot/tradingbot-backend
```

2. Aktivera den delade virtuella miljön i repo-rot (rekommenderat):

```bash
# I repo-rot:
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

3. Installera beroenden:

```bash
pip install -r requirements.txt
```

4. Starta servern (utveckling):

Alternativ A – kör från `tradingbot-backend`:

```powershell
cd .\tradingbot-backend
$env:AUTH_REQUIRED = "True"
$env:PYTHONPATH   = (Resolve-Path ".").Path
python -m uvicorn main:app --reload
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Alternativ B – kör från repo-roten med skript (rekommenderas för enkelhet):

```powershell
pwsh -File .\scripts\start.ps1   # startar på http://127.0.0.1:8000
```

Alternativ C – kör från repo-roten utan skript:

```powershell
$env:AUTH_REQUIRED = "True"
uvicorn main:app --reload --app-dir .\tradingbot-backend
```

Servern startar på `http://127.0.0.1:8000`. Socket.IO finns på `/ws`.

## Konfiguration

1. Kopiera exempelfilen för miljövariabler:

```bash
cp env.example .env
```

2. Redigera `.env` med dina Bitfinex API-nycklar och autentiseringsinställningar:

# --- Bitfinex REST/WS ---
BITFINEX_API_KEY=din_api_nyckel
BITFINEX_API_SECRET=din_api_hemlighet
BITFINEX_PUBLIC_API_URL=https://api-pub.bitfinex.com/v2
BITFINEX_AUTH_API_URL=https://api.bitfinex.com/v2

BITFINEX_WS_API_KEY=din_ws_api_nyckel
BITFINEX_WS_API_SECRET=din_ws_api_hemlighet
BITFINEX_WS_PUBLIC_URI=wss://api-pub.bitfinex.com/ws/2
BITFINEX_WS_AUTH_URI=wss://api.bitfinex.com/ws/2

# Backend JWT
JWT_SECRET_KEY=byt_till_en_stark_hemlighet
SOCKETIO_JWT_SECRET=byt_till_en_stark_hemlighet
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Kräv JWT för REST/WS (sätt False i dev vid behov)
AUTH_REQUIRED=True

# (Valfritt) Telegram-notiser
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...  # BotFather token
TELEGRAM_CHAT_ID=123456789           # Chat eller kanal-ID
# Validering (lätta defaults för snabb start)
# Körs periodiskt av scheduler om PROB_VALIDATE_ENABLED=True
PROB_VALIDATE_ENABLED=true
PROB_VALIDATE_INTERVAL_MINUTES=120
PROB_VALIDATE_TIMEFRAME=1m
PROB_VALIDATE_LIMIT=50           # var låg i utveckling, höj manuellt vid behov
PROB_VALIDATE_MAX_SAMPLES=50     # var låg i utveckling, höj manuellt vid behov

# WS vid start (rekommenderas False i utveckling – starta från ws‑test vid behov)
# Kan togglas via GET/POST /api/v2/mode/ws-connect-on-start
# ws_connect_on_start påverkar bara startup och kräver omstart för effekt
# (runtime‑WS påverkas av dina manuella subar och WS‑strategy‑toggle)

```

3. Se `API_KEY_SETUP.md` för instruktioner om hur du skapar och konfigurerar Bitfinex API-nycklar.

4. Se `SUB_ACCOUNT_SETUP.md` för instruktioner om hur du konfigurerar ett sub-konto för testning.

## Telegram-notiser

Om `TELEGRAM_BOT_TOKEN` och `TELEGRAM_CHAT_ID` är satta skickas notiser vid bl.a.:

- Lyckad/misslyckad order
- Avbruten order (lyckad/misslyckad)
- Circuit Breaker aktivering

Notiser skickas även via Socket.IO som `notification`-event.

## Moduler

> **💡 Snabbtips:** Börja med **Core Trading Services** och **Unified Configuration Management** för att förstå systemets grundläggande funktionalitet.

### Services

#### **Core Trading Services**
- **bitfinex_data.py**: Hanterar hämtning av marknadsdata från Bitfinex REST API
- **bitfinex_websocket.py**: Hanterar realtidsdata via Bitfinex WebSocket API
- **strategy.py**: Implementerar tradingstrategier baserade på tekniska indikatorer
- **realtime_strategy.py**: Hanterar realtidsutvärdering av strategier
- **scheduler.py**: Schemaläggning av strategiutvärderingar och andra uppgifter
- **trading_integration.py**: Integrerar olika delar av systemet för komplett tradingfunktionalitet
- **enhanced_auto_trader.py**: Förbättrad automatisk trading med avancerade funktioner

#### **Unified Configuration Management**
- **unified_config_manager.py**: Huvudklass för enhetlig konfigurationshantering
- **config_store.py**: Central lagring med SQLite/Redis och pub/sub
- **config_cache.py**: Per-process cache med invalidation
- **config_validator.py**: Validering med key registry integration
- **rollback_service.py**: Snapshots, rollback och staged rollout
- **config_observability.py**: Metrics, events och monitoring

#### **Market Data & Signals**
- **market_data_facade.py**: Enhetlig datatjänst med WebSocket-first approach
- **unified_signal_service.py**: Enhetlig signal-orkestrering
- **signal_service.py**: Signalgenerering och utvärdering
- **ws_first_data_service.py**: WebSocket-first data service med REST fallback

#### **Risk Management**
- **risk_policy_engine.py**: Samlar RiskGuards och TradeConstraintsService
- **risk_guards.py**: Globala vakter (max daily loss, kill-switch, exposure limits)
- **trade_constraints.py**: Trading window, dagliga limit och cooldown
- **trading_window.py**: Hantering av handelsfönster
- **trade_counter.py**: Räkning av trades per dag/symbol
- **unified_risk_service.py**: Enhetlig riskhantering

#### **Circuit Breakers & Monitoring**
- **unified_circuit_breaker_service.py**: Enhetlig circuit breaker hantering
- **transport_circuit_breaker.py**: Transport-nivå circuit breakers
- **circuit_breaker_recovery.py**: Återhämtning från circuit breaker tillstånd
- **enhanced_observability_service.py**: Förbättrad observability och monitoring

#### **Probability & Validation**
- **prob_model.py**: Sannolikhetsmodell för trading
- **prob_validation.py**: Validering av sannolikhetsmodeller
- **prob_train.py**: Träning av sannolikhetsmodeller
- **validation_service.py**: Allmän valideringstjänst

#### **Performance & Analytics**
- **performance_tracker.py**: Spårning av tradingprestanda
- **backtest.py**: Backtesting av strategier
- **cost_aware_backtest.py**: Kostnadsmedveten backtesting
- **regime_ablation.py**: Regime detection och ablation studies

#### **Utilities & Support**
- **runtime_config.py**: Runtime konfigurationshantering
- **feature_flags_service.py**: Feature flags hantering
- **notifications.py**: Notifikationshantering
- **metrics.py**: Metrics och telemetri
- **health_watchdog.py**: Hälsokontroll och övervakning

> **📋 Sammanfattning:** Systemet består av **66 services** organiserade i **8 kategorier**. De viktigaste för nya utvecklare är **Core Trading Services** och **Unified Configuration Management**.

### REST API

#### **Core API Endpoints**
- **auth.py**: Autentisering mot Bitfinex REST API
- **routes.py**: FastAPI-routes för backend API
- **wallet.py**: Hantering av plånboksinformation
- **positions.py**: Hantering av positioner
- **positions_history.py**: Hantering av positionshistorik
- **margin.py**: Hantering av margin-information
- **order_history.py**: Hantering av orderhistorik
- **active_orders.py**: Hantering av aktiva ordrar
- **order_validator.py**: Validering av orderparametrar

#### **Advanced API Endpoints**
- **unified_config_api.py**: API för Unified Configuration Management
- **rollback_api.py**: API för rollback och snapshot-hantering
- **observability_api.py**: API för observability och monitoring
- **debug_routes.py**: Debug-endpoints för utveckling
- **funding.py**: Funding och lån-hantering
- **ledgers.py**: Ledger och transaktionshistorik

> **📋 Sammanfattning:** **17 REST API endpoints** organiserade i **Core** (grundläggande trading) och **Advanced** (avancerade funktioner).

### WebSocket

- **auth.py**: Autentisering mot Bitfinex WebSocket API
- **manager.py**: Hantering av WebSocket-anslutningar
- **order_handler.py**: Hantering av ordrar via WebSocket
- **wallet_handler.py**: Hantering av plånboksuppdateringar via WebSocket
- **position_handler.py**: Hantering av positionsuppdateringar via WebSocket
- **subscription_events.py**: Hantering av WebSocket-prenumerationer och events

> **📋 Sammanfattning:** **8 WebSocket handlers** för realtidskommunikation med Bitfinex API.

### Indicators

- **rsi.py**: Implementering av Relative Strength Index (RSI)
- **ema.py**: Implementering av Exponential Moving Average (EMA)
- **atr.py**: Implementering av Average True Range (ATR)
- **adx.py**: Implementering av Average Directional Index (ADX)
- **regime.py**: Regime detection och marknadsregime-analys

> **📋 Sammanfattning:** **6 tekniska indikatorer** för marknadsanalys och strategiutvärdering.

### Utils

- **bitfinex_client.py**: Hjälpklass för Bitfinex API-anrop
- **logger.py**: Konfigurering av loggning
- **advanced_rate_limiter.py**: Avancerad rate limiting med circuit breakers
- **bitfinex_rate_limiter.py**: Bitfinex-specifik rate limiting
- **candle_cache.py**: Cache för candle-data
- **candles.py**: Candle-data hantering och bearbetning
- **feature_flags.py**: Feature flags hantering
- **nonce_manager.py**: Nonce-hantering för API-anrop
- **rate_limiter.py**: Allmän rate limiting
- **token_masking.py**: Masking av känsliga tokens i loggar

> **📋 Sammanfattning:** **10 utility-moduler** för API-hantering, rate limiting, caching och säkerhet.

### Config

- **key_registry.py**: Central nyckel-katalog för Unified Configuration Management
- **priority_profiles.py**: Prioritetsprofiler för konfigurationskällor
- **settings.py**: Grundläggande inställningar och konfiguration
- **startup_config.py**: Startup-konfiguration och initialisering
- **strategy_settings.json**: Strategi-inställningar
- **risk_guards.json**: Risk guards konfiguration
- **order_templates.json**: Ordermallar

> **📋 Sammanfattning:** **8 konfigurationsfiler** för systeminställningar, strategier och riskhantering.

### Models

- **api_models.py**: Pydantic-modeller för API-requests och responses
- **signal_models.py**: Modeller för signaler och trading-signaler

> **📋 Sammanfattning:** **2 modellfiler** med Pydantic-scheman för API och signaler.

### Scraper

Scraper-verktyg för att extrahera Bitfinex API-dokumentation finns i `archived/scraper/`. Dessa verktyg används för att hålla API-dokumentationen uppdaterad och kan behövas för framtida API-versioner.

## API-dokumentation

Detaljerad API-dokumentation nås via OpenAPI-specen:

- `GET /openapi.json` (kan importeras i Lovable/verktyg)
- `GET /docs` (interaktiv Swagger UI)
- Scraper-verktyg för API-dokumentation finns i `docs/scraper/`

## Snabbstart

1. Skapa `.env` från mall och fyll i nycklar (se Konfiguration ovan)

2. Hämta JWT och anropa ett säkrat REST-endpoint (PowerShell-exempel):

```powershell
$body = @{ user_id='frontend_user'; scope='read'; expiry_hours=1 } | ConvertTo-Json
$token = (Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/auth/ws-token -Method Post -ContentType 'application/json' -Body $body).token
$h = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/wallets -Headers $h | ConvertTo-Json -Depth 6
```

3. Testa Socket.IO med testklienten `ws_test.html` som serveras via `/ws`:

- Öppna `http://127.0.0.1:8000/ws`
- Klicka “Get JWT”, därefter “Connect WS” och lyssna på events

## Autentisering (JWT) och åtkomst

- Backend kan kräva JWT för både REST och Socket.IO enligt `AUTH_REQUIRED` i `.env`.
- Hämta en access token via:

  - `POST /api/v2/auth/ws-token` med payload:

    ```json
    { "user_id": "frontend_user", "scope": "read", "expiry_hours": 1 }
    ```

  - Svaret innehåller `access_token` som används i `Authorization: Bearer <token>`.

- Socket.IO: Skicka samma Bearer-token i `Authorization` headern när du ansluter, eller som query `?token=...` i utveckling.

## WebSocket-test (Socket.IO)

- Öppna testklienten på `http://127.0.0.1:8000/ws` (serverar `ws_test.html`).
- Knappen “Get JWT” anropar `POST /api/v2/auth/ws-token` och fyller `Authorization`-headern automatiskt.
- Realtids-händelser (wallet, positions, orders, trades) emit:as som Socket.IO-events.

- Simple/Advanced Mode: använd checkboxen “Visa avancerat” för att dölja/visa avancerade sektioner i `ws_test.html`. Valet sparas i `localStorage` och återställs automatiskt.
- Statusrad: överst i sidan visas en kompakt status (öppet/paus, nästa öppning, Circuit Breaker, WS‑anslutning). Uppdateras vid anslutning, notifieringar och risk‑ändringar.

## Smoke test (kommandon)

1. Hämta JWT och förbered Authorization-header

```powershell
$body = @{ user_id='frontend_user'; scope='read'; expiry_hours=1 } | ConvertTo-Json
$token = (Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/auth/ws-token -Method Post -ContentType 'application/json' -Body $body).token
$h = @{ Authorization = "Bearer $token" }
"Token prefix: $($token.Substring(0,20))..."
```

2. Hämta plånböcker

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/wallets -Headers $h | ConvertTo-Json -Depth 6
```

3. Lägg en liten market-order (sim/ subaccount)

```powershell
$order = @{ symbol='tBTCUSD'; amount='0.0001'; type='EXCHANGE MARKET' } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/order -Method Post -Headers $h -ContentType 'application/json' -Body $order | ConvertTo-Json -Depth 6
```

4. Avbryt alla ordrar (fallback per order finns i backend)

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/orders/cancel/all -Method Post -Headers $h | ConvertTo-Json -Depth 6
```

Lovable-knappar: "Get JWT", "Get Wallets", "Market Buy", "Cancel All" mappas till ovan.

## Risk & handelsfönster (API-exempel)

### PowerShell (Windows)

1. Hämta JWT och sätt Authorization-header

```powershell
$body = @{ user_id='frontend_user'; scope='read'; expiry_hours=1 } | ConvertTo-Json
$token = (Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/auth/ws-token -Method Post -ContentType 'application/json' -Body $body).token
$h = @{ Authorization = "Bearer $token" }
```

2. Uppdatera max trades per dag

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/risk/max-trades -Method Post -Headers $h -ContentType 'application/json' -Body (@{ max_trades_per_day = 5 } | ConvertTo-Json)
```

3. Uppdatera handelsfönster och paus

```powershell
$payload = @{
  timezone = 'Europe/Stockholm'
  windows  = @{
    mon = @(@('08:00','17:00'))
    tue = @(@('08:00','17:00'))
    wed = @(@('08:00','17:00'))
    thu = @(@('08:00','17:00'))
    fri = @(@('08:00','16:00'))
    sat = @()
    sun = @()
  }
  paused = $false
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/risk/windows -Method Post -Headers $h -ContentType 'application/json' -Body $payload
```

4. Hämta riskstatus

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/risk/status -Headers $h | ConvertTo-Json -Depth 6
```

5. Uppdatera max trades per symbol och visa trade‑counter

```powershell
$perSym = 3
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/risk/max-trades-symbol -Method Post -Headers $h -ContentType 'application/json' -Body (@{ max_trades_per_symbol_per_day = $perSym } | ConvertTo-Json)

Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v2/risk/trade-counter -Headers $h | ConvertTo-Json -Depth 6
```

### curl (bash)

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v2/auth/ws-token \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"frontend_user","scope":"read","expiry_hours":1}' | jq -r .token)

curl -s -X POST http://127.0.0.1:8000/api/v2/risk/max-trades \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"max_trades_per_day":5}' | jq .

curl -s -X POST http://127.0.0.1:8000/api/v2/risk/windows \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"timezone":"Europe/Stockholm","windows":{"mon":[["08:00","17:00"]],"tue":[["08:00","17:00"]],"wed":[["08:00","17:00"]],"thu":[["08:00","17:00"]],"fri":[["08:00","16:00"]],"sat":[],"sun":[]},"paused":false}' | jq .

curl -s http://127.0.0.1:8000/api/v2/risk/status -H "Authorization: Bearer $TOKEN" | jq .
```

## Tester

### Köra tester

```bash
python -m pytest tests/
```

### Testfiler

- **test_auth.py**: Testar autentisering mot Bitfinex API
- **test_market_data.py**: Testar hämtning av marknadsdata
- **test_realtime.py**: Testar realtidsfunktionalitet
- **test_strategy.py**: Testar strategiutvärdering

## Utveckling

### Kodstruktur

Projektet följer en modulär struktur där varje modul har ett specifikt ansvarsområde:

- **services/**: Kärntjänster för trading-funktionalitet
- **rest/**: REST API-implementation
- **ws/**: WebSocket-implementation
- **indicators/**: Tekniska indikatorer
- **utils/**: Hjälpfunktioner och verktyg
- **tests/**: Testfiler
- **config/**: Konfigurationsfiler
- **models/**: Datamodeller
- **scraper/**: Web scraping-funktionalitet

### Exempel (arkiverade)

Exempel-skript har flyttats till `docs/legacy/examples/` för referens och är inte en del av produktion.

### Bidra

## CI (GitHub Actions)

En enkel CI kör lint och tester på push/PR.

Skapa `.github/workflows/ci.yml` i repo-roten:

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: tradingbot-backend
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
          cache-dependency-path: "tradingbot-backend/requirements.txt"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest mypy bandit

      - name: Type-check (mypy)
        run: |
          mypy --ignore-missing-imports --install-types --non-interactive . || true

      - name: Security (bandit)
        run: |
          bandit -q -r . || true

      - name: Lint (importable modules)
        run: python -c "import sys; import pkgutil; print('OK')"

      - name: Run tests
        env:
          AUTH_REQUIRED: "False"
        run: pytest -q
```

Notera att `AUTH_REQUIRED=False` under test förenklar körningen. Justera vid behov.


## Orderflaggor (Reduce-Only/Post-Only)

- **Reduce-Only**: Säkerställer att en order endast minskar en befintlig position, aldrig ökar eller vänder den. Praktiskt för att stänga eller delstänga positioner utan risk att oavsiktligt öppna motsatt riktning. I backend stöds flaggan i modellerna och används bl.a. vid "Stäng position" (skickar MARKET med `reduce_only=true`).

- **Post-Only**: Ordern läggs endast om den kan bli en maker-order (ligga i orderboken). Om den annars skulle matchas direkt som taker avbryts den i stället. Används för att undvika taker-avgifter och för att säkerställa likviditetspostning. Relevant främst för LIMIT-ordrar.

Användning i API (exempel för bracket):

```json
{
  "symbol": "tBTCUSD",
  "amount": "0.01",
  "side": "buy",
  "entry_type": "EXCHANGE LIMIT",
  "entry_price": "30000",
  "post_only": true,
  "reduce_only": false
}
```

Observera att `post_only` ignoreras för MARKET-ordrar (gäller LIMIT). `reduce_only` kan användas för att säkra exits.

## Backtest & Heatmap

- Backtest-endpoint: `POST /api/v2/strategy/backtest` med fält `symbol`, `timeframe`, `limit` och automatisk lokal tidszon via UI.
- Returnerar bl.a.: `final_equity`, `winrate`, `max_drawdown`, `sharpe`, `distribution`, `equity_curve`, `heatmap_return` (alias `heatmap`), `heatmap_winrate` och `heatmap_counts`.
- Heatmap visar genomsnittlig avkastning per trade (return-heatmap). Winrate-heatmap visar andel vinnare per cell. UI kan utökas med toggle vid behov.

## Ordermallar

- Endpoints:
  - GET `/api/v2/order/templates` – lista mallar
  - GET `/api/v2/order/templates/{name}` – hämta en mall
  - POST `/api/v2/order/templates` – spara/uppdatera mall
  - DELETE `/api/v2/order/templates/{name}` – ta bort mall
- Lagring: `config/order_templates.json` (tålig mot tom/korrupt fil)
- UI (ws_test.html):
  - "Spara mall (från Bracket)" – sparar aktuell bracket‑konfiguration under angivet namn
  - "Visa mallar" – listar och erbjuder "Använd" som fyller bracket‑fälten

1. Forka repositoryt
2. Skapa en feature branch (`git checkout -b feature/amazing-feature`)
3. Commita dina ändringar (`git commit -m 'Add some amazing feature'`)
4. Pusha till branchen (`git push origin feature/amazing-feature`)
5. Öppna en Pull Request

## Cursor Prompts

Se `cursor_prompts.md` för en svensk systemprompt och tio återanvändbara Cursor‑mallar (bugfix, REST/WS‑endpoint, strategi/indikator, ordervalidering, tester, dokumentation, refaktorering, scraper, CI). Mallarna är anpassade till projektets modulstruktur (`services`, `rest`, `ws`, `indicators`, `utils`) och Bitfinex API v2 (REST + WS, autentiserat).

## Arkitektur: MarketDataFacade, SignalService, RiskPolicyEngine, Circuit Breakers

### MarketDataFacade

- En enhetlig datatjänst som prioriterar WebSocket-data med REST fallback och gemensam cache.
- API (urval):
  - `get_ticker(symbol)`
  - `get_candles(symbol, timeframe, limit, force_fresh=False)`
  - `get_configs_symbols()` och `get_currency_symbol_map()` (proxy via REST)
  - `parse_candles_to_strategy_data(candles)` (helper som använder `utils.candles`)

### SignalService

- Enhetlig signal-orkestrering som kan kombinera deterministiska heuristiker med sannolikhetsmodell.
- Returnerar `SignalScore` med fält: `recommendation`, `confidence`, `probability`, `source`, `features`.
- Används nu i REST där lokala confidence/prob tidigare beräknades (t.ex. watchlist, regime-all).

### RiskPolicyEngine

- Samlar RiskGuards och TradeConstraintsService i en tydlig policy:
  - RiskGuards (globala vakter: max daily loss, kill-switch, exposure limits)
  - TradeConstraintsService (trading window, dagliga limit och cooldown via TradeCounter/TradingWindow)
- API (urval): `evaluate(symbol, amount, price)`, `record_trade(symbol)`, `status()`

### Circuit Breakers

- Två separata kretsbrytare i logg/metrics:
  - TradingCircuitBreaker (handel) – pausar handel vid felspikar i risk/routing.
  - TransportCircuitBreaker (nätverk/REST) – öppnas per endpoint vid 429/5xx och återställer automatiskt.
- Exponeras via Prometheus-metrics: `tradingbot_trading_circuit_breaker_active` och `tradingbot_transport_circuit_breaker_active` (bakåtkompatibelt `tradingbot_circuit_breaker_active`).

### Rate limiting

Backend använder en avancerad token‑bucket limiter per endpoint‑typ med semaforer.
Du kan mönster‑klassificera endpoints via `RATE_LIMIT_PATTERNS` i `.env`:

```
RATE_LIMIT_PATTERNS=^auth/w/=>PRIVATE_TRADING;^auth/r/positions=>PRIVATE_ACCOUNT;^auth/r/wallets=>PRIVATE_ACCOUNT;^auth/r/info/margin=>PRIVATE_MARGIN;^(ticker|candles|book|trades)=>PUBLIC_MARKET
```

Detta styr både token‑bucket och concurrency caps per endpoint‑typ, samt exporteras som metrics (tokens tillgängliga och utilization%).

### Runtime‑konfiguration (hot‑reload)

Backend stödjer enkla runtime‑overrides för utvalda nycklar via REST:

```
GET  /api/v2/runtime/config           # listar aktiva overrides
POST /api/v2/runtime/config { "values": { "WS_TICKER_STALE_SECS": 5, "CANDLE_STALE_SECS": 120 } }
```

Stödda nycklar just nu:
- `WS_TICKER_STALE_SECS`: override för hur länge WS‑ticker anses färsk (sek)
- `CANDLE_STALE_SECS`: override för candle‑cache staleness (sek)

### Metrics: marknadsdata‑andelar

I `/metrics` exponeras aggregerade procentandelar för datakällor:
- `tradingbot_marketdata_cache_percent`
- `tradingbot_marketdata_rest_percent`
- `tradingbot_marketdata_ws_percent`

Använd dem för paneler i t.ex. Grafana för att följa cache‑träffar, REST‑fallbacks, och WS‑andel över tid.

## Transport-limiter: circuit breaker state (_cb_state)

Transport‑nivån (REST) använder en enkel circuit breaker per endpoint, hanterad av `utils/advanced_rate_limiter.py`.

- Nycklar: `fail_count`, `open_until` (epoch‑sek), `last_failure`.
- `can_request(endpoint)`: True när `now >= open_until`.
- `time_until_open(endpoint)`: sekunder kvar tills circuit stänger.
- `note_failure(endpoint, status_code, retry_after)`: ökar `fail_count`, sätter `open_until` via `Retry-After` eller exponentiell backoff, och signalerar Unified CB.
- `note_success(endpoint)`: nollar state och signalerar återhämtning.

Felsök:

- `GET /api/v2/debug/rate_limiter` visar limiter‑stats och `time_until_open` för vanliga endpoints.
- Se även `services/unified_circuit_breaker_service.py` för övergripande CB‑status.

# AI Change: Added Deprecation & Sunset-plan (Agent: Cursor, Date: 2025-09-15)

## Deprecation & Sunset-plan

Denna sektion beskriver vilka legacy‑endpoints och funktioner som är markerade för avveckling, hur klienter ska migrera, samt vilka datum som gäller. Alla avvecklingar följer HTTP‑headersna `Deprecation`, `Sunset` och `Link` för att guida klienter.

- **Risk V1/V2 routes**: Använd unified risk‑endpoints under `/api/v2/risk/unified/*`.
  - Legacy: `/api/v2/risk/status`, `/api/v2/risk/windows`, `/api/v2/risk/pause`, `/api/v2/risk/resume`, och alla `/api/v2/v2/risk/*` varianter.
  - Status: Avvecklade i kodbasen; unified används. Klienter ska migrera omgående.

- **Validation: legacy `/prob/validate*`**: Använd `/api/v2/validation/probability`.
  - Legacy: `POST /api/v2/prob/validate`, `POST /api/v2/prob/validate/run` (svarar med `Deprecation`/`Sunset`/`Link`).
  - Sunset: 2026‑01‑01 00:00:00Z. Efter datumet tas legacy bort.
  - Migration: Byt till `POST /api/v2/validation/probability` och uppdatera schema enligt `services.validation_service`.

- **Metrics**: Använd JSON‑sammanfattning.
  - Legacy: `GET /metrics` (Prometheus text) finns kvar men UI ska använda `GET /api/v2/metrics/summary`.
  - Plan: När UI är helt migrerad kan `GET /metrics` endast exponeras för Prometheus‑scrape.

- **MCP**: Helt borttagen.
  - Legacy: alla `/api/v2/mcp/*` endpoints och MCP‑klienter.
  - Migration: Tokenhämtning sker via `POST /api/v2/auth/ws-token`. UI och scripts uppdaterade.

- **TransportCircuitBreaker**: Funktionellt ersatt av `AdvancedRateLimiter` + `UnifiedCircuitBreakerService`.
  - Legacy‑anrop ur REST‑moduler borttagna. Klassen kan tas bort när inga referenser återstår.

- **WS pool namn/prefix‑hygien**:
  - CI blockerar nu `/api/v2/v2`‑mönster i routerfiler med `APIRouter(prefix="/api/v2")`.

- **Unified Signals SoT**:
  - SoT: `services/unified_signal_service.py` (`unified_signal_service`).
  - Legacy: `services/signal_service.py` innehöll dubblettklass; nu endast alias till SoT. All ny utveckling ska importera `from services.unified_signal_service import unified_signal_service`.

### Avvecklingsprocess

1. Märk legacy‑endpoints med `Deprecation`, `Sunset`, `Link` och instrumentera `legacy_endpoints_total{endpoint=...}`.
2. Migrera UI/klienter till ersättning och verifiera i staging.
3. Efter sunset‑datum: ta bort legacy‑endpoints/kod.
4. Uppdatera denna sektion och changelog.

### Spårning och uppföljning

- Metrik: `legacy_endpoints_total{endpoint}` används för att följa kvarvarande trafik.
- Dashboard: SystemPanel visar `/api/v2/metrics/summary` där legacy‑användning kan synas i counters.

## 🔧 Unified Configuration Management System

### Översikt

Det nya Unified Configuration Management System v2.0 löser konfigurationskonflikter och ger enhetlig hantering av alla konfigurationskällor.

### Komponenter

- **KeyRegistry** (`config/key_registry.py`) - Central nyckel-katalog med schema och metadata
- **ConfigStore** (`services/config_store.py`) - Central lagring med SQLite/Redis och pub/sub
- **ConfigCache** (`services/config_cache.py`) - Per-process cache med invalidation
- **UnifiedConfigManager** (`services/unified_config_manager.py`) - Huvudklass med kontextuell prioritet
- **ConfigValidator** (`services/config_validator.py`) - Validering med key registry integration
- **RollbackService** (`services/rollback_service.py`) - Snapshots, rollback och staged rollout
- **ConfigObservability** (`services/config_observability.py`) - Metrics, events och monitoring

### API Endpoints

- `GET /api/v2/config/keys` - Lista alla konfigurationsnycklar
- `GET /api/v2/config/{key}` - Hämta konfigurationsvärde
- `POST /api/v2/config/{key}` - Sätt konfigurationsvärde
- `POST /api/v2/config/validate` - Validera konfiguration
- `GET /api/v2/config/effective` - Hämta effektiv konfiguration
- `GET /api/v2/config/stats` - Konfigurationsstatistik

### Prioritet

1. **Runtime Config** (högsta - dashboard-ändringar)
2. **Feature Flags** (feature toggles)
3. **Settings** (miljövariabler)
4. **Config Files** (JSON-filer)

## 🛡️ Kodkvalitet & Säkerhet

### Automatiserade Verktyg

```powershell
# Formatering (Black)
python -m black .

# Linting (Ruff)
python -m ruff check . --fix

# Säkerhet (Bandit)
python -m bandit -r . -c bandit.yaml

# Tester (Pytest)
python -m pytest tests/ -v

# Type checking (MyPy)
python -m mypy . --ignore-missing-imports
```

### CI/CD Pipeline

- **GitHub Actions:** Automatisk kodkvalitetskontroll
- **Pre-commit hooks:** Automatisk formatering och linting
- **Security scanning:** Bandit för säkerhetsproblem
- **Test coverage:** Pytest med omfattande test suite

### Konfigurationsfiler

- `pyproject.toml` - Ruff, Black och isort konfiguration
- `bandit.yaml` - Säkerhetslinter konfiguration
- `pytest.ini` - Test konfiguration
- `.pre-commit-config.yaml` - Pre-commit hooks
