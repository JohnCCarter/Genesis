# Genesis Trading Bot - Backend

Detta är backend-delen av Genesis Trading Bot, en plattform för automatiserad trading med Bitfinex API.

## Innehåll

1. [Översikt](#översikt)
2. [Installation](#installation)
3. [Konfiguration](#konfiguration)
4. [Telegram-notiser](#telegram-notiser)
5. [Moduler](#moduler)
6. [API-dokumentation](#api-dokumentation)
7. [Tester](#tester)
8. [Utveckling](#utveckling)
9. [Orderflaggor (Reduce-Only/Post-Only)](#orderflaggor-reduce-onlypost-only)
10. [Backtest & Heatmap](#backtest--heatmap)
11. [CI (GitHub Actions)](#ci-github-actions)
12. [Arkitektur: MarketDataFacade, SignalService, RiskPolicyEngine, Circuit Breakers](#arkitektur-marketdatafacade-signalservice-riskpolicyengine-circuit-breakers)

## Översikt

Genesis Trading Bot är en plattform för automatiserad trading med Bitfinex API. Backend-delen hanterar:

- Autentisering mot Bitfinex API (REST och WebSocket)
- Hämtning av marknadsdata
- Teknisk analys och strategiutvärdering
- Orderhantering
- Positionshantering
- Realtidsuppdateringar via WebSocket
- Schemaläggning av strategier
- Loggning och felhantering

## Installation

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

```
BITFINEX_API_KEY=din_api_nyckel
BITFINEX_API_SECRET=din_api_hemlighet
BITFINEX_API_URL=https://api.bitfinex.com/v2

# WebSocket-nycklar (om separata nycklar används för WS)
BITFINEX_WS_API_KEY=din_ws_api_nyckel
BITFINEX_WS_API_SECRET=din_ws_api_hemlighet

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

### Services

- **bitfinex_data.py**: Hanterar hämtning av marknadsdata från Bitfinex REST API
- **bitfinex_websocket.py**: Hanterar realtidsdata via Bitfinex WebSocket API
- **strategy.py**: Implementerar tradingstrategier baserade på tekniska indikatorer
- **realtime_strategy.py**: Hanterar realtidsutvärdering av strategier
- **scheduler.py**: Schemaläggning av strategiutvärderingar och andra uppgifter
- **trading_integration.py**: Integrerar olika delar av systemet för komplett tradingfunktionalitet

### REST API

- **auth.py**: Autentisering mot Bitfinex REST API
- **routes.py**: FastAPI-routes för backend API
- **wallet.py**: Hantering av plånboksinformation
- **positions.py**: Hantering av positioner
- **positions_history.py**: Hantering av positionshistorik
- **margin.py**: Hantering av margin-information
- **order_history.py**: Hantering av orderhistorik
- **active_orders.py**: Hantering av aktiva ordrar
- **order_validator.py**: Validering av orderparametrar

### WebSocket

- **auth.py**: Autentisering mot Bitfinex WebSocket API
- **manager.py**: Hantering av WebSocket-anslutningar
- **order_handler.py**: Hantering av ordrar via WebSocket
- **wallet_handler.py**: Hantering av plånboksuppdateringar via WebSocket
- **position_handler.py**: Hantering av positionsuppdateringar via WebSocket

### Indicators

- **rsi.py**: Implementering av Relative Strength Index (RSI)
- **ema.py**: Implementering av Exponential Moving Average (EMA)
- **atr.py**: Implementering av Average True Range (ATR)

### Utils

- **bitfinex_client.py**: Hjälpklass för Bitfinex API-anrop
- **logger.py**: Konfigurering av loggning

### Scraper

Scraper-verktyg för att extrahera Bitfinex API-dokumentation finns i `docs/scraper/`. Dessa verktyg används för att hålla API-dokumentationen uppdaterad och kan behövas för framtida API-versioner.

### Models

- **api_models.py**: Pydantic-modeller för API-requests och responses

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
