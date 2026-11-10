# FridgeChef AI - Local Development PowerShell Launcher
Write-Host "=================================================================" -ForegroundColor Green
Write-Host "  FRIDGECHEF AI — LOCAL DEMONSTRATION LAUNCHER (PowerShell)" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
Write-Host ""

$repoRoot = $PSScriptRoot

# 1. Start Backend in new process
Write-Host "Starting Backend API on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$repoRoot\api'; wsl -d Ubuntu -e bash -c `"cd '/mnt/c/Users/chara/Desktop/Fridge project/api' && ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`""

Start-Sleep -Seconds 4

# 2. Start Frontend in new process
Write-Host "Starting Frontend UI on http://localhost:5173 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$repoRoot\web'; npm run dev"

Start-Sleep -Seconds 3

# 3. Open Browser
Write-Host "Opening http://localhost:5173 in browser..." -ForegroundColor Yellow
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "FridgeChef is running! Press Enter to exit this launcher window." -ForegroundColor Green
Read-Host

