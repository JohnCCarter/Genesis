📊 Felsökningsguide - Genesis Trading Bot

Obs: Arkitekturöversikt och systemflöden finns i `ARCHITECTURE.md`.

---

🛠️ Extra felsökningspunkter

1) Candles‑URL per timeframe
- Symptom: Loggar visar anrop som `candles/trade:1m,5m:tBTCUSD/hist`.
- Orsak: Kombinerade timeframes i en URL accepteras inte av Bitfinex.
- Åtgärd: Iterera per timeframe (först `1m`, sedan `5m`) och gör separata anrop.

2) WS‑koppling i UnifiedSignalService
- Symptom: Startup‑varning om att `UnifiedSignalService` saknar `set_websocket_service`.
- Åtgärd: Implementera `set_websocket_service(ws)` eller ta bort kopplingsanropet i `main.py`.

3) REST har WS‑endpoints
- Symptom: `/api/v2/ws/*` endpoints ligger i REST.
- Åtgärd: Flytta WS‑specifika operationer till Socket.IO/WS‑händelser.

4) Modellfiler för fler symboler/timeframes
- Symptom: Prob‑signaler 0.0 för ETH/DOT/ADA/5m.
- Åtgärd: Lägg till modeller eller inaktivera validering/retrain tills filer finns.

5) Bitfinex REST 500 vid order
- Åtgärd: Parsea 500‑payload i `rest/auth.place_order`, verifiera minsta orderstorlek och API‑permissions.

6) Singelton‑disciplin för Settings
- Åtgärd: Ersätt alla `Settings()` med `from config.settings import settings`.

7) Frontend toggles och runtime_config
- Åtgärd: Dashboard ska läsa/sätta `/api/v2/mode/*` och spegla `runtime_config`.

8) Uvicorn reload‑stabilitet (Windows)
- Åtgärd: Utöka `--reload-exclude` (ex. `logs/*`, `*.db`) i `dev-backend.ps1`.

9) Tester att lägga till
- Symbol‑mapping (tTEST → effektiv `tBTCUSD`) i REST orderflödet.
- DRY‑RUN blockerar WS‑fallback i order/update/bracket.
- Candles per timeframe (1m, 5m separata anrop).
- `/mode/*` speglar `runtime_config` end‑to‑end.

10) Endpoint‑separation (översikt)
- REST: order, wallets, positions, signals, candles (snapshots).
- WebSocket: live subscriptions (ticker/candles/trades), realtidsorder, privata events.

---

🧪 Felsökningssekvens – Praktisk checklista

1) Bekräfta konfigurationer
- Kontrollera `.env`: `DRY_RUN_ENABLED`, `PROB_MODEL_ENABLED`, `PROB_AUTOTRADE_ENABLED`, `TRADING_PAUSED`, `WS_CONNECT_ON_START`, `SCHEDULER_ENABLED`.
- Starta backend och läs startup‑loggarna.

2) API‑toggles speglar runtime_config
- `GET /api/v2/mode/dry-run`, `GET /api/v2/mode/autotrade`, `GET /api/v2/mode/ws-strategy`.
- Om skillnad: `POST /api/v2/mode/*` och verifiera igen.

3) REST‑orderflöde (ren REST)
- `POST /api/v2/order` med `tBTCUSD`, `DRY_RUN_ENABLED=False`.
- Bekräfta i logg: REST submit, ingen WS fallback.

4) WS‑orderflöde (ren WS)
- Säkerställ WS connected + authenticated i logg.
- Skicka `[0, "on", null, payload]` via WS‑verktyg.
- Verifiera `on`, `ou`, `oc` callbacks i WS‑logg.

5) Separation kontroll
- REST: notera att `/api/v2/ws/*` är felplacerade, ignorera tills refaktorering.
- WS: WSFirstDataService får använda REST‑fallback.

6) Marknadsdata
- `GET /api/v2/watchlist` → data ska komma (WS först, REST fallback).
- Logg: `marketdata.source=ws` eller `marketdata.source=rest reason=ws_timeout`.

7) Prob‑modellen
- `PROB_MODEL_FILE` korrekt; `/mode/prob-model` speglas i `prob_model.enabled`.
- `GET /api/v2/signals/live` > 0.0 vid aktiv modell.

8) Runtime‑toggles E2E
- `POST /api/v2/mode/dry-run { enabled }` → `GET` → lägg order → se effekt.
- `POST /api/v2/mode/autotrade { enabled }` → `GET` → se reaktion i logik.

9) WS‑subscriptions
- `POST /api/v2/ws/subscribe` → ticker/candles/trades.
- Kontrollera loggar och Socket.IO events i frontend.

10) Uppföljning av fel
- Bitfinex 500: symbol, storlek, permissions, förbättra felparsering.
- "invalid (on)": ska vara löst (arrayformat).
- Trades history 200 + JSON‑fel: se `rest/order_history.py` förbättrade loggar.


