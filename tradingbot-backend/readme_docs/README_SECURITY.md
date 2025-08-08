# Säkerhetsförbättringar för Autentisering

Detta dokument beskriver de säkerhetsförbättringar som har implementerats för autentiseringssystemet i TradingBot Backend.

## 1. ⏲️ NTP-synkronisering

För att eliminera problem med `iat` (issued-at) och `exp` (expiration) i JWT-tokens har vi implementerat:

- En `/time`-endpoint som returnerar serverns aktuella tid
- Klient-exempel som synkroniserar sin tid med servern
- Kontroll och loggning av tidsskillnader för att upptäcka NTP-drift
- Tolerans för upp till 5 minuters drift mellan server och klient

## 2. 🔑 Authorization Header

Vi har förbättrat token-hanteringen genom att:

- Använda `Authorization`-header istället för URL-parametrar
- Implementera Bearer token-format (`Authorization: Bearer <token>`)
- Säkrare hantering som förhindrar att tokens syns i loggar och URL-cache
- Bakåtkompatibilitet genom att stödja URL-parametrar som fallback

## 3. 🔒 Kortare livstid och refresh-flow

För att minska riskerna med exponerade tokens har vi:

- Minskat livstiden för access tokens till 15 minuter (från 30)
- Implementerat refresh tokens med 24 timmars livstid
- Förnyelse sker via Socket.IO-eventet `refresh_token` (inte en REST-endpoint)
- Klient-exempel som automatiskt förnyar tokens innan de går ut

## 4. 🛠️ Klientvalidering av tokens

Klientsidan har nu förbättrats med:

- Validering av token-giltighet innan användning
- Proaktiv förnyelse av tokens (5 minuter innan utgång)
- Automatisk återanslutning med nya tokens om autentisering misslyckas
- Tidssynkronisering för att undvika problem med `iat`/`exp`-validering

## Exempel på användning

För att se hur du använder det nya autentiseringssystemet, se exempel i:

- `examples/token_client_example.js` - Klientsidan för token-hantering (inkl. `refresh_token`-event)
- `ws/auth.py` - Serversidan för autentisering och token-refresh

## 5. 🧩 AUTH_REQUIRED (REST och Socket.IO)

- `AUTH_REQUIRED=True` (standard) kräver giltig JWT för alla `/api/v2/*` REST-endpoints och Socket.IO-anslutningar.
- Sätt `AUTH_REQUIRED=False` i utveckling för att temporärt tillåta åtkomst utan JWT.
- Token hämtas via `POST /api/v2/auth/ws-token` och används i `Authorization: Bearer <token>`.

## Teknisk Implementation

- JWT-tokens innehåller nu fält för `jti` (token ID), `type` (access/refresh) och `iat`/`exp`
- Tokens valideras på både klient- och serversidan
- NTP-drift hanteras genom att jämföra serverns tid med tokenens `iat`
- Refresh tokens kan inte användas för API-anrop, endast för att förnya access tokens

## Rekommendationer

- Använd alltid HTTPS i produktionsmiljö
- Förvara refresh tokens säkert (använd inte localStorage i produktion)
- Installera NTP-synkronisering på servern för att hålla tiden korrekt
- Implementera token-återkallelse för ytterligare säkerhet
