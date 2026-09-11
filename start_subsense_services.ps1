# SubSense Platform Multi-Service Launcher
# =========================================
# Launches all SubSense backend and frontend services in dedicated PowerShell windows.

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Starting SubSense Mine Subsidence Early-Warning Platform...   " -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

$WorkspaceRoot = $PSScriptRoot

# 0. Ensure Android ADB Port 8022 is Forwarded for Termux SMS
Write-Host "[0/5] Verifying Android ADB Port Forwarding (8022 -> 8022)..." -ForegroundColor Magenta
try {
    adb forward tcp:8022 tcp:8022 2>$null
    Write-Host " ADB Port 8022: Active (Termux SMS Gateway)" -ForegroundColor Green
} catch {
    Write-Host " ADB warning: Ensure phone is plugged in with adb debugging active" -ForegroundColor Yellow
}

# 1. Start AI/ML Service (Port 8000)
Write-Host "[1/5] Launching AI/ML Service on http://localhost:8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WorkspaceRoot\ai-ml'; python -m uvicorn models.serving.app:app --host 0.0.0.0 --port 8000"

# 2. Start GIS Spatial Service (Port 8001)
Write-Host "[2/5] Launching GIS Service on http://localhost:8001..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WorkspaceRoot\gis'; python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8001"

# 3. Start Alerting Backend (Port 3000)
Write-Host "[3/5] Launching Alerting Engine on http://localhost:3000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WorkspaceRoot\alerting\backend'; npx ts-node src/api/server.ts"

# 4. Start BFF Gateway (Port 3001)
Write-Host "[4/5] Launching BFF Gateway on http://localhost:3001..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WorkspaceRoot\dashboard'; npm run dev:bff"

# 5. Start Web Dashboard (Port 5174)
Write-Host "[5/5] Launching Web Dashboard on http://localhost:5174..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WorkspaceRoot\dashboard'; npm --workspace=apps/web-dashboard run preview -- --port 5174"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " All SubSense services launched! Opening web dashboard...        " -ForegroundColor Yellow
Write-Host " Web Dashboard: http://localhost:5174                            " -ForegroundColor White
Write-Host " BFF Gateway:   http://localhost:3001                            " -ForegroundColor White
Write-Host " Alerting:      http://localhost:3000                            " -ForegroundColor White
Write-Host " AI/ML Docs:    http://localhost:8000/docs                       " -ForegroundColor White
Write-Host " GIS Docs:      http://localhost:8001/docs                       " -ForegroundColor White
Write-Host "=================================================================" -ForegroundColor Cyan

Start-Sleep -Seconds 3
Start-Process "http://localhost:5174"
