# ─── SubSense Sensor Monitoring Dashboard ─── Windows Launcher ───
# Single-process: Python backend + embedded React dashboard on :8080

Write-Host "`n╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   SubSense - Sensor Monitoring Dashboard         ║" -ForegroundColor Cyan
Write-Host "║   Single-Process Monitor (No Node.js needed)     ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

Write-Host "[1/3] Checking dependencies..." -ForegroundColor Yellow
pip install -q -r "$dir\requirements.txt"

Write-Host "[2/3] Checking ADB connection (Termux SMS)..." -ForegroundColor Yellow
try {
    adb forward tcp:8022 tcp:8022 2>$null | Out-Null
    Write-Host "      ✓ ADB forwarded tcp:8022 -> tcp:8022" -ForegroundColor Green
} catch {
    Write-Host "      ℹ ADB not running (Termux SMS will use LAN or fallback)." -ForegroundColor DarkYellow
}

Write-Host "[3/3] Starting SubSense Monitor on port 8080..." -ForegroundColor Yellow
Write-Host "`n══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ SubSense Monitor is LIVE!" -ForegroundColor Green
Write-Host "  🌐 Dashboard URL:  http://localhost:8080" -ForegroundColor Cyan
Write-Host "  📡 Serial Ports:   Auto-scanning (COM14, COM15, etc.)" -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════════════`n" -ForegroundColor Green

python "$dir\app.py"
