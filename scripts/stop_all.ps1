# scripts/stop_all.ps1 - Windows PowerShell process cleanup
Write-Host "Stopping all CardioSDN Python processes..." -ForegroundColor Yellow

$procs = Get-Process python -ErrorAction SilentlyContinue
foreach ($p in $procs) {
    try {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    } catch {}
}

Write-Host "CardioSDN processes terminated." -ForegroundColor Green
