# Genesis Trading Bot - Venv Setup Script
# Kör detta script från projektets rotkatalog

Write-Host "🚀 Genesis Trading Bot - Venv Setup" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green

# Kontrollera att vi är i rätt katalog
if (-not (Test-Path "tradingbot-backend")) {
    Write-Host "❌ Fel: Kör detta script från projektets rotkatalog" -ForegroundColor Red
    exit 1
}

# Navigera till backend-katalogen
Set-Location tradingbot-backend

Write-Host "📁 Skapar virtuell miljö..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "⚠️  Venv finns redan. Vill du skapa en ny? (y/N)" -ForegroundColor Yellow
    $response = Read-Host
    if ($response -eq "y" -or $response -eq "Y") {
        Remove-Item -Recurse -Force venv
        python -m venv venv
    }
} else {
    python -m venv venv
}

Write-Host "🔧 Aktiverar virtuell miljö..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

Write-Host "📦 Installerar beroenden..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host "⚙️  Konfigurerar miljövariabler..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item env.example .env
    Write-Host "✅ .env-fil skapad från env.example" -ForegroundColor Green
    Write-Host "📝 Kom ihåg att redigera .env med dina API-nycklar!" -ForegroundColor Cyan
} else {
    Write-Host "✅ .env-fil finns redan" -ForegroundColor Green
}

Write-Host "🧪 Verifierar installation..." -ForegroundColor Yellow
try {
    python -c "import fastapi, uvicorn, socketio; print('✅ Alla beroenden installerade!')"
    Write-Host "🎉 Setup slutförd!" -ForegroundColor Green
} catch {
    Write-Host "❌ Fel vid verifiering: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "📋 Nästa steg:" -ForegroundColor Cyan
Write-Host "1. Redigera .env med dina Bitfinex API-nycklar" -ForegroundColor White
Write-Host "2. Starta servern: uvicorn main:app --reload" -ForegroundColor White
Write-Host "3. Öppna http://localhost:8000 i webbläsaren" -ForegroundColor White

# Återställ till ursprunglig katalog
Set-Location ..
