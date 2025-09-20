# Genesis Trading Bot - Frontend Dashboard

> **React-baserad dashboard för att övervaka och styra Genesis Trading Bot med realtidsdata och intuitiv användargränssnitt.**

[![React](https://img.shields.io/badge/React-18-blue.svg)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-5.0+-green.svg)](https://vitejs.dev)
[![Socket.IO](https://img.shields.io/badge/Socket.IO-4.0+-orange.svg)](https://socket.io)

Detta är frontend-delen av Genesis Trading Bot, en React-baserad dashboard för att övervaka och styra trading-boten.

## Innehåll

1. [Översikt](#översikt)
2. [Arkitektur](#arkitektur)
3. [Installation](#installation)
4. [Konfiguration](#konfiguration)
5. [Utveckling](#utveckling)
6. [Paneler](#paneler)
7. [API-integration](#api-integration)
8. [WebSocket](#websocket)
9. [Bygga för produktion](#bygga-för-produktion)

## Översikt

Frontend dashboarden är byggd med:

- **React 18** med TypeScript
- **Vite** som build-verktyg
- **Socket.IO Client** för realtidskommunikation
- **Fetch API** för REST-anrop
- **LocalStorage** för persistenta inställningar

Dashboarden består av flera paneler:

- **Trading**: Orderhantering, aktiva ordrar, positionshantering
- **Risk & Guardrails**: Trading window, riskinställningar
- **Data & Strategy**: Marknadsdata, strategiparametrar
- **Model & Validation**: Probabilistisk modell, validering
- **Performance & History**: Trade-historik, prestanda
- **System**: Systemhälsa, debug-verktyg

## 🏛️ Arkitektur

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Dashboard                       │
├─────────────────────────────────────────────────────────────┤
│  React 18 + TypeScript + Vite                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Main App (main.tsx)                                   │ │
│  │  ├── Trading Panel     │  ├── Risk Panel              │ │
│  │  ├── Market Panel      │  ├── History Panel           │ │
│  │  ├── System Panel      │  └── Wallets Panel           │ │
│  │  └── Navigation & Layout                               │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────▲───────────────────────────────────────┘
                      │ API Calls + WebSocket
┌─────────────────────┴───────────────────────────────────────┐
│  Backend Integration                                        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  REST API (api.ts)     │  WebSocket (socket.ts)       │ │
│  │  ├── JWT Auth          │  ├── Real-time Events        │ │
│  │  ├── Order Management  │  ├── Market Data             │ │
│  │  ├── Risk Controls     │  ├── Position Updates        │ │
│  │  └── System Status     │  └── Notifications           │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────▲───────────────────────────────────────┘
                      │ HTTP/WebSocket
┌─────────────────────┴───────────────────────────────────────┐
│  Genesis Backend (FastAPI)                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  REST Endpoints        │  WebSocket Handlers           │ │
│  │  ├── /api/v2/auth      │  ├── Real-time Data          │ │
│  │  ├── /api/v2/orders    │  ├── Order Updates           │ │
│  │  ├── /api/v2/risk      │  ├── Position Changes        │ │
│  │  └── /api/v2/system    │  └── System Events           │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Dataflöde

1. **Initialisering**: App laddar JWT-token från localStorage
2. **Autentisering**: Token används för alla API-anrop
3. **Realtidsdata**: WebSocket-anslutning för live-uppdateringar
4. **State Management**: React state + localStorage för persistence
5. **Error Handling**: Centraliserad felhantering med användarfeedback

## Installation

### Förutsättningar

- Node.js 18+
- npm
- Backend-servern måste vara igång (se huvud-README för instruktioner).

### Steg för installation

1.  Navigera till dashboard-mappen:

    ```powershell
    cd frontend/dashboard
    ```

2.  Installera beroenden:

    ```powershell
    npm install
    ```

3.  Skapa en `.env`-fil i denna mapp (`frontend/dashboard/.env`) och lägg till följande rad. Detta är kritiskt för att frontend ska kunna hitta din backend.

    ```env
    VITE_API_BASE=http://127.0.0.1:8000
    ```

4.  Starta utvecklingsservern:

    ```powershell
    npm run dev
    ```

Dashboarden startar på `http://localhost:5173`.

## Konfiguration

### Miljövariabler (.env)

```env
# API-bas URL (backend)
VITE_API_BASE=http://127.0.0.1:8000

# WebSocket URL (backend)
VITE_WS_URL=http://127.0.0.1:8000
```

### Backend-konfiguration

Se backend README för:

- API-nycklar för Bitfinex
- WebSocket-konfiguration
- Strategiinställningar

## Utveckling

### Projektstruktur

```
src/
├── components/          # React-komponenter
│   ├── TradingPanel.tsx
│   ├── RiskPanel.tsx
│   ├── MarketPanel.tsx
│   ├── HistoryPanel.tsx
│   ├── SystemPanel.tsx
│   └── WalletsPanel.tsx
├── lib/
│   ├── api.ts          # API-hjälpfunktioner
│   └── socket.ts       # WebSocket-hantering
├── types/              # TypeScript-typer
└── main.tsx           # App-entry point
```

### Kommandon

```bash
# Utvecklingsserver
npm run dev

# Bygg för produktion
npm run build

# Förhandsvisa produktion
npm run preview

# Lint och type-check
npm run lint
npm run type-check
```

## Paneler

### Trading Panel

- **Orderhantering**: Market/Limit ordrar med symbol-autocomplete
- **Aktiva ordrar**: Visa, avbryt, redigera ordrar
- **Positionshantering**: Visa aktiva positioner
- **Wallet-balanser**: Visa kontosaldo

### Risk Panel

- **Trading Window**: 24-timmars schema per veckodag
- **Riskinställningar**: Max trades, cooldown, circuit breaker
- **Trading Paused**: Pausa all trading

### Market Panel

- **Watchlist**: Realtidsmarknadsdata
- **Strategiparametrar**: EMA/RSI/ATR perioder och vikter
- **Auto-regim**: Automatisk regimdetektering (Trend/Range/Balanced)
- **Auto-vikter**: Automatisk viktjustering baserat på regim

### History Panel

- **Trade-historik**: Komplett historik över trades
- **Ledger**: Transaktionshistorik
- **Prestanda**: P&L, equity-kurva

### System Panel

- **Systemhälsa**: Backend-status, API-anslutning
- **Debug-verktyg**: WebSocket-anslutning, REST-caller
- **Loggar**: Systemloggar och felmeddelanden

## API-integration

### REST API

Dashboarden använder backend REST API:er för:

- Orderhantering (`/api/v2/orders`)
- Positionsdata (`/api/v2/positions`)
- Wallet-data (`/api/v2/wallets`)
- Strategiinställningar (`/api/v2/strategy`)
- Runtime-toggles (`/api/v2/mode/*`)

### Autentisering

API-anrop använder JWT-tokens från localStorage:

```typescript
const token = localStorage.getItem('auth_token');
const headers = { Authorization: `Bearer ${token}` };
```

## WebSocket

### Anslutning

Dashboarden ansluter automatiskt till backend WebSocket:

```typescript
import { io } from 'socket.io-client';
const socket = io(import.meta.env.VITE_WS_URL);
```

### Events

- **ticker**: Realtidsmarknadsdata
- **trades**: Trade-uppdateringar
- **orders**: Order-statusändringar
- **positions**: Positionsuppdateringar

### Debug-panel

System-panelen innehåller WebSocket-debug-verktyg:

- Connect/Disconnect
- Subscribe/Unsubscribe till kanaler
- Visa aktiva prenumerationer
- WebSocket-log

## Bygga för produktion

### Bygg

```bash
npm run build
```

### Deploy

Byggda filer finns i `dist/`-mappen och kan deployas till:

- GitHub Pages
- Netlify
- Vercel
- Egen webbserver

### Miljövariabler för produktion

Uppdatera `.env` med produktions-URL:er:

```env
VITE_API_BASE=https://your-backend-domain.com
VITE_WS_URL=https://your-backend-domain.com
```

## Felsökning

### Vanliga problem

1. **"Backend inte tillgänglig"**

   - Kontrollera att backend-servern körs
   - Verifiera `VITE_API_BASE` i `.env`

2. **"WebSocket ej ansluten"**

   - Kontrollera backend WebSocket-status
   - Verifiera `VITE_WS_URL` i `.env`

3. **"API-nycklar saknas"**

   - Konfigurera Bitfinex API-nycklar i backend
   - Se backend README för instruktioner

4. **"Symboler laddas inte"**
   - Kontrollera backend API-status
   - Verifiera Bitfinex-anslutning

### Debug-verktyg

- Använd System-panelens debug-sektion
- Öppna browser DevTools för nätverksloggar
- Kontrollera backend-loggar

## Utveckling av nya funktioner

### Lägga till ny panel

1. Skapa ny komponent i `src/components/`
2. Lägg till i `main.tsx`
3. Uppdatera navigation och routing

### Lägga till ny API-endpoint

1. Uppdatera `src/lib/api.ts`
2. Lägg till TypeScript-typer
3. Implementera i relevant panel

### WebSocket-events

1. Lägg till event-hantering i `src/lib/socket.ts`
2. Uppdatera relevanta komponenter
3. Testa med debug-panelen
