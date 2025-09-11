# TODO – Konsolidering och Dubblettåtgärder (Genesis Trading Bot)

Denna lista sammanfattar prioriterade åtgärder för att minska dubbletter/överlapp och stärka arkitekturen.

## 1) Konsolidera risklager (Hög)

- Flytta pre‑trade‑kontroller till `UnifiedRiskService` som enda publika API.
- Ersätt direkta anrop till `RiskManager` i `rest/routes.py`/`services/trading_service.py`.
- Behåll `RiskPolicyEngine`/`TradeConstraintsService` som interna beroenden.
- Klar-kriterier: alla ordervägar anropar `UnifiedRiskService.evaluate_risk()`; tester uppdaterade.

## 2) Circuit Breakers (Hög)

- Centralisera state/telemetri i `UnifiedCircuitBreakerService`.
- Låt `TransportCircuitBreaker`/`advanced_rate_limiter` endast signalera events.
- Klar-kriterier: enhetlig CB‑statuspanel; duplicerad logik borttagen.

## 3) WS‑signaler (Hög)

- Låt `BitfinexWebSocketService` endast tillhandahålla data/callbacks.
- Kör strategiutvärdering i `RealtimeStrategyService`; exponera via `UnifiedSignalService`.
- Klar-kriterier: inga strategi‑beslut i WS‑servicen; enhetligt signal-API.

## 4) MarketDataFacade (Medel)

- Samla WS‑first + REST i `MarketDataFacade` och integrera `ws_first_data_service`.
- Klar-kriterier: ett publikt data‑API; mindre kopplingar mellan services.

## 5) Order‑idempotens (Medel)

- Centralisera idempotenscache i en service/utility.
- Ta bort ad‑hoc cache i `rest/routes.py`.
- Klar-kriterier: en källa för idempotens; tester gröna.

## 6) Scheduler/refresh (Medel)

- Konsolidera `refresh_manager`/`scheduler`/ad‑hoc jobb till en scheduler med namngivna jobb.
- Klar-kriterier: konfigurerbara intervall; jobbstatus/metrics.

## 7) Metrics‑standard (Medel)

- Inför `metrics_client` för standardiserade nycklar/labels.
- Refaktorera direkta `metrics_store`/`inc`‑anrop.
- Klar-kriterier: enhetlig mätning; dashboard uppdaterad.

## 8) Konfiguration/Feature flags (Medel)

- Läs env endast via `config/settings.py`; exekvera flaggor via `feature_flags_service`.
- Klar-kriterier: inga direkta `os.environ[...]` i services.

## 9) Bracket/OCO‑persistens (Låg)

- Förbättra disk‑persistens och recovery‑rutin i `bracket_manager`.
- Klar-kriterier: säkert återstartsbeteende; testfall för partial fills.

## 10) Rapport

- Generera `analysis/summary.md` med funna överlapp, beslut och nästa steg.
- Klar-kriterier: dokument länkad från `README_TRADING_FUNCTIONS.md`.

---

Status spåras via TODO‑listan i projektet.
