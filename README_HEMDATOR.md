# Genesis Trading Bot - Hemdator Setup

**Specifik guide för din hemdator med alla vanliga problem och lösningar**

## 🏠 Din Hemdator-konfiguration

- **OS:** Windows 10/11
- **Terminal:** PowerShell
- **Projekt-sökväg:** `[DIN_HEMDATOR_SÖKVÄG]` ⚠️ **ÄNDRA DETTA till din riktiga hemdator-sökväg!**
- **Python:** 3.11+ (installera från python.org om du inte har det)
- **Node.js:** v18+ (installera från nodejs.org om du inte har det)
- **Poetry:** ❌ INTE nödvändigt! Vi använder enkel venv istället

## ✅ Rekommenderad snabbstart (Lokal venv, utan Poetry)

**LOKAL miljö rekommenderas** - isolerar dependencies från andra projekt och globala Python.
Detta är den säkraste och mest stabila vägen.

```powershell
# 1) Navigera till projektet (ÄNDRA SÖKVÄGEN!)
cd "[DIN_HEMDATOR_SÖKVÄG]"

# 2) Hämta senaste koden från jobbet
git pull origin main

# 3) Skapa och aktivera lokal venv för hemdatorn
python -m venv .venv_hem
& ".\.venv_hem\Scripts\Activate.ps1"
python -m pip install -U pip setuptools wheel

# 4) Installera Python dependencies
python -m pip install -r tradingbot-backend\requirements.txt

# 5) Skapa/uppdatera config-filer
python setup_config.py

# 6) Kopiera och redigera .env (ENDAST första gången)
copy tradingbot-backend\env.example tradingbot-backend\.env
# Öppna .env och lägg till dina Bitfinex API-nycklar

# 7) Installera frontend dependencies
cd frontend\dashboard
npm install
cd ..\..

# 8) Starta backend
cd tradingbot-backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 9) Starta frontend (nytt PowerShell-fönster)
cd "[DIN_HEMDATOR_SÖKVÄG]\frontend\dashboard"
npm run dev

# 10) Öppna i webbläsaren
# Backend API: http://127.0.0.1:8000/docs
# Frontend: http://127.0.0.1:5173
```

Tips: `scripts/start.ps1` prioriterar `.venv_clean` och faller tillbaka till `.venv` om den inte finns.

## 🚀 Daglig startup (efter första setup)

När du sitter hemma och vill starta projektet snabbt:

### **Backend startup:**
```powershell
# 1. Navigera till projektet
cd "[DIN_HEMDATOR_SÖKVÄG]"

# 2. Hämta eventuella uppdateringar från jobbet
git pull origin main

# 3. Aktivera lokal miljö
& ".\.venv_hem\Scripts\Activate.ps1"

# 4. Starta backend
cd tradingbot-backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### **Frontend startup (nytt PowerShell-fönster):**
```powershell
cd "[DIN_HEMDATOR_SÖKVÄG]\frontend\dashboard"
npm run dev
```

### **Snabbkommandon:**
```powershell
# Öppna webbläsare direkt till rätt sidor
start http://127.0.0.1:8000/docs    # Backend API
start http://127.0.0.1:5173         # Frontend Dashboard

# Kontrollera att allt fungerar
curl http://127.0.0.1:8000/health   # Backend health check
```

### **🔒 Nya säkerhetsförbättringar (2025-08-29):**

- ✅ **Path traversal vulnerabilities** fixade (CWE-022)
- ✅ **Black updated** till 25.1.0 (ReDoS fix)
- ✅ **Dependencies updated**: requests, beautifulsoup4, pycodestyle, pyflakes
- ✅ **Secure model directory**: `config/models/` för ML-filer
- ✅ **Input sanitization** för API endpoints
- ✅ **CodeQL security analysis** uppsatt för kontinuerlig scanning

## 🚨 Vanliga Problem & Lösningar

### **Problem 1: "python command not found" på hemdatorn**

**Felmeddelande:**
```
'python' is not recognized as an internal or external command
```

**Lösning:**
```powershell
# Installera Python från python.org
# ELLER använd Microsoft Store version
# ELLER kolla om du har py istället:
py --version
py -m venv .venv_hem  # Använd py istället för python
```

### **Problem 2: "Access denied" när du skapar venv**

**Lösning:**
```powershell
# Öppna PowerShell som Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# ELLER använd annan mapp:
cd C:\temp\Genesis  # Istället för Program Files eller skyddade mappar
```

### **Problem 3: Git pull kräver autentisering**

**Lösning:**
```powershell
# Första gången, konfigurera git:
git config --global user.name "Ditt Namn"
git config --global user.email "din.email@exempel.com"

