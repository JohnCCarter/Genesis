# Genesis Trading Bot – Hemdator Snabbstart

Endast det som behövs för att starta lokalt på hemdatorn.

- Miljöer

  - Windows 10/11, PowerShell
  - Python 3.11+ (använd virtuell miljö `.venv_clean`)
  - Node.js v18+

- Backend (start)

```powershell
cd "[DIN_HEMDATOR_SÖKVÄG]"
python -m venv .venv_clean                 # första gången
& ".\.venv_clean\Scripts\Activate.ps1"
python -m pip install -U pip setuptools wheel   # första gången
python -m pip install -r tradingbot-backend\requirements.txt    # första gången
cd tradingbot-backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- Frontend (start)

```powershell
cd "[DIN_HEMDATOR_SÖKVÄG]\\frontend\\dashboard"
npm install    # första gången
npm run dev
```

API: <http://127.0.0.1:8000/docs> • Dashboard: <http://127.0.0.1:5173>

Ersätt `[DIN_HEMDATOR_SÖKVÄG]` med din faktiska sökväg hemma.
