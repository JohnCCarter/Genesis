# Genesis Trading Bot - Snapshot Script
# Skapar en backup av projektet med timestamp

param(
    [string]$Description = ""
)

# Skapa timestamp
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$snapshotName = "Genesis_snapshot_${timestamp}.zip"

# Skapa backups-mapp om den inte finns
if (!(Test-Path "backups")) {
    New-Item -ItemType Directory -Path "backups" -Force
    Write-Host "Skapade backups-mapp"
}

# Lista filer att inkludera
$filesToBackup = @(
    "tradingbot-backend",
    "frontend",
    "scripts",
    "README.md",
    "README_HEMDATOR.md",
    "pyproject.toml",
    "docker-compose.yml"
)

Write-Host "Skapar snapshot: $snapshotName"

try {
    # Skapa backup
    Compress-Archive -Path $filesToBackup -DestinationPath "backups\$snapshotName" -Force

    # Lägg till beskrivning om angiven
    if ($Description) {
        $descriptionFile = "backups\${snapshotName}.txt"
        $Description | Out-File -FilePath $descriptionFile -Encoding UTF8
        Write-Host "Beskrivning sparad: $descriptionFile"
    }

    Write-Host "✅ Snapshot skapad framgångsrikt: $snapshotName"
    Write-Host "📁 Plats: backups\$snapshotName"

    # Visa senaste snapshots
    Write-Host "`n📋 Senaste snapshots:"
    Get-ChildItem "backups\Genesis_snapshot_*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | ForEach-Object {
        Write-Host "  - $($_.Name) ($($_.LastWriteTime.ToString('yyyy-MM-dd HH:mm')))"
    }

}
catch {
    Write-Host "❌ Fel vid skapande av snapshot: $($_.Exception.Message)"
    Write-Host "💡 Tips: Stäng alla program som använder projektfiler"
    exit 1
}
