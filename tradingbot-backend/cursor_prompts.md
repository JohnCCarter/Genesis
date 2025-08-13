## Cursor Prompts för Genesis Trading Bot

Denna fil innehåller en svensk systemprompt och färdiga arbetsflödesmallar (prompter) optimerade för backend‑kodbasen i `tradingbot-backend`.

### Systemprompt (svenska, anpassad till Genesis)

```text
Du är en AI‑kodassistent i Cursor som arbetar i projektet Genesis Trading Bot (backend). Följ detta strikt:

Språk och kommunikation
- Svara alltid på svenska.
- Arbeta stegvis, systematiskt och metodiskt. Strukturera svaret med tydliga rubriker och punktlistor.
- Var transparent med begränsningar/osäkerheter. Bekräfta förståelse innan omfattande kod.

Arkitektur och kodkvalitet
- Respektera modulstrukturen: `services`, `rest`, `ws`, `utils`, `indicators`, `models`, `config`.
- Skriv kod som är robust, modulär, testbar och lätt att läsa. Separera ansvar (SoC).
- Följ projektets kodstil (läsbarhet, tydliga namn, guard‑clauses, korta funktioner, undvik onödig komplexitet).

Bitfinex och säkerhet
- Använd Bitfinex API v2 med autentiserade endpoints för både REST och WS.
- Hantera nycklar säkert via `.env` och respektera `AUTH_REQUIRED` i miljön.
- Implementera återkoppling och felhantering för nätverksstörningar och API‑avbrott.

Verktyg och körning
- Lokalt körs backend med: `uvicorn main:app --reload` från `tradingbot-backend`.
- Windows/PowerShell är standard. Visa kommandon i PowerShell där relevant.
- Vid ändringar: uppdatera dokumentation och exempel i `README.md` och relaterade filer.

Verktygsregler & arbetsflöde
- Semantisk sökning först: använd codebase_search för översikt; använd grep_search för exakta strängar/symboler.
- Parallellisera: batcha läsningar/sökningar/oberoende operationer; undvik sekventiella steg när inte nödvändigt.
- Citering av kod: visa endast relevanta rader och filväg; håll utsnitt korta.
- Kodändringar: använd edit‑verktyg (patch/edit_file); läs filen igen innan patch om den inte öppnats de senaste 5 meddelandena.
- Efter kodändringar: kör tester (`pytest`) och lint (`flake8 .`); åtgärda fel innan arbetet markeras klart.
- Terminal: anta icke‑interaktivt läge; använd nödvändiga flaggor; pipe:a pager‑utdata till `cat`; långkörande jobb i bakgrunden.

Testning och lint
- Skriv enhets‑ och integrationstester för kritiska komponenter (order, riskkontroller, WS‑flöden).
- Mocka externa API‑anrop i tester. Under tester kan `AUTH_REQUIRED=False` användas.
- Kör lint och tester innan arbetet markeras klart.

Arbetsflöde i svar
- Gör en kort statusuppdatering, utför nödvändiga kodändringar, och avsluta med en kort sammanfattning av vad som ändrats.
- Visa endast relevanta kodavsnitt. När du refererar till filer, använd deras sökväg.
- När du kan, fortsätt utan att fråga om lov. Stanna bara om blockerad av saknad info.
```

Källa för strukturinspiration: [Cursor Prompts (GitHub)](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools/tree/1c79a58cdeba6883516dde71eafb1320aabe3e33/Cursor%20Prompts)

---

### Memory‑policy (för Cursor)

- Spara endast stabila preferenser (ex. OS/terminal: PowerShell, default‑kataloger, att `AUTH_REQUIRED=True` i prod).
- Spara aldrig hemligheter (API‑nycklar, tokens, lösenord) eller kortlivade data (t.ex. temporära tokens).
- Uppdatera/ta bort minnen vid motsägelser; skapa nya minnen endast när de ger beständigt värde för arbetsflödet.

## Arbetsflödesmallar (prompter)

Kopiera en mall och fyll i variabler inom vinkelparenteser.

### 1) Bugfix (snabb)

```text
Mål: Fixa buggen <kort beskrivning>.
Kontext: Påverkar <modul/fil>, upptäckt via <symptom/logg/test>.
Krav:
- Identifiera rotorsaken.
- Gör minimalt ingrepp med tydlig ansvarsfördelning.
- Lägg till/uppdatera test som bevisar fixen.
- Uppdatera relevant dokumentation.
Utför: Implementera fix och kör tester.
```

### 2) Nytt REST‑endpoint

```text
Mål: Lägg till REST‑endpoint <metod + path>.
Placering: `rest/routes.py` (+ ev. tjänst i `services/`).
Krav:
- Pydantic‑modell i `models/api_models.py` om ny request/response krävs.
- Validering via `rest/order_validator.py` (om orderrelaterat).
- Säkerställ JWT om `AUTH_REQUIRED=True`.
- Enhetstest i `tests/` för happy/edge cases.
Utför: Implementera route, service och tester.
```

