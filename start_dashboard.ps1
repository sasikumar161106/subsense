# SubSense Platform Dashboard Launcher
# ========================================
# Launches SubSense BFF Gateway (Port 3001) and Web Dashboard (Port 5174).

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Starting SubSense Mine Monitoring Platform (Direct Mode)...      " -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

$WorkspaceRoot = $PSScriptRoot

# 1. Start BFF Gateway (Port 3001)
Write-Host "[1/2] Launching BFF Gateway on http://localhost:3001..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WorkspaceRoot\dashboard'; npm run dev:bff"

# 2. Build Web Dashboard if dist is missing, then Start Web Dashboard (Port 5174)
if (-not (Test-Path "$WorkspaceRoot\dashboard\apps\web-dashboard\dist")) {
    Write-Host "[2/2] Building Web Dashboard production assets..." -ForegroundColor Yellow
    Push-Location "$WorkspaceRoot\dashboard"
    npm --workspace=packages/shared run build
    npm --workspace=apps/web-dashboard run build
    Pop-Location
}
Write-Host "[2/2] Launching Web Dashboard on http://localhost:5174..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WorkspaceRoot\dashboard'; npm --workspace=apps/web-dashboard run preview -- --port 5174"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " SubSense Dashboard online! Opening web browser...               " -ForegroundColor Yellow
Write-Host " Web Dashboard:   http://localhost:5174                          " -ForegroundColor White
Write-Host " BFF WebSocket:   ws://localhost:3001/ws/live                    " -ForegroundColor White
Write-Host " LoRa Ingest URL: http://localhost:3001/api/v1/telemetry/broadcast" -ForegroundColor White
Write-Host "=================================================================" -ForegroundColor Cyan

Start-Sleep -Seconds 3
Start-Process "http://localhost:5174"
