# Genesis Trading Bot – Tradingfunktioner

Denna dokumentation beskriver tradingfunktionerna end‑to‑end i backend, inklusive marknadsdataflöde, signalgenerering, risk- och circuit breaker‑lager, orderexekvering, bracket/OCO, positions- och plånbokshantering, schemaläggning samt observability/metrics. Fil- och modulnamn hänvisar till `tradingbot-backend/` om inget annat anges.

## Innehåll

- Översikt
- Marknadsdata & WebSocket
- Signaler & Strategier
- Riskhantering & Circuit Breakers
- Order & Exekvering
- Bracket/OCO
- Positioner, Plånböcker & Marginal
- Schemaläggning & Automation
- Backtest & Simulering
- Prestanda & Observability
- API-yta (viktiga endpoints)
- Konfiguration & Feature Flags

## Översikt

- Dataflöde: Market Data (WS/REST) → Indicators → Signals → Risk/Policies → Orders/Positions → Metrics.
- Enhetliga tjänster: `MarketDataFacade`, `UnifiedSignalService`, `RiskManager`/`UnifiedRiskService`, `TradingService`/`TradingIntegrationService`, `BracketManager`, `PerformanceService`, `UnifiedCircuitBreakerService`.

## Marknadsdata & WebSocket

- Bitfinex WS v2 (auth) med reconnect/heartbeat: `services/bitfinex_websocket.py`.
- Stöd för `ticker`, `trades`, `candles:<tf>` med per‑symbol cache och callbacks.
- Privat WS‑event (fills/cancels) för bracket/OCO: `services/bracket_manager.py`.
- REST‑hämtningar och cache via `services/bitfinex_data.py`, `services/market_data_facade.py`.

## Signaler & Strategier

- Indikatorer: `indicators/ema.py`, `rsi.py`, `atr.py`, `adx.py`, `regime.py` (EMA‑Z, trendregim).
- Strategier:
  - Heuristisk/viktad EMA/RSI/ATR: `services/strategy.py`, vikter i `services/strategy_settings.py`.
  - Probabilistisk modell (om aktiverad): `services/prob_model.py`, features i `services/prob_features.py`.
  - Realtidsstrategi på WS‑data: `services/realtime_strategy.py`, integration i `BitfinexWebSocketService`.
- Enhetlig signalservice (standard/enhanced/realtime): `services/unified_signal_service.py`, `services/signal_service.py`.

## Riskhantering & Circuit Breakers

- Globala riskvakter: max daily loss, kill‑switch, exposure limits: `services/risk_guards.py` (konfig: `config/risk_guards.json`).
- Trade constraints (handelstider, cooldown, per‑symbol caps): `services/trade_constraints.py` via `services/risk_policy_engine.py` och `services/risk_manager.py`.
- Enhetlig riskservice som sammanför guards/constraints/CB: `services/unified_risk_service.py`.
- Circuit breakers:
  - Transport‑CB för REST/HTTP (429/5xx) med backoff: `services/transport_circuit_breaker.py`, `utils/advanced_rate_limiter.py`.
  - Trading‑CB och Rate‑Limiter‑CB: `services/unified_circuit_breaker_service.py`.

## Order & Exekvering

- Enhetlig tradingservice med tre lägen:
  - Standard (REST): `services/trading_service.py` → `_execute_standard_trade()` → `services/trading_integration.py`.
  - Enhanced (position sizing, intervall): `services/enhanced_auto_trader.py`.
  - Realtime (WS‑driven när kopplad): `TradingService._execute_realtime_trade()`.
- Ordervalidering mot Bitfinex‑krav: `rest/order_validator.py` (fallback‑data om scraper saknas).
- Idempotens via `client_id` (60s cache) och `DRY_RUN_ENABLED` för säker test.
- Post‑Only/Reduce‑Only flaggor stöds och vidarebefordras.
- Endpoints för place/get/cancel/list/history/trades: se avsnitt API‑yta.

