Param(
    [string]$ApiBase = "http://127.0.0.1:8000"
)

Push-Location "$PSScriptRoot\..\frontend\dashboard"
try {
    $env:VITE_API_BASE = $ApiBase
    npm run dev
} finally {
    Pop-Location
}