# Om du får autentiseringsfel:
git remote -v  # Kolla remote URL
# Använd GitHub personal access token istället för lösenord
```

### **Problem 4: Port 8000 eller 5173 är upptagen på hemdatorn**

**Lösning:**
```powershell
# Hitta vad som använder porten:
netstat -ano | findstr :8000
netstat -ano | findstr :5173

# Använd andra portar:
uvicorn main:app --reload --port 8001  # Backend
npm run dev -- --port 5174            # Frontend
```

### **Problem 5: npm install misslyckas**

**Lösning:**
```powershell
# Rensa npm cache:
npm cache clean --force

# Installera med verbose output:
npm install --verbose

# Om det fortfarande misslyckas, ta bort node_modules:
Remove-Item node_modules -Recurse -Force
Remove-Item package-lock.json
npm install
```

### **Problem 0: Poetry inte installerat**

**Felmeddelande:**

```
'poetry' is not recognized as an internal or external command
```

**Lösning:**

```powershell
# Installera Poetry först
pip install poetry

# Verifiera installation
poetry --version
```

### **Problem 1: Poetry-konfiguration fel**

**Felmeddelande:**

```
The Poetry configuration is invalid:
  - Either [project.name] or [tool.poetry.name] is required in package mode.
  - Either [project.version] or [tool.poetry.version] is required in package mode.
```

**Lösning:**

```powershell
# Kör ALLTID från projekt-root, INTE från backend-mappen
cd "[DIN_HEMDATOR_SÖKVÄG]"

# Aktivera Poetry-miljön (skapas automatiskt vid första körning)
poetry shell

# Starta backend från projekt-root
poetry run uvicorn tradingbot-backend.main:app --reload --host 0.0.0.0 --port 8000
```

### **Problem 2: ModuleNotFoundError: No module named 'config'**

**Felmeddelande:**

```
ModuleNotFoundError: No module named 'config'
```

**Lösning:**

```powershell
# ❌ FEL - från projekt-root
poetry run uvicorn main:app --reload

# ✅ RÄTT - från projekt-root med full sökväg
poetry run uvicorn tradingbot-backend.main:app --reload --host 0.0.0.0 --port 8000
```

### **Problem 3: PowerShell Execution Policy**

**Felmeddelande:**

```
File cannot be loaded because running scripts is disabled on this system.
```

**Lösning:**

```powershell
# Kör som Administrator och kör:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Eller för denna session:
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

### **Problem 4: Python-versioner**

**Kontrollera Python-version:**

```powershell
python --version  # Ska vara 3.11.x
poetry env info   # Ska visa rätt Python-version
```

**Om fel version:**

```powershell
# Skapa ny Poetry-miljö med rätt Python
poetry env remove python
poetry env use python3.11
poetry install
```

### **Problem 5: Port 8000 upptagen**

**Kontrollera:**

```powershell
netstat -ano | findstr :8000
```

**Lösning:**

```powershell
# Använd annan port
poetry run uvicorn tradingbot-backend.main:app --reload --host 0.0.0.0 --port 8001

# Eller döda processen
taskkill /PID [PID_NUMMER] /F
```

## 🚀 Snabbstart för Hemdator

### **Första gången setup på hemdatorn:**

#### **Steg 1: Förutsättningar**
```powershell
# Kontrollera att du har rätt verktyg installerade
python --version    # Bör vara 3.11+
node --version      # Bör vara v18+
git --version       # För att hämta kod från jobbet

# Om något saknas:
# Python: https://python.org/downloads
# Node.js: https://nodejs.org
# Git: https://git-scm.com/downloads
```

#### **Steg 2: Hämta projektet från jobbet**
```powershell
# Klona projektet till din hemdator (ÄNDRA SÖKVÄGEN!)
cd "[DIN_FÖRÄLDER_MAPP]"
git clone https://github.com/JohnCCarter/Genesis.git
cd Genesis

# ELLER om projektet redan finns hemma:
cd "[DIN_HEMDATOR_SÖKVÄG]"
git pull origin main
git status  # Kontrollera att du är på main branch
```

#### **Steg 3: Setup Python-miljö**
```powershell
# Skapa LOKAL Python-miljö (isolerad från andra projekt)
python -m venv .venv_hem
& ".\.venv_hem\Scripts\Activate.ps1"
python -m pip install -U pip setuptools wheel
python -m pip install -r tradingbot-backend\requirements.txt
```

#### **Steg 4: Setup konfiguration**
```powershell
# Skapa config-filer
python setup_config.py

# Kopiera .env-template och lägg till dina API-nycklar
copy tradingbot-backend\env.example tradingbot-backend\.env
# VIKTIGT: Öppna .env i textredigerare och lägg till:
# BITFINEX_API_KEY=din_api_nyckel
# BITFINEX_API_SECRET=din_api_secret
```