## Bracket/OCO

- Server‑sidig OCO/bracketgruppering: `services/bracket_manager.py`.
  - Länkar `entry`, `sl`, `tp` via grupp‑ID (gid), sparar state på disk.
  - Reagerar på privata WS‑event (te/tu/oc): auto‑cancel syskon på fill, hanterar partial fills och cleanup.

## Positioner, Plånböcker & Marginal

- Wallets, total USD: `rest/wallet.py`.
- Positioner & historik: `rest/positions.py`, `rest/positions_history.py`.
- Margin info, leverage, status: `rest/margin.py`.
- Aggregation efter trade i `services/trading_integration.py` (wallet/positions refresh).

## Schemaläggning & Automation

- Scheduler och refresh: `services/scheduler.py`, `services/refresh_manager.py`.
- WS‑first data & koordination: `services/ws_first_data_service.py`, `services/data_coordinator.py`.
- Prob‑validering/retrain flöden: tester i `tests/test_scheduler_prob_*`.

## Backtest & Simulering

- Backtest: `services/backtest.py` och kostnadsmedveten backtest: `services/cost_aware_backtest.py`.

## Prestanda & Observability

- Metrics/Prometheus: `services/metrics.py` (+ `render_prometheus_text`), nyttjas i REST.
- Förbättrad observability: `services/enhanced_observability_service.py`.
- Rate‑limit/Circuit breaker‑telemetri: `utils/advanced_rate_limiter.py`.

## API‑yta (urval)

- Orders
  - `POST /api/v2/order` – skapa order (validering, risk, idempotens, dry‑run)
  - `GET /api/v2/orders` – alla aktiva ordrar
  - `GET /api/v2/orders/symbol/{symbol}` – aktiva ordrar för symbol
  - `GET /api/v2/order/{order_id}` – orderdetails
  - `GET /api/v2/orders/history` – orderhistorik
  - `GET /api/v2/order/{order_id}/trades` – trades för order
  - Cancel‑varianter inkl. per symbol
- WebSocket
  - `GET /api/v2/ws/pool/status`
  - `POST /api/v2/ws/subscribe` – `ticker|trades|candles`
  - `POST /api/v2/ws/unsubscribe`
- Wallet/Positions/Margin
  - `GET /api/v2/wallet/*`, `GET /api/v2/positions*`, `GET /api/v2/margin/*`

## Konfiguration & Feature Flags

- Miljö: `env.example` (t.ex. `AUTH_REQUIRED`, `DRY_RUN_ENABLED`, rate‑limit/CB/WS‑URI).
- Risk guards: `config/risk_guards.json`.
- Strategiviktning och indikatorperioder: `services/strategy_settings.py`.
- Feature flags & runtime toggles: `services/feature_flags_service.py`, `services/runtime_mode.py`.

---

## Testning (rekommenderad täckning)

- Enhetstester för ordervalidering, risk guards, circuit breakers, signalgenerator, WS‑subscriptions, scheduler.
- Mocka Bitfinex REST/WS i tests för determinism.

## Framtida förbättringar

- Nya indikatorer (BB, MACD, StochRSI), fler riskmetrik, förbättrad orderbokshantering, och utökade dashboards.

## Tradingbot Funktionalitet – Kategoriserad

### 🟥 Fungerar inte utan (Kärnsystem)

- Autentiserad Bitfinex‑anslutning för REST (order) och en pålitlig marknadsdatakälla (WS eller REST) — Status: Implementerad
- Orderflöde: `POST /api/v2/order`, cancel/list av aktiva ordrar, ordervalidering — Status: Implementerad
- Kontodata: plånbok (total USD) och aktuella positioner via REST — Status: Implementerad
- Basrisk: kill‑switch, max daily loss, trade window/cooldown — Status: Implementerad

### 🟧 Kritiska för stabilitet och säkerhet

