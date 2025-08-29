#!/bin/bash

# Genesis Trading Bot - Venv Setup Script (Bash version)
# Kör detta script från projektets rotkatalog

echo "🚀 Genesis Trading Bot - Venv Setup"
echo "====================================="

# Kontrollera att vi är i rätt katalog
if [ ! -d "tradingbot-backend" ]; then
    echo "❌ Fel: Kör detta script från projektets rotkatalog"
    exit 1
fi

# Navigera till backend-katalogen
cd tradingbot-backend

echo "📁 Skapar virtuell miljö..."
if [ -d "venv" ]; then
    echo "⚠️  Venv finns redan. Vill du skapa en ny? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf venv
        python -m venv venv
    fi
else
    python -m venv venv
fi

echo "🔧 Aktiverar virtuell miljö..."
source venv/Scripts/activate

echo "📦 Installerar beroenden..."
pip install -r requirements.txt

echo "⚙️  Konfigurerar miljövariabler..."
if [ ! -f ".env" ]; then
    cp env.example .env
    echo "✅ .env-fil skapad från env.example"
    echo "📝 Kom ihåg att redigera .env med dina API-nycklar!"
else
    echo "✅ .env-fil finns redan"
fi

echo "🧪 Verifierar installation..."
if python -c "import fastapi, uvicorn, socketio; print('✅ Alla beroenden installerade!')" 2>/dev/null; then
    echo "🎉 Setup slutförd!"
else
    echo "❌ Fel vid verifiering"
fi

echo ""
echo "📋 Nästa steg:"
echo "1. Redigera .env med dina Bitfinex API-nycklar"
echo "2. Starta servern: uvicorn main:app --reload"
echo "3. Öppna http://localhost:8000 i webbläsaren"

# Återställ till ursprunglig katalog
cd ..
