# TODO – Sannolikhetsmodell för automatiserad handel

## Mål och scope

- [ ] Definiera beslutshorisont (t.ex. 20–50 candles) och tidsskala (1m/5m/15m)
- [ ] Definiera TP/SL‑trösklar och klasströsklar för buy/sell/hold
- [ ] Undvik dataläckage (endast information känd vid beslutstid)

## Data och features

- [ ] Bygg feature‑extractor (per symbol/tf):
  - [ ] Trend/momentum: EMA‑spread, EMA‑lutning, RSI, ROC
  - [ ] Vol/regim: ATR/price, vol‑percentiler, regimflagga (low/high vol)
  - [ ] Struktur: range‑kompression, breakout‑indikatorer (enkla)
  - [ ] (Valfritt) Volym‑percentiler om tillgängligt
- [ ] Labeler: generera buy/sell/hold baserat på framtida ROI vs TP/SL
- [ ] Spara dataset (parquet/csv) med metadata (symbol, tf, tidsstämplar)

## Modellering och kalibrering

- [ ] Träna logistisk regression per symbol/timeframe (tolkningsbar baseline)
- [ ] Kalibrera sannolikheter (isotonic eller Platt scaling)
- [ ] Exportera modellvikter + kalibrator till JSON (per symbol/tf)

## Inferens i backend

- [ ] Lägg till predict_proba i `services/strategy.py` (ny modul/funktion)
- [ ] Fallback: använd nuvarande viktade heuristik om modell saknas
- [ ] Returnera `{buy, sell, hold, confidence}` och exponera i API

## Beslutsregel (policy)

- [ ] EV‑beslut: p(win)*TP − p(loss)*SL − fees/slippage > tröskel
- [ ] Confidence‑krav: abstain om |p(buy) − p(sell)| < δ
- [ ] Position‑size: Kelly‑inspirerad fraktion med hård cap (riskregler)

## Validering och drift

- [ ] Backtest: Brier score, LogLoss, EV/PnL per symbol/tf
- [ ] Live‑övervakning: rullande Brier, kalibreringskurvor
- [ ] Retraine/rekalibrera: veckovis/månadsvis; atomisk modell‑swap

## UI‑integrering

- [ ] Watchlist: visa sannolikheter och EV; badge för abstain/handel
- [ ] Risk‑panelen: visa p‑fördelning och beslutsstatus (trade/no‑trade)

## Guardrails och integrationer

- [ ] Respektera befintliga riskregler (windows, limits, cooldowns)
- [ ] Margin/likviditet: handla endast om `tradable > 0`

## Öppna frågor (att besluta)

- [ ] Startsymboler/timeframes (t.ex. tBTCUSD 1m/5m)
- [ ] TP/SL‑nivåer (procent/ATR‑baserade)
- [ ] Uppdateringsfrekvens för retraining/rekalibrering
- [ ] Feature‑loggning och datalagring (kvantitet, retention)