- WS‑first `ticker` och `candles:1m` per symbol (lägre latens, stabilare signaler) — Status: Implementerad
- Bracket/OCO: entry + SL/TP kopplat till privata WS‑event (minskar nedsidesrisk) — Status: Delvis
- Idempotens (`client_id`) och `DRY_RUN_ENABLED` för säkra/repeterbara körningar — Status: Implementerad
- Transport/Trading circuit breakers och rate‑limit (advanced limiter) med backoff — Status: Implementerad
- Metrics‑endpoint (Prometheus‑text) för bastelemetri och övervakning — Status: Implementerad

### 🟨 Strategi & signaler

- Grundindikatorer: EMA, RSI, ATR med konfigurerbara perioder och vikter — Status: Implementerad
- Enkel heuristisk signal: BUY/SELL/HOLD/WAIT — Status: Implementerad
- Realtidsstrategi på WS‑data och enhetlig signalservice (standard/enhanced/realtime) — Status: Implementerad

### 🟦 Nice to Have (Analytics & UX)

- Förbättrad observability och dashboards/paneler (risk, wallets, orders, performance) — Status: Delvis
- Performance‑tracking och backtest‑visualisering — Status: Delvis
- Feature‑flags/runtime toggles i UI — Status: Implementerad

### 🟩 Framtida/experimentella funktioner

- Confidence‑score och förbättrad position sizing — Status: Delvis
- Fler indikatorer (BB, MACD, StochRSI), multi‑timeframe analys — Status: Planerad
- ML‑baserad probabilistisk modell för signaler — Status: Delvis
- Avancerade alerts/automation — Status: Delvis

---

## Dubbletter, överflöd och konsolideringsförslag

- WS‑signalflöde vs. UnifiedSignalService
  - Överflöd: Realtidsutvärdering sker i både `services/bitfinex_websocket.py` och genom `services/realtime_strategy.py`/`services/unified_signal_service.py`.
  - Konsolidering: Låt `UnifiedSignalService` vara enda publik signalyta; WS‑servicen matar endast rådata/callbacks.

- Risklager (RiskManager, UnifiedRiskService, RiskPolicyEngine, TradeConstraintsService)
  - Dubblett/överlapp: `RiskManager.pre_trade_checks` och `UnifiedRiskService.evaluate_risk` gör delvis samma kontroller.
  - Konsolidering: Anropa enbart `UnifiedRiskService` från REST/TradingService; håll `RiskManager` som tunn wrapper eller avveckla.

- Circuit Breakers (UnifiedCircuitBreakerService vs TransportCircuitBreaker)
  - Överlapp: Båda spårar fel/cooldown. Transport‑CB finns även i advanced rate limiter.
  - Konsolidering: Flytta rapportering och state till `UnifiedCircuitBreakerService`; låt transportlagret bara signalera events.

- Ordervalidering och idempotens
  - Möjlig dubblett: Idempotens cache i `rest/routes.py` och potentiella liknande skydd i services.
  - Konsolidering: Centralisera idempotens i en service (t.ex. `services/metrics` eller egen `request_cache`) och återanvänd.

- Strategy engines (strategy.py, realtime_strategy.py, enhanced_auto_trader.py)
  - Överlapp: Flera vägar för signal→trade.
  - Konsolidering: `TradingService` ska vara enda exekveringsväg; strategiutdata standardiseras till en modell (`SignalResponse`).

- Bracket/OCO state
  - Överflöd: State på disk och minne kan divergera vid krascher.
  - Konsolidering: En tydlig persistensstrategi (transaktionssäkert skriv, recovery‑rutin) och enhetliga API‑anrop för register/reset.

- Metrics/observability
  - Överlapp: Viss metrik skrivs från flera platser.
  - Konsolidering: Introducera en tunn `metrics_client` som standardiserar nycklar/labels och minskar duplikat.
