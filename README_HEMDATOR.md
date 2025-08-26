# Genesis Trading Bot - Hemdator Setup

**Specifik guide för din hemdator med alla vanliga problem och lösningar**

## 🏠 Din Hemdator-konfiguration

- **OS:** Windows 10 (22631)
- **Terminal:** PowerShell
- **Projekt-sökväg:** `[DIN_HEMDATOR_SÖKVÄG]` (ändra till din faktiska sökväg)
- **Python:** 3.11
- **Poetry:** INTE installerat än (kommer installeras)

## ✅ Rekommenderad snabbstart (Windows venv, utan Poetry)

Detta är den enklaste och mest stabila vägen, identisk med din nuvarande fungerande miljö.

```powershell
# 1) Skapa och aktivera ren venv
cd "[DIN_HEMDATOR_SÖKVÄG]"
python -m venv .venv_clean
& ".\.venv_clean\Scripts\Activate.ps1"
python -m pip install -U pip setuptools wheel

# 2) Installera beroenden
python -m pip install -r tradingbot-backend\requirements.txt
# Säker pinnings för HTTP‑stacken
python -m pip install "uvicorn[standard]==0.24.0" "click==8.1.7" "h11==0.14.0" pydantic-settings

# 3) .env
copy tradingbot-backend\env.example tradingbot-backend\.env
# Fyll BITFINEX_API_KEY/SECRET m.m. i tradingbot-backend\.env

# 4) Starta backend (scriptet väljer .venv_clean automatiskt)
.\scripts\start.ps1 start

# 5) Verifiera
Start-Sleep -Seconds 3
start http://127.0.0.1:8000/docs
```

Tips: `scripts/start.ps1` prioriterar `.venv_clean` och faller tillbaka till `.venv` om den inte finns.

### **Hitta din sökväg:**

```powershell
# Öppna PowerShell och kör:
pwd
# Eller
Get-Location

# Detta visar din nuvarande katalog
# Exempel: C:\Users\DittAnvändarnamn\Documents\Genesis
```

## 🚨 Vanliga Problem & Lösningar

### Problem − Null‑byte‑skript korruptar venv

Om du kör ett skript som tar bort null‑bytes, se till att EXKLUDERA `/.venv*`, `/node_modules`, `/frontend/dist`, `/tradingbot-backend/__pycache__`.

Symtom: paketfel som `cannot import FastAPI`, `ModuleNotFoundError: httptools`, h11‑API fel.

Lösning (snabb):

```powershell
# Skapa ny venv och använd den
python -m venv .venv_clean
& ".\.venv_clean\Scripts\Activate.ps1"
python -m pip install -U pip setuptools wheel
python -m pip install -r tradingbot-backend\requirements.txt
python -m pip install "uvicorn[standard]==0.24.0" "click==8.1.7" "h11==0.14.0" pydantic-settings
```

Starta om med `.\scripts\start.ps1 start`.

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

### **Första gången setup:**

```powershell
# 1. Klona projektet till din hemdator
git clone https://github.com/JohnCCarter/Genesis.git
cd Genesis

# 2. Byt till rätt branch
git checkout Genesis-Frontend

# 3. Installera Poetry
pip install poetry

# 4. Installera alla beroenden
poetry install

# 5. Skapa config-filer
python setup_config.py

# 6. Skapa .env-fil med dina API-nycklar
# Kopiera från env.example och lägg till dina Bitfinex-nycklar
# (env.example innehåller nu alla nödvändiga variabler)
```

### **Steg 1: Öppna PowerShell som Administrator**

```powershell
# Sätt execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### **Steg 2: Navigera till projekt**

```powershell
# Ändra till din faktiska sökväg på hemdatorn
cd "[DIN_HEMDATOR_SÖKVÄG]"
```

### **Steg 3: Installera och aktivera Poetry**

```powershell
# Installera Poetry (om inte redan gjort)
pip install poetry

# Skapa och aktivera Poetry-miljön
poetry install
poetry shell
```

### **Steg 4: Starta Backend**

```powershell
# Från projekt-root (VIKTIGT!)
poetry run uvicorn tradingbot-backend.main:app --reload --host 0.0.0.0 --port 8000
```

### **Steg 5: Starta Frontend (nytt PowerShell-fönster)**

```powershell
cd "[DIN_HEMDATOR_SÖKVÄG]\frontend\dashboard"
npm install
npm run dev
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

### **Senaste snapshot:**

- **Fil:** `Genesis_snapshot_20250825_102456.zip`
- **Datum:** 2025-08-25 10:24:56
- **Innehåll:** Alla optimeringar, README_HEMDATOR.md, uppdaterad env.example

## 📞 Snabbhjälp

### **Om allt krånglar:**

```powershell
# 1. Stäng alla PowerShell-fönster
# 2. Öppna ny PowerShell som Administrator
# 3. Kör från början:

cd "[DIN_HEMDATOR_SÖKVÄG]"
git checkout Genesis-Frontend  # Säkerställ rätt branch
pip install poetry
poetry install
poetry shell
poetry run uvicorn tradingbot-backend.main:app --reload --host 0.0.0.0 --port 8000
```

### **Om Poetry inte fungerar:**

```powershell
# Återinstallera Poetry
pip uninstall poetry
pip install poetry
poetry install
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

**Kom ihåg:** Kör ALLTID backend från projekt-root med `tradingbot-backend.main:app`! 🎯