#### **Steg 5: Setup frontend**
```powershell
cd frontend\dashboard
npm install
cd ..\..
```

#### **Steg 6: Testa att allt fungerar**
```powershell
# Starta backend
cd tradingbot-backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# I nytt PowerShell-fönster, starta frontend:
cd "[DIN_HEMDATOR_SÖKVÄG]\frontend\dashboard"
npm run dev

# Testa i webbläsare:
# http://127.0.0.1:8000/docs (Backend API)
# http://127.0.0.1:5173 (Frontend)
```

### **Steg 1: Öppna PowerShell som Administrator**

```powershell
# Sätt execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### **Steg 2: Daglig startup (efter första setup)**

```powershell
# Backend startup
cd "C:\Users\fa06662\HCP\Hämtade filer\Genesis"
& ".\.venv_clean\Scripts\Activate.ps1"
cd tradingbot-backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### **Steg 3: Frontend startup (nytt PowerShell-fönster)**

```powershell
cd "C:\Users\fa06662\HCP\Hämtade filer\Genesis\frontend\dashboard"
npm run dev
```

### **Steg 4: Snabb verifiering**

```powershell
# Testa att allt fungerar
start http://127.0.0.1:8000/docs    # Backend API
start http://127.0.0.1:5173         # Frontend Dashboard
```

## 🔧 Felsökning för Hemdator

### **Kontrollera miljö:**

```powershell
# Kontrollera Python-version
python --version

# Kontrollera Poetry
poetry --version

# Kontrollera Node.js
node --version
npm --version

# Kontrollera katalog
pwd
```

### **Rensa cache:**

```powershell
# Rensa Python cache
Get-ChildItem -Path "tradingbot-backend" -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force

# Rensa Poetry cache
poetry cache clear . --all

# Rensa npm cache
cd frontend/dashboard
npm cache clean --force
```

### **Återinstallera beroenden:**

```powershell
# Poetry
poetry install --sync

# NPM
cd frontend/dashboard
npm install
```

### **Kolla loggar:**

```powershell
# Backend-loggar
Get-Content "tradingbot-backend\tradingbot.log" -Tail 50

# Sök efter fel
Get-Content "tradingbot-backend\tradingbot.log" -Tail 100 | Select-String "ERROR"

# Sök efter API-anrop
Get-Content "tradingbot-backend\tradingbot.log" -Tail 100 | Select-String "REST API"
```

## 📋 Kommandon för Hemdator

### **Backend-kommandon:**

```powershell
# Aktivera miljö
poetry shell

# Starta från projekt-root
poetry run uvicorn tradingbot-backend.main:app --reload --host 0.0.0.0 --port 8000

# Starta med debug
poetry run uvicorn tradingbot-backend.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug

# Starta utan reload (produktion)
poetry run uvicorn tradingbot-backend.main:app --host 0.0.0.0 --port 8000
```

### **Frontend-kommandon:**

```powershell
# Navigera till frontend
cd "[DIN_HEMDATOR_SÖKVÄG]\frontend\dashboard"

# Installera beroenden
npm install

# Starta utvecklingsserver
npm run dev

# Bygg för produktion
npm run build
```

### **Docker-kommandon:**

```powershell
# Starta hela stacken
docker-compose up tradingbot-dev

# Endast backend
docker-compose up tradingbot-backend

# Stoppa alla
docker-compose down
```

## 🎯 Optimeringsstatus

### **Implementerade optimeringar:**

- ✅ **Förbättrad cache-strategi** (10 min TTL)
- ✅ **Request cache** (30 sekunder TTL)
- ✅ **Failure tracking** (1 minut cooldown)
- ✅ **Data coordinator** (delar data mellan tjänster)
- ✅ **Optimerad scheduler** (30 min intervall)

### **Förväntade förbättringar:**

- **70-80% färre API-anrop** till Bitfinex
- **Bättre prestanda** genom minskad nätverksbelastning
- **Mindre risk för rate limiting**
- **Stabilare system**

## 🔗 Användbara länkar

- **Backend:** http://localhost:8000
- **Frontend:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs
- **Loggar:** `tradingbot-backend\tradingbot.log`

## 📸 Snapshots och Backups

### **Skapa snapshot av projektet:**

```powershell
# Skapa timestamp
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$snapshotName = "Genesis_snapshot_${timestamp}.zip"

# Skapa backup (exkluderar loggfiler som kan vara låsta)
Compress-Archive -Path "tradingbot-backend", "frontend", "scripts", "README.md", "README_HEMDATOR.md", "pyproject.toml", "docker-compose.yml" -DestinationPath "backups\$snapshotName" -Force

Write-Host "Snapshot skapad: $snapshotName"
```

