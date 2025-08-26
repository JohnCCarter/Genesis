# Genesis Trading Bot - Utvecklingsstartskript
# Detta skript startar projektet med Docker för att undvika beroendeproblem

Write-Host "🚀 Startar Genesis Trading Bot i utvecklingsläge..." -ForegroundColor Green

# Kontrollera om Docker är installerat
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker är inte installerat. Installera Docker Desktop först." -ForegroundColor Red
    exit 1
}

# Kontrollera om Docker körs
try {
    docker info | Out-Null
}
catch {
    Write-Host "❌ Docker körs inte. Starta Docker Desktop först." -ForegroundColor Red
    exit 1
}

# Skapa .env-fil om den inte finns
if (-not (Test-Path ".env")) {
    Write-Host "📝 Skapar .env-fil från template..." -ForegroundColor Yellow
    Copy-Item "tradingbot-backend/env.example" ".env" -ErrorAction SilentlyContinue
    Write-Host "⚠️  Redigera .env-filen med dina API-nycklar innan du fortsätter" -ForegroundColor Yellow
}

# Starta utvecklingsmiljön
Write-Host "🐳 Startar Docker-utvecklingsmiljö..." -ForegroundColor Blue
docker-compose up tradingbot-dev

Write-Host "✅ Genesis Trading Bot är nu tillgänglig på:" -ForegroundColor Green
Write-Host "   Backend: http://localhost:8000" -ForegroundColor Cyan
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
