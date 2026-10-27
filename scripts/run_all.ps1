# scripts/run_all.ps1 - Windows PowerShell one-command startup script
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " Starting CardioSDN Healthcare System Stack (Windows PowerShell) " -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Cyan

# 1. Initialize and Seed DB
python -u db/seed.py

# 2. Launch orchestrator
python -u scripts/run_all.py
