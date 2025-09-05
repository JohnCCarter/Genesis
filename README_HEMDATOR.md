# Genesis Trading Bot – Hemdator Snabbstart

Enkel guide för att starta boten lokalt på en hemdator.

---

### 1. Förberedelser (engångsinstallation)

#### a. Miljö

-   Windows 10/11 med PowerShell
-   Python 3.11+
-   Node.js v18+

#### b. Skapa virtuell miljö och installera paket

```powershell
# Navigera till din projektmapp
cd "[DIN_HEMDATOR_SÖKVÄG]"

# Skapa och aktivera virtuell miljö
python -m venv .venv_clean
& ".\.venv_clean\Scripts\Activate.ps1"

# Uppdatera pip och installera Python-paket
python -m pip install -U pip
python -m pip install -r tradingbot-backend\requirements.txt
```

#### c. Konfigurera Backend (`.env`-fil)

Skapa en fil med namnet `.env` i mappen `tradingbot-backend/` och klistra in följande. **Byt ut dina Bitfinex API-nycklar.**

```
# tradingbot-backend/.env

# --- Autentisering (för utveckling) ---
AUTH_REQUIRED=True
JWT_SECRET_KEY=dev-jwt-secret
SOCKETIO_JWT_SECRET=dev-jwt-secret

# --- Dina Bitfinex API-nycklar ---
BITFINEX_API_KEY=your_bitfinex_api_key_here
BITFINEX_API_SECRET=your_api_secret_here

# --- Funktioner att stänga av för lokal körning ---
WS_CONNECT_ON_START=False
SCHEDULER_ENABLED=False
MCP_ENABLED=False
```

#### d. Konfigurera Frontend (`.env`-fil)

Skapa en fil med namnet `.env` i mappen `frontend/dashboard/` och klistra in följande:

```
# frontend/dashboard/.env

VITE_API_BASE=http://127.0.0.1:8000
```

#### e. Installera Frontend-paket

```powershell
# Navigera till frontend-mappen
cd "[DIN_HEMDATOR_SÖKVÄG]\frontend\dashboard"

# Installera Node.js-paket
npm install
```

---

### 2. Starta programmet

Du behöver två separata terminalfönster.

#### a. Starta Backend

I det **första** terminalfönstret:
```powershell
cd "[DIN_HEMDATOR_SÖKVÄG]"
& ".\.venv_clean\Scripts\Activate.ps1"
cd tradingbot-backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

#### b. Starta Frontend

I det **andra** terminalfönstret:
```powershell
cd "[DIN_HEMDATOR_SÖKVÄG]\frontend\dashboard"
npm run dev
```

---

### 3. Öppna i webbläsaren

-   **Dashboard:** [http://localhost:5173](http://localhost:5173)
-   **API-dokumentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

*Ersätt `[DIN_HEMDATOR_SÖKVÄG]` med din faktiska sökväg.*