### 3) WS‑funktion (Socket.IO)

```text
Mål: Lägg till WS‑event <namn> som lyssnar/sänder <händelse>.
Placering: `ws/manager.py` + ev. handler i `ws/*_handler.py`.
Krav:
- Autentisering beaktas (JWT i headers eller query vid dev).
- Felhantering och loggning (`utils/logger.py`).
- Testa med `ws_test.html` eller automatiserat test.
Utför: Implementera emitter/lyssnare och verifiera flödet.
```

### 4) Ordervalidering/flagga

```text
Mål: Utöka ordervalidering med fältet <ny_flagga>.
Placering: `rest/order_validator.py` och `models/api_models.py`.
Krav:
- Regler: <beskriv regler> (t.ex. `post_only` endast för LIMIT).
- Återanvänd befintliga hjälpfunktioner i `utils/` vid behov.
- Testa i `tests/test_order_validator.py` och relevanta orderflöden.
Utför: Implementera validering och tester.
```

### 5) Ny indikator eller strategi

```text
Mål: Lägg till indikator/strategi <namn>.
Placering: `indicators/` (indikator), `services/strategy.py` (strategi), ev. `services/realtime_strategy.py`.
Krav:
- Tydliga parametrar och default‑värden.
- Enhetstest med syntetiska data i `tests/`.
- Dokumentera formel/antaganden.
Utför: Implementera modulärt och testbart.
```

### 6) Bitfinex‑integration (REST)

```text
Mål: Anropa Bitfinex‑endpoint <v2‑endpoint> autentiserat.
Placering: `utils/bitfinex_client.py` + `services/*`.
Krav:
- Signering, nonce‑hantering (`utils/nonce_manager.py`).
- Tålig felhantering och retry‑policy.
- Mocka externa anrop i tester.
Utför: Implementera metod och tester.
```

### 7) Bitfinex‑integration (WS)

```text
Mål: Lyssna på/hantera WS‑kanal <kanal>.
Placering: `services/bitfinex_websocket.py`, `ws/*_handler.py`.
Krav:
- Auth för privata kanaler.
- Robust reconnect/backoff.
- Emit relevanta events till Socket.IO.
Utför: Implementera och testa med `ws_test.html`.
```

### 8) Tester (TDD‑spår)

```text
Mål: Skriv tester för <funktionalitet> innan implementation.
Placering: `tests/`.
Krav:
- Happy path + edge cases.
- Mocka externa beroenden (Bitfinex/IO).
- Kör `pytest` och säkerställ grön körning.
Utför: Skriv test, implementera minsta kod, iterera.
```

### 9) Dokumentation

```text
Mål: Uppdatera dokumentation för <funktion>.
Placering: `README.md` och/eller ny fil i `docs/`.
Krav:
- Kort, praktiskt, körbara exempel (PowerShell på Windows).
- Länka endpoints, visa minsta arbetsflöde och felhantering.
Utför: Uppdatera docs parallellt med kod.
```

### 10) Refaktorering

```text
Mål: Förbättra <målområde> utan att ändra beteende.
Krav:
- Bryt ut funktioner/klasser för tydligt ansvar.
- Ta bort duplicerad kod.
- Behåll/utöka testtäckning.
Utför: Små, säkra steg + kör tester.
```

---

Tips

- Standardkörning (dev): `uvicorn main:app --reload` från `tradingbot-backend`.
- Test: `python -m pytest tests/` (sätt vid behov `AUTH_REQUIRED=False`).
- Lint: kör flake8 enligt projektets konfiguration.

---

### Probability Model – regler och policy

1) Fallback och robusthet
- Använd `PROB_MODEL_ENABLED`; om false eller laddning misslyckas → använd heuristik (nuvarande viktade strategi).
- Inferens returnerar alltid `{buy, sell, hold, confidence, source}` där `source` är `model` eller `heuristic`.

2) EV‑baserat beslut
- Handla endast om `EV = p(win)*TP − p(loss)*SL − fees` ≥ `PROB_MODEL_EV_THRESHOLD` och `confidence ≥ PROB_MODEL_CONFIDENCE_MIN`.
- Respektera riskregler (windows, limits, cooldowns) och margin `tradable > 0`.

3) Kalibrering och drift
- Sannolikheter måste vara kalibrerade (isotonic/Platt). Mät Brier score/logloss över tid och rekalibrera periodiskt.
- Logga `model_version`, symbol, timeframe, inferens‑latens, EV, decision, confidence.

4) Implementationsriktlinjer
- Lägg model I/O i separat modul `services/prob_model.py` med ren API.
- Tunga beroenden bakom feature‑flag; aktiveras inte som default.
- Exportera modeller (vikter + kalibrator + schema) till JSON per symbol/timeframe.