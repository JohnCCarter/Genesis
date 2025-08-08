# TODO - Genesis Trading Bot Backend

This list summarizes next steps. Prioritized (High -> Medium -> Low).

## High priority

- [ ] UI: Scheduling (calendar) for trading windows
  - [ ] Endpoint: presets (Office hours, Asia/Europe/US sessions)
  - [ ] Holidays support (exclude dates) + API (POST /api/v2/risk/holidays)
- [ ] Notifications: Telegram channel for critical events (order fail, pause, limit)
  - [ ] ENV: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  - [ ] Service + Socket.IO toggle (toast/desktop/Telegram)
- [ ] Metrics/Observability (Prometheus)
  - [ ] More metrics: per-endpoint latency, order outcomes, fills, PnL, WS reconnects
  - [ ] /metrics: structure labels (symbol, side, type)
- [ ] Order flags in bracket: Post-Only, Reduce-Only, IOC/FOK/TIF
  - [ ] Validation + mirror in UI (ws_test.html)
- [ ] RiskManager refinement
  - [ ] Per-symbol max exposure and max concurrent positions
  - [ ] Circuit breaker (pause on max drawdown/error spikes)

## Medium priority

- [ ] Bracket/OCO improvements
  - [ ] Robust partial-fill handling (step sizing, leftover cleanup)
  - [ ] GID grouping and recovery after reconnect
- [ ] PnL & Performance
  - [ ] Realized PnL per symbol (aggregate via ledger/trades)
  - [ ] Equity curve endpoint + UI
  - [ ] /wallets/balance: FX conversion to USD via ticker when needed
- [ ] Risk-based order panel
  - [ ] % of balance + ATR-based sizing – UI preview of SL/TP & risk in USD/%
- [ ] Rate-limit/anti-abuse on sensitive endpoints
  - [ ] Simple IP-based throttling + status codes

## Low priority

- [ ] Backtest sandbox
  - [ ] Local candle cache (SQLite) + history fetcher
  - [ ] Unified simulator (same Strategy + RiskManager)
  - [ ] Reports: Sharpe, winrate, max DD, trade distribution, heatmap
- [ ] Docker
  - [ ] Dockerfile + docker-compose (Bitfinex keys via env)
  - [ ] Healthchecks and graceful shutdown (DMS already supported in WS)
- [ ] API/UI
  - [ ] Watchlist: MTF signal preview (1m/5m/1h) + sorting/filters
  - [ ] Order templates: import/export, favorites, hotkeys (frontend)

## Testing

- [ ] Unit tests
  - [ ] services/bracket_manager.py: registration, fill events, oc/tu/te
  - [ ] services/risk_manager.py: timezones, holidays, cooldown/limits
  - [ ] rest/routes.py risk endpoints: validation/timeformat
  - [ ] position-size: ATR calc + fallback flows
- [ ] Integration tests
  - [ ] REST order flow (market/limit) + Socket.IO notification
  - [ ] Performance/PnL: consistency of wallets/positions/prices
- [ ] Smoke tests (curl/PS)
  - [ ] Token, WS connect, /health, /market/ticker, /risk/position-size, /order/bracket

## Documentation

- [ ] README – update with new endpoints and dashboard Quick Start
- [ ] Describe AUTH_REQUIRED, JWT flow, Socket.IO events
- [ ] Examples: client POST for schedule + templates + backtest

## Configuration & Security

- [ ] .env example – extend with Telegram & rate-limit parameters
- [ ] Config: toggle Bitfinex WS autostart in dev
- [ ] Ensure no keys/logs are exposed (logger levels in prod)

---

Updated as we go.
