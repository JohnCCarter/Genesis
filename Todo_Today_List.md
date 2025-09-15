Här är en komplett, kategoriserad inventering av alla anrop som boten gör (interna API, externa Bitfinex REST/WS samt frontend-klientanrop). Prefixet för backend‑API är /api/v2 via rest/routes.py (root‑endpoints från main.py listas separat).

Nr 1:
Backend API (root, från main.py)
GET / (root info)
GET /health
GET /time
GET /docs, /docs/oauth2-redirect
GET /_docs_static/* (swagger assets)
GET /metrics (Prometheus text)
Backend API (prefix /api/v2, från rest/routes.py)
System & Auth
GET /health
GET /ui/capabilities
MCP utils:
GET /mcp/ws_status
GET /mcp/get_token
GET /mcp/run_validation
POST /mcp/execute
GET /mcp/ws_strategy
POST /mcp/set_ws_strategy
Runtime / Feature toggles
GET /mode/ws-strategy
POST /mode/ws-strategy
POST /mode/autotrade
POST /runtime/config (hot‑reload av configvärden)
WebSocket (status/subscribe)
GET /ws/pool/status
POST /ws/subscribe
Risk & Guardrails (Unified + V1/V2)
Unified:
GET /risk/unified/status
POST /risk/unified/pause
POST /risk/unified/resume
POST /risk/unified/evaluate
POST /risk/unified/reset-guard
V1:
GET /risk/status
GET /risk/windows
POST /risk/windows
POST /risk/pause
POST /risk/resume
V2 (bakåtkompatibilitet):
GET /v2/risk/status
GET /v2/risk/windows
POST /v2/risk/windows
POST /v2/risk/pause
POST /v2/risk/resume
Circuit Breaker (Unified CB)
GET /circuit-breaker/status (valfritt ?name= for en specifik)
POST /circuit-breaker/reset
POST /circuit-breaker/record-success
POST /circuit-breaker/force-recovery
GET /circuit-breaker/recovery-status
Signaler & Strategi
GET /signals/live
GET /signals/{symbol} (om aktiverad)
Validering / Backtest (prob/strategy)
POST /prob/validate/run
V2:
POST /v2/validation/probability
POST /v2/validation/strategy
POST /v2/validation/backtest
GET /v2/validation/history
GET /validation/history
Observability / Metrics / Refresh
GET /metrics (Prometheus text)
GET /metrics/summary
Refresh Manager:
GET /refresh-manager/status
POST /refresh-manager/force-refresh
Order/Trading (kärnflöden)
POST /order
Backend Debug‑endpoints (ur rest/debug_routes.py)
Diverse debug/status‑endpoints (task dump, threads, rate limiter, market data, risk guards, WS, m.m.) — används för felsökning och utveckling (exakta paths varierar men laddas via separat debug_router).
Externa anrop (Bitfinex REST v2, använda i services/rest‑moduler)
Publika (exempel)
GET /v2/tickers?symbols={comma_list}
GET /v2/ticker/{symbol}
GET /v2/candles/trade:{tf}:{symbol}/hist (via facade)
GET /v2/book/{symbol}/{precision}
GET /v2/trades/{symbol}/hist
Privata “read” (auth/r/*)
auth/r/wallets
auth/r/positions
auth/r/positions/hist
auth/r/positions/snap
auth/r/positions/audit
auth/r/orders
auth/r/orders/hist
auth/r/order/{order_id}/trades
auth/r/trades/hist
auth/r/trades/{symbol}/hist
auth/r/ledgers/hist
auth/r/ledgers/{currency}/hist
auth/r/info/margin
auth/r/info/margin/base
auth/r/info/margin/sym:{PAIR}
auth/r/info/user
auth/r/movements
(sign‑test) auth/r/ping
Privata “write” (auth/w/*)
auth/w/order/submit
auth/w/order/update
auth/w/order/cancel
auth/w/order/cancel/all
auth/w/position/claim
auth/w/position/funding/type
auth/w/transfer
Övrigt
auth/r/orders/active (används/testas i utils/tests)
Externa anrop (Bitfinex WebSocket v2)
Publik WS (kanaler)
ticker|t{SYMBOL}
candles|trade:{timeframe}:t{SYMBOL}
Auth WS (om aktiverat)
autentisering + privata flöden (PNL/ordrar m.m.) vid behov
Pool/konfiguration
pool_enabled, pool_max_sockets, pool_max_subs
sub‑hantering (subscribe/unsubscribe), ping/pong, heartbeats
Frontend‑klient (fetch från frontend/dashboard/src/lib/api.ts)
Bas:
GET BASE + /health
GET BASE + /api/v2/ui/capabilities
Token:
POST BASE + /api/v2/mcp/get_token (lagrar localStorage.jwt)
Generiska wrappers (alla backend‑paths ovan via):
GET: get(path) → fetchWithRetry (timeout, retry, klient‑CB)
POST: post(path, body) → fetchWithRetry
Klient‑CB
Lokal breaker i api.ts (öppnar på nätverksfel/timeout/5xx/429)
Reset via resetCircuitBreaker()



Nr 2:
Här är konkreta problem jag ser utifrån dina svar – och hur vi fixar dem:

WS pool (inkonsekvent mot config)
Observation: pool_max_sockets=1 men pool_sockets listar 4 sockets (index 0..3).
Konsekvens: onödig WS‑fläktning, risk för rate‑limits.
Åtgärd: granska WS pool‑initiering så endast 1 publik socket skapas (respektera WS_PUBLIC_SOCKETS_MAX). Sannolikt dubbel initiering vid resubscribe/warmup.
Prob‑only men probability=0
Observation: model_enabled=true men trading_probability=0 för alla symboler.
Konsekvens: panel visar konsekvent HOLD oavsett signals/strength.
Åtgärd: se till att .env pekar på en faktisk modellfil (ex. PROB_MODEL_FILE=tradingbot-backend/config/models/BTCUSD_1m.json) och att filen finns. Träna via services.prob_train_runner och starta om backend.
Riskstatus visar 100% daily_loss/drawdown med equity=0
Observation: current_equity=0, daily_loss_percentage=100, drawdown_percentage=100, men overall_status=healthy.
Konsekvens: vilseledande riskpanel.
Åtgärd: i UnifiedRiskService – när equity saknas/0: returnera 0% för dessa nyckeltal (eller “N/A”) och sätt overall_status baserat på CB och guards, inte på 100% default.
Dubbla risk‑endpoints (V1, V2 och unified)
Observation: både /risk/*, /v2/risk/* och unified endpoints används.
Konsekvens: frontend kan blanda källor → olika status/resume‑beteenden.
Åtgärd: standardisera frontend till endast unified (/risk/unified/*) och låt V1/V2 ligga kvar som bakåtkomp (ej använda i UI).
Tokenflöde och CB‑spam i UI
Observation: dev tools spam “Circuit breaker: OPEN” när token/requests strular.
Åtgärd (redan gjort): api.ts hämtar token via /api/v2/mcp/get_token och token‑anropen räknas inte mot klient‑CB. Verifiera att localStorage.jwt fylls och att Authorization skickas i skyddade anrop.
Scheduler/capabilities vs verkligt läge
Observation: scheduler_running=true, autotrade_enabled=true, dry_run=true.
Risk: autotrade aktiv utan modellprob (>0) kan ge passiva signaler, men DRY_RUN skyddar.
Åtgärd: håll DRY_RUN=true tills modell är laddad och probability>0. När prob fungerar: justera.
Rate limit orders saknar parametrar
Observation: rate_limit.order_max=0, order_window=0 i capabilities.
Konsekvens: inga UI‑indikatorer för order throttle (kan vara önskat).
Åtgärd: sätt riktiga värden i settings om du vill synas i UI; annars ignorera.
WS Strategy On + Connect On Start
Observation: ws.strategy_enabled=true, connect_on_start=true → autosubs aktiv.
Åtgärd: se till att autosubscribe använder samma symbolkälla som signals så vi undviker dubletter och fler sockets.



Här är dubbletter/legacy och rekommenderad konsolidering.

Risk endpoints (V1/V2/Unified)
Dubbletter: /risk/*, /v2/risk/*, samt unified /risk/unified/*.
Konsolidera: använd endast unified (/risk/unified/status|pause|resume|evaluate|reset-guard). Låt V1/V2 ligga kvar som bakåtkomp, markera legacy i kod och UI.
Circuit breaker (tre lager)
Dubblett/överlagring: utils/advanced_rate_limiter har egen CB‑state; services/transport_circuit_breaker.py wrappar; UnifiedCircuitBreakerService håller central state.
Konsolidera: gör Unified som enda SoT (state + metrics). Låt advanced_rate_limiter enbart signalera events till unified (ingen egen livscykel). Ta bort/avveckla TransportCircuitBreaker om den bara duplicerar signalering.
Signals (UnifiedSignalService på två ställen)
Dubblett: en UnifiedSignalService finns i services/unified_signal_service.py och en liknande i services/signal_service.py (med egen cache/generatorer).
Konsolidera: behåll EN modul (föreslås services/unified_signal_service.py) och exponera en tydlig export. Länka UI och andra services till denna. Lämna heuristiken i services/strategy.py som ren debug (prob‑only branch).
Token/Auth endpoints
Dubblett: historiskt /api/v2/auth/ws-token vs nu /api/v2/mcp/get_token.
Konsolidera: använd enbart /api/v2/mcp/get_token. Ta bort/avpublicera äldre auth‑endpoint ur UI/kod.
WS strategy toggles
Dubblett: /mcp/ws_strategy//mcp/set_ws_strategy och /mode/ws-strategy (GET/POST).
Konsolidera: behåll /mode/ws-strategy som officiellt; märk MCP‑varianterna som dev‑only eller ta bort dem från UI.
Validation/Backtest
Dubblett: /prob/validate/run och /v2/validation/* (probability/strategy/backtest/history).
Konsolidera: använd /v2/validation/*. Lämna /prob/validate/run för intern/debug om behövs, annars avveckla.
Metrics
Dubblettliknande: root /metrics (Prometheus) och /api/v2/metrics i router (med auth/extra export).
Konsolidera: behåll root /metrics för Prometheus (utan auth). Flytta extra export till separat intern endpoint eller inkludera i /metrics/summary. UI ska använda /metrics/summary.
Runtime‑flaggor vs FeatureFlags
Överlapp: services/runtime_mode.py (process‑lokal state) och services/feature_flags_service.py.
Konsolidera: gör FeatureFlagsService till SoT; låt runtime_mode bli enkel adapter (eller avveckla). UI och routes ska gå via feature‑flags.
WS pool initiering
Inkonsekvens: config “WS_PUBLIC_SOCKETS_MAX=1” men status visar 4 sockets.
Konsolidera: centralisera initiering/resubscribe i WS‑manager; säkerställ att pool skapats exakt en gång.
Metrics endpoints i router
Kontrollera att UI använder en enda källa för status (kapabiliteter/metrics/refresh) för att undvika dubblettlogik i paneler.
Legacy startscript
tradingbot-backend/server.py (med FastMCP) ser ut som alternativ uppstart. Standardisera på main.py (uvicorn). Märk server.py som legacy/dev‑entry eller ta bort.
Vill du att jag skapar e




Nr 3:
Extra problem:
“/api/v2/v2/…”-risk: Ni listar V2-routes under redan prefixad /api/v2. Om dessa routers själva har base /v2/* blir faktiska paths /api/v2/v2/… → fel.                                                       Namn-inkonsekvens: ws_strategy vs ws-strategy.                                                               Dubbla health/metrics i root och under /api/v2.