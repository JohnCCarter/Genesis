Backend TODO – Genesis (Performance, Robusthet, Risk)

Scope: Endast backend. Fokus på API-tröghet, robusthet (WS/REST), riskvakter, mätbarhet, och drift.
Taggar: #P0 (kritisk), #P1 (hög), #P2 (normal), #perf, #robustness, #risk, #observability

⸻

P0 – Omedelbara förbättringar (kritiska)

[ ] P0: Latensmätning & tröghetsdiagnos (#perf #observability)

Varför: Vi behöver se var tiden försvinner innan vi kan fixa rätt saker.
Steg (Cursor):
• Lägg in end-to-end latenslogg för alla REST-anrop: endpoint, status, connect, TTFB, bytes, retries, Retry-After.
• Mät order-roundtrip: place → ack → fill (ms).
• Mät WS-gap: tid mellan meddelanden per kanal/symbol.
• Exportera mätvärden till befintlig log/metrics-yta (t.ex. JSON-loggar eller din dashboard).
Acceptans: Vi ser p50/p95/p99 latens per endpoint och symbol samt order_roundtrip_ms i dashboard/loggar.

⸻

[ ] P0: Flytta realtidsdata till WS, sluta REST-polla (#perf #robustness)

Varför: REST-pollning driver upp latens och rate-limits.
Steg:
• Säkerställ att tickers/candles/orderbok konsumeras via WS endast.
• Inför debounce/throttle (t.ex. max uppdatering var ~200–300 ms per symbol) på indikatoruppdateringar.
• Lägg en intern kö WS → strategi med backpressure (droppa äldsta om full).
Acceptans: REST används inte längre för realtidspris/OB; inga onödiga REST-loopar körs; inga 429 p.g.a. pollning.

⸻

[ ] P0: Samtidighetskontroll & rate-limiter (#perf #robustness)

Varför: För många samtidiga anrop → köer och 429/503.
Steg:
• Inför global semafor (cap på samtidiga REST-calls).
• Inför rate-limiter (token-bucket) per domän/endpoint (separat bucket för public vs private).
• Respektera Retry-After och använd exponentiell backoff + jitter.
Acceptans: Kraftiga spikes resulterar i kontrollerad backpressure; 429/503 minskar markant.

⸻

[ ] P0: Symbol-registry & meta-sync vid start (#robustness)

Varför: Undvika “pair_not_listed”/inkonsistenser och onödiga API-fel.
Steg:
• Hämta officiell symbol-lista och metadata vid start.
• Bygg whitelist som både WS och REST använder.
• Logga avvikelser (symbol ej i whitelist) och hoppa säkert.
Acceptans: Inga “pair_not_listed” för symboler i drift. Whitelist och mapping används konsekvent.

⸻

[ ] P0: Nonce, idempotens & ordning (Bitfinex) (#robustness)

Varför: Nonce-fel och dubblettordrar orsakar tröghet och risk.
Steg:
• Generera monotont ökande nonce per process.
• Sätt clientOrderId på alla ordrar (idempotens).
• Hantera “nonce too small” med offset-justering + en säker retry.
Acceptans: Inga nonce-fel i loggarna; inga dubblettordrar vid retry.

⸻

[ ] P0: Globala riskvakter – Max Daily Loss & Kill-Switch (#risk)

Varför: Stoppa blödning när dagen går dåligt.
Steg:
• Lägg max daily loss (t.ex. X % av start-equity).
• Aktivera kill-switch som stoppar nya entries och försöker stänga öppna positioner.
• Lägg en cooldown-period efter trigger.
Acceptans: Vid överskriden dagsförlust blockeras ny handel; dashboard/logg visar att guard triggade.

⸻

P1 – Hög prioritet (nästa våg)

[ ] P1: HTTP-klient med pool/keep-alive/HTTP2/timeouts/retries (#perf)

Varför: Minska handshakes, head-of-line och häng.
Steg:
• Återanvänd en klient/pool för REST med keep-alive.
• Sätt hårda timeouts (connect/read/write/pool).
• Aktivera HTTP/2 där möjligt.
• Lägg circuit-breaker: stäng tillfälligt mot upstream efter N fel.
Acceptans: Lägre p95/p99-latens; färre timeouts; färre felspikar under belastning.

⸻

[ ] P1: Cost-aware backtest (avgift, spread, slippage, latency, partial fills) (#perf #quality)

Varför: Realistiska resultat → bättre beslut.
Steg:
• Modellera avgifter + spread + slippage per symbol.
• Simulera partial fills och ack/latency.
• Rapportera Sharpe/Sortino/MAR, hit-rate, avg win/loss, max DD.
Acceptans: Backtest-rapport visar metrik + kostnader; expectancy ändras realistiskt.

⸻

[ ] P1: Prob-kalibrering & position sizing 2.0 (#quality #risk)

Varför: Oskalibrerad “probability” → fel storlek.
Steg:
• Kalibrera sannolikheter (t.ex. reliability-diagram, Platt/Isotonic).
• Använd kalibrerade probs i position sizing (t.ex. fractionerad Kelly capped av risklimits).
Acceptans: Reliability-diagram ~linjärt; positioner skalar rimligt mot prob; förbättrad riskjusterad avkastning i WFO.

⸻

[ ] P1: Regime ablation & gate (#quality)

Varför: Regime-byte måste bevisas nyttigt.
Steg:
• Kör A/B: med/utan regime switching.
• Tillåt regime styra beslut endast om expectancy ↑ och max DD ↓.
Acceptans: Dokumenterad förbättring i WFO; annars fallback till enklare regelverk.

⸻

[ ] P1: Observability – fler metrics & larm (#observability)

Varför: Snabba felupptäckter → snabbare MTTR.
Steg:
• Exportera retry_count, rate_limit_hits, circuit_open_count.
• Larma på no-trades när förväntat, reconnect loops, p99 order_roundtrip över tröskel.
Acceptans: Larm triggar på rätt villkor; dashboard visar trend och outliers.

⸻

P2 – Förfining och skalbarhet

[ ] P2: JSON/parsing & data-path optimering (#perf)

Varför: Slipp CPU-spikar i hot paths.
Steg:
• Minimera kopieringar; batcha parse → vidare till indikatorer.
• Gör indikatorer inkrementella (uppdatera sista bar, räkna inte om allt).
• Vektorisera tunga delar (NumPy), undvik DF-bygge i realtid.
Acceptans: Lägre CPU-tid i profiler; jämnare latens under last.

⸻

[ ] P2: Konto/throttle & cache på “statiska” endpoints (#robustness)

Varför: Onödig last drar ner allt.
Steg:
• Throttla kontobalans/positionshämtning (inte oftare än N sek).
• Cachea symbol/meta med TTL, använd ETag/If-None-Match där möjligt.
Acceptans: Färre REST-calls; stabilare p95-latens.

⸻

[ ] P2: Hälsokoll/Watchdog (#robustness)

Varför: Självövervakning minskar behov av manuell insats.
Steg:
• Periodiska checks: WS-data flödar? Orderqueue tom? Strategy “tyst” för länge?
• Auto-åtgärder (t.ex. reinit av feed) + tydlig loggning/notis.
Acceptans: Watchdog återställer vanliga fel utan manuell insats; incidenter loggas.

⸻

Kodkvalitet, tests & säkerhet (löpande)

[ ] Tests: risk & reconnect-kritiska paths (#tests)
• Enhetstester för max daily loss, kill-switch, cooldown, exposure-cap.
• Integrationstester för WS reconnect, idempotenta ordrar, nonce-fel.
• Backtest-tester med kostnadsmodell + partial fills.
Acceptans: Grönt på testsviten; regressions fångas.

[ ] Säkerhet & secrets-hygien (#security)
• Se att API-nycklar inte läcker i logg/commit; använd env/secrets manager.
• Minsta privilegier på nycklar (no withdrawals).
• Autentisering/åtkomstkontroll på ev. interna API-endpoints.
Acceptans: Inga hemligheter i repo/logg; åtkomstkrav verifierade.

[ ] Dokumentation (operativ & utvecklar) (#docs)
• RUNBOOK: hur starta/stoppa, återstart, felsök vanliga fel, tolkning av dashboard.
• CHANGELOG för konfig-ändringar som påverkar risk/latens.
Acceptans: Ny kollega kan följa runbook och köra boten säkert.

⸻

Körordning (rekommenderad)

1. P0-blocken i ordning: Latensmätning → WS-först → concurrency/rate-limit → symbol-registry → nonce/idempotens → riskvakter.
2. P1: HTTP-klient-uppgradering → cost-aware backtest → prob-kalibrering+possize → regime-ablation → observability-larm.
3. P2: Data-path optimering → konto/throttle+cache → watchdog.
4. Löpande: Tests, säkerhet, dokumentation.

⸻

Definition of Done (DoD)
• Perf: p95/p99-latens ned; drastiskt färre 429/503; stabil order_roundtrip.
• Robusthet: Inga “pair_not_listed”; stabil WS reconnect; inga nonce/dublett-incidents.
• Risk: Max-daily-loss & kill-switch fungerar i skarpt test; cooldown respekteras.
• Observability: Dashboard visar latens, gaps, retries, larm; runbook beskriver åtgärder.
• Kvalitet: Tester täcker riskvakter, reconnect, idempotens; CI grönt.

⸻

Noteringar till Cursor/Agent
• Arbeta modul för modul; skapa PR per P0-punkt.
• Lägg till feature flags i config för nya vakter/metrics så vi kan slå av/på.
• Vid ändringar i exekveringsbanan: uppdatera CHANGELOG och RUNBOOK.
• Vid tvekan: prioritering följer “Körordning”.
