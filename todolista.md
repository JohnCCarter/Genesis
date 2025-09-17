### Genesis Trading Bot – TODO & Status

Uppdaterad: 2025-09-17

#### Utfört idag

- **HTTP‑klient livscykel**: Infört lazy per‑event‑loop `httpx.AsyncClient` och säker stängning

  - `services/http.py`: `get_async_client()`, `close_http_clients()`, uppdaterade `aget/apost`
  - `main.py`: stänger via `close_http_clients()` vid shutdown
  - `services/exchange_client.py`: använder `get_async_client()`

- **Orderflöde och symboler**:

  - `rest/order_validator.py`: accepterar symboler som `SymbolService.listed()` anser giltiga
  - `rest/routes.py` (`/api/v2/order`): symbol‑resolution före validering; validerar på resolverad payload
  - Verifierat tADAUSD 50 buy (EXCHANGE MARKET) med Dry Run av: success=true via WS‑fallback

- **WS order‑ops**:

  - `rest/routes.py` (`/api/v2/ws/orders/ops`): korrekt meddelandeformat `[0, "on", null, payload]`
  - Symbol‑resolution för `on`‑ops; Dry Run simulerar svar

- **Runtime toggles (E2E delvis)**:

  - `/api/v2/mode/dry-run` GET/POST testat (på/av) och ordersvar kontrollerat

- **Dokumentation**:

  - `tradingbot-backend/ARCHITECTURE.md` skapad (arkitektur, call flows, monitoring)
  - `tradingbot-backend/Struktur.md` trimmad för felsökningschecklistor

- **Frontend (kort)**:
  - `Dashboard.tsx`: `activeTab` persisteras i `localStorage`; enklare conditional rendering

#### Kvar att göra (prioritet)

- **Steg 4 – WS‑orderflöde (ren WS)**: Skicka `on` direkt över WS och verifiera att “invalid (sym=?)” är borta
- **Steg 5 – REST↔WS‑separation**: Flytta `/api/v2/ws/*` från REST till riktiga WS‑handlers
- **Steg 8 – Runtime toggles (komplettera)**: Testa övriga toggles (WS‑connect, prob‑model, autotrade, scheduler)
- **Steg 10 – Följa upp fel**: Bitfinex 500 och trades‑history JSON/parse‑fel
- **WS‑koppling i UnifiedSignalService**: Implementera `set_websocket_service(ws)` eller ta bort anropet i `main.py`
- **Modellfiler**: Lägg till/re‑träna för ETH/DOT/ADA/5m eller stäng av validering där det krävs
- **REST 500‑felparsning**: Förbättra 500‑payloadhantering i `rest/auth.place_order`
- **Settings‑singleton**: Säkerställ inga direkta `Settings()` instanser kvar
- **Frontend toggles**: Dashboard ska läsa/sätta `/mode/*` och spegla `runtime_config`
- **Uvicorn reload**: Utöka `--reload-exclude` i `dev-backend.ps1` vid behov
- **Enhetstester**: symbol‑mappning, Dry Run blockerar WS‑fallback, candles/timeframes, `/mode/*`

#### Snabbtest (PowerShell)

```powershell
# Health
curl -sS http://127.0.0.1:8000/health

# Dry Run → av
curl -sS -H "Authorization: Bearer dev" -H "Content-Type: application/json" `
  -d '{"enabled":false}' http://127.0.0.1:8000/api/v2/mode/dry-run

# REST‑order (tADAUSD 50 buy, MARKET)
curl -sS -H "Authorization: Bearer dev" -H "Content-Type: application/json" `
  -d '{"symbol":"tADAUSD","amount":"50","type":"EXCHANGE MARKET","side":"buy"}' `
  http://127.0.0.1:8000/api/v2/order
```

#### Referenser

- Struktur: [tradingbot-backend/Struktur.md](tradingbot-backend/Struktur.md)
- Arkitektur: [tradingbot-backend/ARCHITECTURE.md](tradingbot-backend/ARCHITECTURE.md)
