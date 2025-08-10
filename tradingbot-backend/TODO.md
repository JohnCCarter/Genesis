# TODO - Genesis Trading Bot Backend

Single-user roadmap (Måste → Nice-to-have → Backlog). Fokus: stabil drift, notifieringar, enkel prestandahistorik.

## Måste (single-user scope)

- [x] Circuit breaker (snabb paus vid felspikar)
  - [x] Räkna fel på kritiska endpoints (order, ws-auth) i rullande fönster; auto `pause`
  - [x] WS-notifiering vid paus; manuell `resume` via API (`/api/v2/risk/circuit/reset`)
- [x] Auto-handel kontroll (per symbol)
  - [x] Endpoints: `/auto/start`, `/auto/stop`, `/auto/status`, `/auto/stop-all`, `/auto/start-batch`
  - [x] UI: Snabbstart per symbol, Starta batch, Stoppa alla
- [x] Per‑symbol strategiinställningar
  - [x] GET/POST `/strategy/settings?symbol=...` (vikter + perioder)
  - [x] Strategin och position‑size använder symboloverride
- [x] Notifieringar
  - [x] Socket.IO – order success/fail, risk events, CB
  - [x] Telegram (valfritt): ENV (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), enkel service
- [x] PnL & Performance (minimum)
  - [x] Realized PnL per symbol (USD‑konverterad) + fees (backend)
  - [x] Visa realized_usd i UI (perf detail‑panel)
  - [x] Equity endpoint + sparklines (UI)
  - [x] Dagliga snapshots (equity) – backend & scheduler (UI: knapp + sparkline)
  - [x] Snapshots: visa realized/dagens förändring i UI
- [x] Tester (minimum)

  - [x] Orderflöde (market/limit) + notifiering (grund)
  - [x] RiskManager grunder (pause/window)
  - [x] BracketManager länkning (register)
  - [x] TradingWindow save_rules (persistens och reload)
  - [ ] Tester – Circuit Breaker (risk_manager): öppna/paus, notifiering, reset
  - [x] README – snabbstart, AUTH_REQUIRED/JWT, viktiga endpoints (uppdaterad med nya endpoints och UI)

- [x] WS privata flöden (kanal 0)
  - [x] on/ou/oc/te/tu registrerade i `ws/manager.py`
  - [x] DMS aktiveras vid `auth`; tester lagda

## Nice-to-have

- [ ] Orderflaggor du faktiskt använder (t.ex. Reduce‑Only; Post‑Only vid behov)
- [ ] Risk-baserat orderpanel (UI): % av balans + ATR-beräkning som förhandsvisning
- [ ] Bracket/OCO förbättringar
  - [x] Robust parsing av Bitfinex‑svar (list/dict) för entry/SL/TP
  - [ ] Partial fills (step sizing, cleanup)
  - [ ] GID-grouping och återhämtning efter reconnect
- [ ] Enkel rate-limit på känsliga endpoints

## Backlog

- [ ] UI: Scheduling/kalender + holidays‑API
- [ ] Metrics/observability – avancerade labels (symbol/side/type) och latens
- [ ] Backtest-fördjupning
  - [ ] Lokal candle-cache (SQLite) + history fetcher
  - [ ] Samma simulator som live (Strategy + RiskManager)
  - [x] Rapporter: Sharpe, winrate, max DD, distribution, heatmap
- [ ] Docker (Dockerfile + compose, healthchecks)
- [ ] API/UI: Watchlist MTF-preview, templates import/export/hotkeys

## Klart i UI

- [x] Positionsvy med fler kolumner + "Stäng position" (reduce‑only)
- [x] Exchange (syntetisk) positionsvy baserad på wallets/trades
- [x] Konto‑växel (Exchange/Margin) i order- och bracket‑panel (automatiskt typbyte)
- [x] Ordersmallar: route‑krock fixad – UI använder `GET /api/v2/orders/templates` (tidigare konflikt med `/api/v2/order/{order_id}`)
- [x] Simple/Advanced‑läge i `ws_test.html` (sparas i `localStorage`)
- [x] Statusrad i UI (open/paused/next_open/CB/WS‑status)
- [x] Per‑symbol max‑trades input + "Visa trade‑counter" tabell

---

Updated as we go.
