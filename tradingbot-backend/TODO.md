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
  - [x] Tester – Circuit Breaker (risk_manager): öppna/paus, notifiering, reset
  - [x] README – snabbstart, AUTH_REQUIRED/JWT, viktiga endpoints (uppdaterad med nya endpoints och UI)

- [x] WS privata flöden (kanal 0)

  - [x] on/ou/oc/te/tu registrerade i `ws/manager.py`
  - [x] DMS aktiveras vid `auth`; tester lagda

- [x] WS‑orders (snabb vinst i drift)

  - [x] Endpoints: `/api/v2/ws/order/update`, `/api/v2/ws/orders/cancel-multi`, `/api/v2/ws/orders/ops`
  - [x] UI‑knappar i `ws_test.html` för ou/oc‑multi/ops
  - [x] REST↔WS‑fallback i `/order` (submit) och `/order/update` (update)

- [x] Symbolhantering och validering (WS‑först, REST fallback)
  - [x] Central `SymbolService` med live `/conf` parlistor och alias
  - [x] Filtrera bort icke‑listade par i API (`/market/symbols`, `/market/watchlist`)
  - [x] Startup WS‑subscribe filtrerar bort icke‑listade par
  - [x] `OrderValidator` använder configs/fallback (scraper avstängd, INFO‑logg)

## Nice-to-have

- [x] Orderflaggor du faktiskt använder (t.ex. Reduce‑Only; Post‑Only vid behov)
- [x] Risk-baserat orderpanel (UI): % av balans + ATR-beräkning som förhandsvisning
  - [x] Minimal UI-prototyp `risk_panel.html` som anropar `/api/v2/risk/position-size`
  - [x] UI‑puts: symbol‑dropdown (från `/market/symbols`), risk‑slider, KPI (size/alloc/price/quote total)
  - [x] Ta bort Core‑mode block från panelen (mindre brus)
- [ ] Bracket/OCO förbättringar
  - [x] Robust parsing av Bitfinex‑svar (list/dict) för entry/SL/TP
  - [x] Partial fills (step sizing, cleanup)
  - [x] GID-grouping och återhämtning efter reconnect
  - [x] Enkel rate-limit på känsliga endpoints
  - [x] Enkel lokal candle‑cache (SQLite) – fill‑on‑demand cache (OBS: uppgraderas senare till cache + history fetcher)
  - [x] Cache‑admin endpoints (stats/clear)
  - [x] Bracket‑state reset endpoint
  - [x] Nätverksresiliens: retry/backoff + timeouts
  - [x] Bracket‑healing: vid misslyckad REST‑submit för SL/TP försök WS `on`; registrera grupp ändå och låt privata callbacks slutföra länkning

## Backlog

- [ ] UI: Scheduling/kalender + holidays‑API
- [x] Metrics/observability – avancerade labels (symbol/type/status) via labeled counters
- [ ] Backtest-fördjupning
  - [x] Lokal candle-cache (SQLite) + history fetcher (backfill endpoint)
  - [ ] Samma simulator som live (Strategy + RiskManager) — deferred (on hold)
  - [x] Rapporter: Sharpe, winrate, max DD, distribution, heatmap
- [x] Docker (Dockerfile + compose, healthchecks)
- [ ] API/UI: Watchlist MTF-preview, templates import/export/hotkeys
  - [x] Templates import/export endpoints
  - [x] Watchlist MTF-preview (1m + 5m)
  - [ ] Hotkeys (deferred)

### Nästa steg (prioriterade)

- [x] REST (auth) fler endpoints: funding/transfer/movements
- [x] Marginstatus i UI (källa: WS live / REST fallback) + köp/sälj/Tradable per symbol
- [x] WS margin: skicka `calc` input om null‑fält returneras
- [x] WS skalning: multi‑socket pool vid många feeds (> ~250) – ticker/trades/candles
- [x] "Resync"‑knapp i UI: re‑subscribe + REST snapshot
- [x] Startup audit: logga per `.env`‑symbol om "WS" eller "REST only"
- [x] WS pool status endpoint + UI‑knapp
- [ ] ChanId per socket – ytterligare härdning och tests (coverage)
- [x] Unsubscribe via UI på watchlist (Stop‑knappen kopplad till unsubscribe)
- [x] Pool metrics (Prometheus) och varningar när socket närmar sig max subs
- [ ] Live‑säkerhet (UI/REST)
  - [ ] Kill‑switch i UI (kopplad till `/api/v2/risk/pause`/`resume`)
  - [ ] Circuit breaker: reset/status i UI (kopplad till `/api/v2/risk/circuit/*`)
  - [ ] Per‑symbol limits/cooldowns runtime (UI + endpoints)
- [ ] Snabbstart‑profil (dev)
  - [ ] Disable `PROB_VALIDATE_ENABLED`/`PROB_RETRAIN_ENABLED` via config vid dev
  - [ ] Begränsa WS till env `WS_SUBSCRIBE_SYMBOLS` (t.ex. en symbol) som default i dev
  - [ ] Start utan reload i dev‑script (`scripts/start.ps1 -NoReload`)

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

## Utökningar (checklista)

- [ ] Metrics/observability
  - [x] Latens per endpoint (middleware)
  - [ ] Labels: symbol/side/type, HTTP-status
  - [ ] Utöka metriktyper (histogram/gauge)
- [ ] Candle-cache
  - [ ] TTL/retention och kompaktering (VACUUM)
  - [ ] History fetcher: gap-detektion, paginering, dedupe
  - [ ] Normaliserad ordning (äldst → nyast) vid indikatorer
- [ ] Bracket/OCO
  - [ ] Aktiverbar partial-fill-justering utan omedelbar OCO-cancel
  - [ ] Fördjupad reconnect-reconciliation mot aktiva ordrar
  - [ ] Konsistenskontroller och automatisk sanering av state
- [ ] Rate-limit
  - [ ] Utöka till bracket submit/cancel-all och andra känsliga endpoints
  - [ ] Per-IP/per-user nycklar och metrik
- [ ] Retry/backoff
  - [ ] Tillämpa i fler REST-moduler (t.ex. positions/close)
  - [ ] Konsolidera i gemensam hjälpare
- [ ] Docker/drift
  - [ ] Multi-stage build, non-root, prod-profil
  - [ ] (Valfritt) Compose-profil för Prometheus/Grafana
- [ ] Security/auth
  - [ ] IP-allowlist eller basic auth för /metrics (rot)
  - [ ] Env-styrning för privat/offentlig metrics
- [ ] Tester
  - [ ] E2E för rate-limit/retry
  - [ ] Assertions för nya metrics och cache-retention

<!-- Core Mode (klart) -->
