#!/bin/bash

# Genesis Trading Bot - Hemdator Miljöfix
# Kör detta script från projektets rotkatalog

echo "🔧 Genesis Trading Bot - Hemdator Miljöfix"
echo "=========================================="

# 1. Kontrollera att vi är i rätt katalog
if [ ! -d "tradingbot-backend" ]; then
    echo "❌ Fel: Kör detta script från projektets rotkatalog"
    exit 1
fi

echo "📋 Steg 1: Rensa och återskapa virtuell miljö"
cd tradingbot-backend

# Ta bort gammal venv om den finns
if [ -d "venv" ]; then
    echo "🗑️  Tar bort gammal virtuell miljö..."
    rm -rf venv
fi

# Skapa ny venv
echo "📁 Skapar ny virtuell miljö..."
python -m venv venv

# Aktivera venv
echo "🔧 Aktiverar virtuell miljö..."
source venv/Scripts/activate

echo "📦 Steg 2: Uppdatera pip och installera beroenden"
# Uppdatera pip
python -m pip install --upgrade pip

# Installera alla beroenden
echo "📦 Installerar projektberoenden..."
pip install -r requirements.txt

echo "⚙️  Steg 3: Konfigurera miljövariabler"
# Skapa .env om den inte finns
if [ ! -f ".env" ]; then
    echo "📝 Skapar .env-fil från template..."
    cp env.example .env
    echo "⚠️  Kom ihåg att redigera .env med dina API-nycklar!"
else
    echo "✅ .env-fil finns redan"
fi

echo "🧪 Steg 4: Verifiera installation"
# Testa kritiska paket
if python -c "import fastapi, uvicorn, socketio, pydantic_settings, talib; print('✅ Alla kritiska paket installerade')" 2>/dev/null; then
    echo "🎉 Backend-miljö fixad!"
else
    echo "❌ Problem med paketinstallation"
    exit 1
fi

echo "🌐 Steg 5: Fixa frontend"
cd ../frontend/dashboard

# Installera frontend-beroenden
echo "📦 Installerar frontend-beroenden..."
npm install

echo "✅ Frontend-beroenden installerade"

# Återställ till rotkatalog
cd ../..

echo ""
echo "🎉 Miljöfix slutförd!"
echo ""
echo "📋 Nästa steg:"
echo "1. Redigera tradingbot-backend/.env med dina API-nycklar"
echo "2. Starta backend: cd tradingbot-backend && source venv/Scripts/activate && uvicorn main:app --reload"
echo "3. Starta frontend: cd frontend/dashboard && npm run dev"
echo ""
echo "🌐 Servrar kommer att köra på:"
echo "   Backend: http://localhost:8000"
echo "   Frontend: http://localhost:5173 (eller 5174)"
