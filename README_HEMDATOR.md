# Genesis Trading Bot – Hemdator Snabbstart

Enkel guide för att starta boten lokalt på en hemdator.

**Dator:** Skynet
**Sökväg:** `C:\Users\salib\Desktop\Repo\Genesis`

## 🏠 **Lokal Utvecklingsmiljö**

Detta är en **lokal utvecklingsmiljö** som körs endast på din dator:

- **Backend:** `http://localhost:8000` (lokalt)
- **Frontend:** `http://localhost:5173` (lokalt)
- **Ingen extern åtkomst** - endast från din dator
- **Säker konfiguration** - WebSocket och scheduler är avstängda

---

### 1. Förberedelser (engångsinstallation)

#### a. Miljö

- Windows 10/11 med PowerShell
- Python 3.11+
- Node.js v18+ (npm 11.4.2+)

#### b. Installera paket

```powershell
# Navigera till din projektmapp
cd "C:\Users\salib\Desktop\Repo\Genesis"

# Installera Python-paket (ingen virtuell miljö behövs)
python -m pip install -U pip
python -m pip install -r tradingbot-backend\requirements.txt

# Installera Frontend-paket
cd frontend\dashboard
npm install
cd ..\..
```

---

### 2. Konfiguration

#### a. Backend (`.env`-fil)

Filen `tradingbot-backend/.env` finns redan konfigurerad med:

```
# Server & Frontend
HOST=127.0.0.1
PORT=8000
VITE_API_BASE=http://127.0.0.1:8000

# Autentisering (för utveckling)
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

#### b. Frontend (`.env`-fil)

Filen `frontend/.env` finns redan konfigurerad med:

```
VITE_API_BASE=http://127.0.0.1:8000
```

---

### 3. Starta programmet

#### 🚀 **Enkel start (rekommenderat)**

Kör detta kommando från projektets rotmapp:

```powershell
cd "C:\Users\salib\Desktop\Repo\Genesis"
.\scripts\start_normal.ps1
```

Detta startar automatiskt både backend och frontend i separata terminalfönster med **säker lokal konfiguration**.

#### 🔧 **Manuell start (alternativ)**

Om du föredrar att starta manuellt:

**Terminal 1 (Backend):**

```powershell
cd "C:\Users\salib\Desktop\Repo\Genesis\tradingbot-backend"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 (Frontend):**

```powershell
cd "C:\Users\salib\Desktop\Repo\Genesis\frontend\dashboard"
npm run dev
```

---

### 4. Öppna i webbläsaren

- **Dashboard:** [http://localhost:5173](http://localhost:5173)
- **Backend API:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **API-dokumentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### 5. Felsökning

#### Om backend inte startar:

- Kontrollera att Python är installerat: `python --version`
- Kontrollera att alla paket är installerade: `pip list`

#### Om frontend inte startar:

- Kontrollera att Node.js är installerat: `node --version`
- Kontrollera att npm är installerat: `npm --version`
- Installera om paket: `npm install`

#### Om API-anrop misslyckas:

- Kontrollera att backend körs på port 8000
- Kontrollera att `AUTH_REQUIRED=False` i `.env` för utveckling

_Alla sökvägar är nu konfigurerade för datorn Skynet._

Kolla start_normal.ps1 för mer detaljerad information.
