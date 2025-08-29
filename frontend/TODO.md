## Frontend TODO

- Risk Panel

  - [x] Ersätt lokala helpers med `TB.*` (headers, fetch, toast, symbol‑map, format)
  - [x] Visa WS‑status (Connected/Auth) i Quick Trade
  - [x] Gör varje Avancerat‑del hopfällbar (Prob/Validation/Feature‑logg/Strategy/Risk)
  - [x] Lägg icke‑blockerande knapp‑spinners för Preview/Trade/Validate/Retrain
  - [x] Flytta inline‑stilar till `risk-panel.css`

- WS Test

  - [x] Kanal‑väljare (ticker/trades/candles) + timeframe för candles
  - [x] Visa aktiva subs via `/api/v2/ws/pool/status` och möjliggör targeted Unsub

- Shared

  - [x] Utöka `TB.fetchJsonWithTimeout` med enkel felrendering till mål‑`pre`
  - [x] Lägg liten util för state‑persistens (get/set JSON i localStorage med prefix)

- Observability

  - [x] Lägg UI‑visning av senaste fel i Risk (kort lista)
  - [x] Små statusbadges (grönt/rött) för toggles och WS‑status

- Dashboard (React/Vite)

  - [x] StatusCard.tsx + Toggles.tsx
    - [x] Poll `GET /api/v2/ws/pool/status` var 5s
    - [x] Läs `GET /api/v2/ui/capabilities` för att styra synlighet/labels
  - [x] QuickTrade.tsx
    - [x] Inputs: symbol/side/amount/price, persist i localStorage
    - [x] Preview: `GET /api/v2/market/ticker/:symbol` (notional + fee)
    - [x] Trade: `POST /api/v2/order`, visa svar i `<pre>`
  - [x] ValidationPanel.tsx
    - [x] Inputs: symbol/timeframe/limit/max_samples
    - [x] `POST /api/v2/prob/validate/run`, visa JSON i `<pre>`
  - [x] DebugPage.tsx (fas 2)
    - [x] WS sub/unsub (ticker/trades/candles), visa aktiva subs
    - [ ] Privat callbacks‑logg (orders/positions) + Clear/Pause
    - [ ] (Valfritt) enkel candles‑graf
  - [x] Routing/struktur
    - [x] `src/pages/Dashboard.tsx` som monterar komponenterna
    - [x] `src/lib/api.ts` (använd `VITE_API_BASE`)
  - [x] UX
    - [x] Toaster/felhantering, disable/spinner på knappar

- Städ
  - [ ] Ta bort legacy‑filer när nya sidor är godkända (backup finns i `frontend/_backup/`)

### Backend‑hooks (för frontend‑kontroller)

- [x] Respektera `validation_on_start` vid startup (stoppa warm‑up om av)
- [x] (Valfritt) Auto‑subscribe när WS Strategy togglas till On (använd `WS_SUBSCRIBE_SYMBOLS`)
