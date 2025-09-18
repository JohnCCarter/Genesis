📘 Arkitekturöversikt - Genesis Trading Bot

🚀 1. Startup-sekvens och Initialisering
Ordning vid startup (main.py):
- Miljövariabler & Settings (Rad 33)
  - Laddar .env fil automatiskt
  - Skapar singleton Settings instans
  - Sätter os.environ värden
- Core Module Imports (Rad 40-63)
  - ws.manager.socket_app - WebSocket hantering
  - rest.routes.rest_router - REST API endpoints
  - services.bitfinex_websocket.bitfinex_ws - Bitfinex WebSocket
  - services.metrics_client - Metrics och monitoring
- WebSocket Connection (Rad 94-126)
  - Ansluter till Bitfinex WebSocket (5s timeout)
  - WebSocket autentisering (3s timeout)
  - Kopplar WebSocket till enhetliga services
- Component Activation (Rad 128-138)
  - config.startup_config.enable_components_on_startup()
  - Aktiverar komponenter baserat på miljövariabler
  - Loggar startup-status
- Scheduler Start (Rad 140-151)
  - Startar services.scheduler.scheduler om aktiverat
  - Körs endast om ENABLE_SCHEDULER=true eller DEV_MODE=true
- Circuit Breaker Recovery (Rad 153-162)
  - Startar services.circuit_breaker_recovery
  - Hanterar automatisk återhämtning från fel

🔄 2. REST API Endpoints och Anropsmönster
Huvudkategorier av endpoints:
- Autentisering & Tokens
  - POST /api/v2/auth/ws-token - Genererar WebSocket token
  - GET /api/v2/auth/verify - Verifierar token
- Orderhantering
  - POST /api/v2/order - Lägger order (huvudendpoint)
  - POST /api/v2/orders/cancel/{order_id} - Avbryter order
  - POST /api/v2/orders/cancel/symbol/{symbol} - Avbryter alla ordrar för symbol
  - GET /api/v2/orders - Hämtar aktiva ordrar
  - GET /api/v2/orders/symbol/{symbol} - Hämtar ordrar för specifik symbol
- Marknadsdata & Signals
  - GET /api/v2/signals/live - Hämtar live trading signals
  - GET /api/v2/signals/{symbol} - Hämtar signal för specifik symbol
  - GET /api/v2/watchlist - Hämtar watchlist data
  - GET /api/v2/candles/{symbol} - Hämtar candle data
- Plånbok & Positioner
  - GET /api/v2/wallets - Hämtar plånböcker
  - GET /api/v2/positions - Hämtar positioner
  - GET /api/v2/positions/history - Hämtar positionshistorik
- Performance & Metrics
  - GET /api/v2/performance/daily - Hämtar dagliga statistik
  - GET /api/v2/metrics/acceptance - Hämtar acceptance metrics
  - GET /api/v2/metrics/prometheus - Prometheus metrics

🌐 3. WebSocket Event Handlers
Bitfinex WebSocket Events:
- Autentisering
  - auth - WebSocket autentisering (1 gång vid startup + vid reconnect)
- Marknadsdata (Public)
  - ticker - Prisuppdateringar
  - candles - Candle data
  - trades - Trade executions
- Privata Events (Authenticated)
  - os - Order snapshot
  - on - Order new
  - ou - Order update
  - oc - Order cancel
  - te - Trade executed
  - tu - Trade update
  - ps - Position snapshot
  - pu - Position update
  - pc - Position close
  - ws - Wallet snapshot
  - wu - Wallet update

⏰ 4. Scheduler Tasks och Exekveringsfrekvens
UnifiedSchedulerService jobb:
- Critical Priority (30s): health_check, circuit_breaker_monitor
- High Priority (60s): equity_snapshot
- Medium Priority (300s): prob_validation, regime_update
- Low Priority (1800s): cache_retention, prob_retraining

📈 5. Anropsvolym per Komponent (uppskattning)
- REST API: 500-2000 anrop/dag
- WebSocket Events: 10,000-50,000 events/dag
- Scheduler Tasks: 1,000-5,000 exekveringar/dag
- Bitfinex API: 100-500 anrop/dag (rate limited)

�� 6. Kritiska Anropskedjor
- Orderläggning (place_order_endpoint)
  - Autentisering → Rate limiting → Dry run check → Order validation → Risk kontroll → Idempotency → Symbol resolution → REST API call → (ev.) WS fallback
- Signal Generation
  - Market data → Candle parsing → Signal calc → Prob model → Risk eval → Response
- WebSocket Data Flow
  - WS connect → Auth → Subscribe → Event handlers → Process → UI emit

🎯 7. Performance Bottlenecks
- Symbol Resolution (per order)
- Market Data Fetching (hög frekvens)
- WebSocket Reconnection (dataförlust-risk)
- Circuit Breaker Recovery (blockering)
- Rate Limiting (throughput)

📊 8. Monitoring och Metrics
- API Response Times: P95 < 2.5s, P99 < 3.5s
- WebSocket Reconnection Rate: < 1%/h
- Order Success Rate: > 95%
- Circuit Breaker Trips: < 5/dag
- Memory Usage: < 80%

📎 Sammanfattning av Anropsflöde
- Startup: Settings → Imports → WS connect/auth → Components → Scheduler → Recovery
- Volym: REST (500–2000), WS (10k–50k), Scheduler (1k–5k), Bitfinex (100–500)
- Flöden: Order (9 steg), Signal (6 steg), WS (6 steg)
- Resiliens: WS‑fallback för REST, circuit breakers, rate limiting
