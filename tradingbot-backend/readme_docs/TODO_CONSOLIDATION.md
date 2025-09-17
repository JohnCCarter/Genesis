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

## 6) Scheduler/refresh (Medel) ✅

- ✅ Konsolidera `refresh_manager`/`scheduler`/ad‑hoc jobb till en scheduler med namngivna jobb.
- ✅ Klar-kriterier: konfigurerbara intervall; jobbstatus/metrics.
- **Implementerat:** `UnifiedSchedulerService` konsoliderar alla schemalagda jobb med prioriteter och status-tracking.

## 7) Metrics‑standard (Medel)

- Inför `metrics_client` för standardiserade nycklar/labels.
- Refaktorera direkta `metrics_store`/`inc`‑anrop.
- Klar-kriterier: enhetlig mätning; dashboard uppdaterad.

## 8) Konfiguration/Feature flags (Medel) ✅

- ✅ Läs env endast via `config/settings.py`; exekvera flaggor via `feature_flags_service`.
- ✅ Klar-kriterier: inga direkta `os.environ[...]` i services.
- **Implementerat:** `utils/feature_flags.py` utility ersätter direkta env-anrop; utökad `FeatureFlagsService` med pytest-mode och runtime-config.

## 9) Bracket/OCO‑persistens (Låg) ✅

- ✅ Förbättra disk‑persistens och recovery‑rutin i `bracket_manager`.
- ✅ Klar-kriterier: säkert återstartsbeteende; testfall för partial fills.
- **Implementerat:** Förbättrad `_load_state()` med validering, `recover_partial_fills()` för omstart, `_backup_corrupt_state()` för felhantering.

## 10) Rapport ✅

- ✅ Generera `analysis/summary.md` med funna överlapp, beslut och nästa steg.
- ✅ Klar-kriterier: dokument länkad från `README_TRADING_FUNCTIONS.md`.
- **Implementerat:** `analysis/summary.md` genererad med detaljerad framstegsrapport och status för alla punkter.

---

## 🎉 **SLUTSTATUS: ALLA PUNKTER KLARA!**

**Datum:** 2025-01-27
**Framsteg:** 10/10 punkter implementerade (100%)

### ✅ **FULLSTÄNDIGT KLARA:**
1. **Konsolidera risklager** - `UnifiedRiskService` implementerat
2. **Circuit Breakers** - `UnifiedCircuitBreakerService` centraliserat
3. **WS-signaler** - Tydlig separation mellan data och strategi
4. **MarketDataFacade** - WS-first med REST fallback
5. **Order-idempotens** - `IdempotencyService` centraliserat
6. **Scheduler/refresh** - `UnifiedSchedulerService` konsoliderat
7. **Metrics-standard** - `MetricsClient` för enhetlig mätning
8. **Feature flags** - `utils/feature_flags.py` ersätter env-anrop
9. **Bracket/OCO-persistens** - Förbättrad recovery och validering
10. **Rapport** - `analysis/summary.md` genererad

### 🚀 **Resultat:**
- **Enhetlig arkitektur** med centraliserade services
- **Robust felhantering** och recovery-rutiner
- **Modulär struktur** med tydlig separation av ansvar
- **Förbättrad underhållbarhet** och testbarhet
- **Konsistent konfiguration** via feature flags

**Status:** Konsolideringsprojektet är **SLUTFÖRT** ✅
