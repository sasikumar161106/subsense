# SubSense LoRa SX126x Network Launcher
# =====================================
# Launches SubSense LoRa edge nodes or the surface gateway bridge.

param (
    [string]$Port = "COM3",
    [int]$Freq = 865,
    [string]$Role = ""
)

$WorkspaceRoot = $PSScriptRoot

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " SubSense LoRa SX126x Network Deployment Launcher                " -ForegroundColor Yellow
Write-Host " Frequency: $Freq MHz (India ISM Band) | Default Port: $Port     " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# Detect connected ports
$DetectedPorts = python -c "import serial.tools.list_ports; print(','.join([p.device for p in serial.tools.list_ports.comports()]))" 2>$null
if ($DetectedPorts) {
    Write-Host "Detected Serial Ports: $DetectedPorts" -ForegroundColor Green
} else {
    Write-Host "No active hardware serial ports detected." -ForegroundColor Yellow
}

if (-not $Role) {
    Write-Host "`nSelect LoRa Execution Mode:" -ForegroundColor White
    Write-Host " [1] Standalone LoRa Surface Gateway Node (Direct Ingest -> AI/ML & BFF)" -ForegroundColor Green
    Write-Host " [2] Surface Gateway Bridge (Direct LoRa mode @ 9600 baud)" -ForegroundColor Green
    Write-Host " [3] Surface Gateway Bridge (ESP32 USB Serial mode @ 115200 baud)" -ForegroundColor Green
    Write-Host " [4] Standalone LoRa Underground Sensor Node (Field Transmitter / Simulation)" -ForegroundColor Green
    Write-Host " [5] Hybrid Sensor Node (ESP32 USB Ingest -> LoRa 865 MHz Broadcast)" -ForegroundColor Green
    Write-Host " [6] Standalone LoRa Gallery Relay Node (Multi-Hop Repeater)" -ForegroundColor Green
    Write-Host " [7] Run LoRa SX126x Hardware Diagnostics on $Port" -ForegroundColor Cyan
    Write-Host " [8] Run Complete System (Backend Services + LoRa Gateway)" -ForegroundColor Magenta
    
    $Choice = Read-Host "`nEnter selection (1-8) [Default: 1]"
    if (-not $Choice) { $Choice = "1" }
} else {
    $Choice = $Role
}

switch ($Choice) {
    "1" {
        Write-Host "`nLaunching Standalone Surface Gateway Node on $Port ($Freq MHz)..." -ForegroundColor Green
        python "$WorkspaceRoot\edge\lora_nodes\main.py" --mode gateway --port $Port --freq $Freq
    }
    "2" {
        Write-Host "`nLaunching Gateway Bridge in Direct-LoRa mode on $Port ($Freq MHz)..." -ForegroundColor Green
        python "$WorkspaceRoot\gateway-bridge\bridge.py" --mode direct-lora --port $Port --lora-freq $Freq
    }
    "3" {
        Write-Host "`nLaunching Gateway Bridge in ESP32 Serial mode on $Port (115200 baud)..." -ForegroundColor Green
        python "$WorkspaceRoot\gateway-bridge\bridge.py" --mode serial --port $Port --baud 115200
    }
    "4" {
        $Anomaly = Read-Host "Simulate physical tilt hazard (>4.0 deg)? (y/N)"
        if ($Anomaly -eq "y" -or $Anomaly -eq "Y") {
            python "$WorkspaceRoot\edge\lora_nodes\main.py" --mode sensor --port $Port --freq $Freq --anomaly
        } else {
            python "$WorkspaceRoot\edge\lora_nodes\main.py" --mode sensor --port $Port --freq $Freq
        }
    }
    "5" {
        $EspPort = Read-Host "Enter ESP32 Serial Port (e.g. COM3 or /dev/ttyUSB0) [Default: COM3]"
        if (-not $EspPort) { $EspPort = "COM3" }
        Write-Host "`nLaunching Hybrid Sensor Node (ESP32 on $EspPort -> LoRa on $Port @ $Freq MHz)..." -ForegroundColor Green
        python "$WorkspaceRoot\edge\lora_nodes\main.py" --mode sensor --port $Port --freq $Freq --esp32-port $EspPort
    }
    "6" {
        Write-Host "`nLaunching LoRa Relay Node on $Port ($Freq MHz)..." -ForegroundColor Green
        python "$WorkspaceRoot\edge\lora_nodes\main.py" --mode relay --port $Port --freq $Freq
    }
    "7" {
        Write-Host "`nRunning Hardware Diagnostic Suite on $Port..." -ForegroundColor Cyan
        python "$WorkspaceRoot\edge\scripts\diagnose_lora.py" --port $Port --freq $Freq
    }
    "8" {
        Write-Host "`n[1/2] Starting SubSense Backend and Dashboard..." -ForegroundColor Yellow
        Start-Process powershell -ArgumentList "-File", "`"$WorkspaceRoot\start_subsense_services.ps1`""
        Write-Host "[2/2] Starting Surface LoRa Gateway on $Port..." -ForegroundColor Green
        python "$WorkspaceRoot\edge\lora_nodes\main.py" --mode gateway --port $Port --freq $Freq
    }
    default {
        Write-Host "Invalid selection. Exiting." -ForegroundColor Red
    }
}
