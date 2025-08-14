# TODO – Sannolikhetsmodell för automatiserad handel

## Mål och scope — KLART

- [x] Definierade env‑flaggor (PROB_MODEL_TIME_HORIZON, PROB_MODEL_EV_THRESHOLD, PROB_MODEL_CONFIDENCE_MIN)
- [x] Fallback‑policy och beslutsprincip dokumenterad

## Data och features — KLART

- [x] Feature‑extractor (ema_diff, rsi_norm, atr_pct)
- [x] Labeler: buy/sell/hold baserat på framtida ROI vs TP/SL
- [x] Dataset‑bygge (in‑memory helpers)

## Modellering och kalibrering — KLART

- [x] Logistisk regression baseline (one‑vs‑rest buy/sell)
- [x] Platt‑kalibrering på valideringssplit
- [x] Export JSON (vikter + kalibrator + schema)

## Inferens i backend — KLART

- [x] `services/prob_model.py` + integration i `services/strategy.py`
- [x] API: `/api/v2/prob/predict` (features, probs, EV, decision)

## Beslutsregel (policy) — KLART

- [x] EV‑beslut + confidence‑krav (env‑styrt)

## Position‑size & AutoTrade — PÅGÅR

- [x] Env: `PROB_AUTOTRADE_ENABLED`, `PROB_SIZE_MAX_RISK_PCT`, `PROB_SIZE_KELLY_CAP`, `PROB_SIZE_CONF_WEIGHT`
- [x] Endpoints: `POST /api/v2/prob/preview` (storlek/SL/TP), `POST /api/v2/prob/trade` (guardrails + bracket)
- [x] Kelly/conf‑vikt i storlek (använd `PROB_SIZE_*` + EV/konfidens) – implementerad i `/prob/preview` (size*base, size_weight, kelly*\* i svar)
- [x] UI: Risk‑panel – knappar för Preview/Trade med tydliga guardrails
- [x] Metrics/loggar: `prob_trade` events, latens och utfall per symbol/side

## Validering och drift — KLART (grund)

- [x] `/api/v2/prob/status` (enabled/loaded/schema/version/thresholds)
- [x] `/api/v2/prob/predict` returnerar latens och decision + EV
- [x] `/api/v2/prob/validate` för Brier/LogLoss
- [x] Schemalagd validering (Brier/LogLoss) i `SchedulerService`
- [x] Schemalagd retraining + atomisk reload av modell
- [x] Rullande Brier/LogLoss (tidsserie + retention) i metrics

## UI‑integrering — KLART

- [x] `prob_test.html` (inferens och visning av probs/EV/decision)
- [x] Integrera i ordinarie vyer (risk‑panel)
- [x] Watchlist: EV/prob/decision i API (`/market/watchlist?prob=true`) och visning i `ws_test.html`

## Tester — KLART

- [x] Enhetstest: `services/prob_features.py`
  - [x] `compute_features_from_candles` (min/max edge fall, kort historik)
  - [x] `label_sequence` (tp/sl, horizon‑trim)
  - [x] `build_dataset` (align features/labels)
- [x] Enhetstest: `services/prob_model.py`
  - [x] `predict_proba` med mockad `model_meta` (schema/kalibrering)
  - [x] Fallback när `enabled=false` eller modell saknas
- [x] API‑tester (monkeypatch candles)
  - [x] `POST /api/v2/prob/predict` (probs, EV, decision, latens)
  - [x] `POST /api/v2/prob/validate` (Brier/LogLoss returneras rimligt)
- [x] Scheduler
  - [x] Valideringskörning uppdaterar `metrics_store['prob_validation']`
  - [x] Rullande fönster fylls och trimmas enligt retention

## Guardrails och integrationer

- [x] Respektera befintliga riskregler (windows, limits, cooldowns)
- [x] Margin/likviditet: handla endast om `tradable > 0`

## Övrigt — KLART

- Startsymboler/timeframes styrs via UI och `/prob/config`
- TP/SL‑nivåer används via ATR‑multiplikatorer i preview/trade
- Uppdateringsfrekvenser (validation/retraining) styrs via `/prob/config`
- Feature‑loggning implementerad med retention och vy i UI