### **Återställ från snapshot:**

```powershell
# Lista tillgängliga snapshots
Get-ChildItem "backups\Genesis_snapshot_*.zip" | Sort-Object LastWriteTime -Descending

# Återställ från senaste snapshot
$latestSnapshot = Get-ChildItem "backups\Genesis_snapshot_*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Expand-Archive -Path $latestSnapshot.FullName -DestinationPath "." -Force

Write-Host "Återställt från: $($latestSnapshot.Name)"
```

### **Automatisk snapshot före stora ändringar:**

```powershell
# Kör detta före stora uppdateringar eller experiment
.\scripts\create_snapshot.ps1

# Med beskrivning
.\scripts\create_snapshot.ps1 -Description "Före optimering av cache-system"
```

### **Senaste säkerhetsuppdateringar:**

- **Datum:** 2025-08-29
- **Innehåll:** Path traversal fixes, Black 25.1.0, dependency updates
- **Status:** ✅ CodeQL High severity alerts #22 och #23 lösta
- **Branch:** Migrerat till `main` från `Genesis-Frontend`

## 📞 Snabbhjälp

### **Om allt krånglar:**

```powershell
# 1. Stäng alla PowerShell-fönster
# 2. Öppna ny PowerShell
# 3. Kör från början:

cd "C:\Users\fa06662\HCP\Hämtade filer\Genesis"
git status  # Kontrollera att du är på main branch

# Skapa ny ren venv
python -m venv .venv_clean
& ".\.venv_clean\Scripts\Activate.ps1"
python -m pip install -U pip setuptools wheel
python -m pip install -r tradingbot-backend\requirements.txt

# Starta backend
cd tradingbot-backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### **Om du vill använda Poetry ändå:**

```powershell
# Poetry är INTE nödvändigt men om du vill:
pip install poetry
poetry install
poetry shell
poetry run uvicorn tradingbot-backend.main:app --reload --host 0.0.0.0 --port 8000
```

### **Om npm inte fungerar:**

```powershell
# Rensa npm cache och återinstallera
cd frontend/dashboard
npm cache clean --force
npm install
```

## 🔧 Kodkvalitet och Linting

### **Backend (Python):**

```powershell
# Formatera kod
poetry run black tradingbot-backend/

# Lint och fixa automatiskt
poetry run ruff check tradingbot-backend/ --fix

# Säkerhetsscanning
poetry run bandit -r tradingbot-backend/

# Säkerhetsaudit av dependencies
poetry run pip-audit --requirement tradingbot-backend/requirements.txt

# Type checking
poetry run mypy tradingbot-backend/

# Test med coverage
poetry run pytest tradingbot-backend/tests/ --cov=tradingbot-backend --cov-report=html
```

### **Frontend (TypeScript/React):**

```powershell
cd frontend/dashboard

# Installera dev-verktyg
npm install

# Lint och fixa
npm run lint:fix

# Formatera kod
npm run format

# Type-check
npm run type-check
```

### **Pre-commit hooks:**

```powershell
# Installera pre-commit
poetry run pre-commit install

# Kör alla hooks manuellt
poetry run pre-commit run --all-files
```

---

## 🛡️ Säkerhetsstatus (2025-08-29)

### **✅ Lösta säkerhetsproblem:**

1. **Path Traversal (CWE-022)** - High severity
   - `services/prob_train.py` - Robust path validation
   - `rest/routes.py` - Input sanitization och containment checks
   - Säker `config/models/` directory för ML-modeller

2. **Black ReDoS Vulnerability** - Moderate severity
   - Uppdaterat från 24.8.0 till 25.1.0

3. **Dependency Updates:**
   - `beautifulsoup4`: 4.12.2 → 4.13.5
   - `requests`: 2.32.4 → 2.32.5
   - `pycodestyle`: 2.12.1 → 2.14.0
   - `pyflakes`: 3.2.0 → 3.4.0

### **🔍 CodeQL Security Analysis:**
- Lokal scanning uppsatt för kontinuerlig säkerhetsanalys
- GitHub Dependabot alerts #22 och #23 lösta
- Alle High severity findings åtgärdade

### **📋 Kommande CI/CD status:**
När du pushar kommer alla tester att passera:
- ✅ Backend CI (Windows)
- ✅ Frontend CI (Ubuntu)
- ✅ Säkerhetscanning
- ✅ Linting och formatting

---

**Kom ihåg:** Använd `uvicorn main:app` från `tradingbot-backend/` directory! 🎯
