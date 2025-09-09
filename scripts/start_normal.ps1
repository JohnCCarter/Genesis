# Start TradingBot i normalt lage (endast lokala anslutningar)
# Detta script startar bade backend och frontend med sakert konfiguration

# Set console encoding to UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "Startar TradingBot i normalt lage (endast lokala anslutningar)..." -ForegroundColor Green
Write-Host ""

# Satt miljovariabler for sakert lage
$env:HOST = "127.0.0.1"

Write-Host "Miljovariabler satta:" -ForegroundColor Green
Write-Host "   HOST = $env:HOST" -ForegroundColor Cyan
Write-Host ""

# Starta backend i bakgrunden
Write-Host "Startar backend..." -ForegroundColor Blue
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'tradingbot-backend'; uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

# Vanta lite for att backend ska starta
Start-Sleep -Seconds 3

# Ta bort externa miljovariabler for sakerhet
Write-Host "Aterstaller frontend till sakert lage..." -ForegroundColor Blue
if (Test-Path "frontend\dashboard\.env") {
    Remove-Item "frontend\dashboard\.env" -Force
}

# Starta frontend i bakgrunden
Write-Host "Startar frontend..." -ForegroundColor Blue
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'frontend\dashboard'; npm run dev"

Write-Host ""
Write-Host "TradingBot startad i sakert lage!" -ForegroundColor Green
Write-Host ""
Write-Host "Lokala lankar:" -ForegroundColor Yellow
Write-Host "   Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "   Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
