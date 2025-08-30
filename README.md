# Genesis Trading Bot

En avancerad trading bot för Bitfinex med live signals, regime detection och enhanced auto-trading.

## 🚀 Snabbstart

### 1. Klona projektet

```bash
git clone https://github.com/JohnCCarter/Genesis.git
cd Genesis
git checkout Genesis
```

### 2. Konfigurera environment

```bash
# Skapa virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell
# eller
.venv\Scripts\activate      # Windows Command Prompt

# Installera dependencies
pip install -r tradingbot-backend/requirements.txt
```

### 3. Konfigurera config-filer

```bash
# Kör setup script för att skapa config-filer från templates
python setup_config.py
```

### 4. Konfigurera API-nycklar

Skapa `.env` fil i root-mappen:

```env
BITFINEX_API_KEY=din_api_key
BITFINEX_API_SECRET=din_api_secret
```

### 5. Starta systemet

```bash
# Backend
cd tradingbot-backend
uvicorn main:app --reload

# Frontend (nytt terminal-fönster)
cd frontend/dashboard
npm install
npm run dev
```

## 📁 Config-filer

Efter setup skapas följande config-filer från templates:

- `tradingbot-backend/config/strategy_settings.json` - Strategi-inställningar
- `tradingbot-backend/config/trading_rules.json` - Trading-regler och tider
- `tradingbot-backend/config/performance_history.json` - Performance-historik

**Viktigt:** Redigera `trading_rules.json` och sätt `"paused": false` när du är redo att handla.

## 🎯 Funktioner

- **Live Trading Signals** med confidence scores och probabilities
- **Enhanced Auto-Trading** som kombinerar signals med befintligt system
- **Regime Detection** för automatisk strategi-anpassning
- **Performance Tracking** för enhanced trading
- **TTL-baserad Cache** för live data-uppdateringar
- **Risk Management** med circuit breakers och trading windows

## 📚 Dokumentation

Se `tradingbot-backend/IMPLEMENTATION_TODO_LIVE_TRADING.md` för detaljerad implementation guide.
