## Frontend TODO

- Risk Panel

  - Ersätt lokala helpers med `TB.*` (headers, fetch, toast, symbol‑map, format)
  - Visa WS‑status (Connected/Auth) i Quick Trade
  - Gör varje Avancerat‑del hopfällbar (Prob/Validation/Feature‑logg/Strategy/Risk)
  - Lägg icke‑blockerande knapp‑spinners för Preview/Trade/Validate/Retrain
  - Flytta inline‑stilar till `risk-panel.css`

- WS Test

  - Kanal‑väljare (ticker/trades/candles) + timeframe för candles
  - Visa aktiva subs via `/api/v2/ws/pool/status` och möjliggör targeted Unsub

- Shared

  - Utöka `TB.fetchJsonWithTimeout` med enkel felrendering till mål‑`pre`
  - Lägg liten util för state‑persistens (get/set JSON i localStorage med prefix)

- Observability

  - Lägg UI‑visning av senaste fel i Risk (kort lista)
  - Små statusbadges (grönt/rött) för toggles och WS‑status

- Städ
  - Ta bort legacy‑filer när nya sidor är godkända (backup finns i `frontend/_backup/`)

### Backend‑hooks (för frontend‑kontroller)

- Respektera `validation_on_start` vid startup (stoppa warm‑up om av)
- (Valfritt) Auto‑subscribe när WS Strategy togglas till On (använd `WS_SUBSCRIBE_SYMBOLS`)
