# ==============================================================================
# Agri_mini - One-Command System Startup Script (PowerShell)
# Starts FastAPI backend (port 8001) and Frontend server (port 5500)
# simultaneously in separate PowerShell windows and opens the browser.
# ==============================================================================

Write-Host "======================================================================" -ForegroundColor Green
Write-Host "  Agri_mini -- AI Agricultural Decision-Support Platform Startup" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green

# 1. Resolve Project Paths
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { "D:\Agri_mini" }
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

# Fallback to direct path if needed
if (-Not (Test-Path $VenvPython)) {
    $VenvPython = "D:\Agri_mini\.venv\Scripts\python.exe"
}

# 2. Check Virtual Environment
if (-Not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Python virtual environment not found at: $VenvPython" -ForegroundColor Red
    Write-Host "Please ensure the virtual environment is set up at D:\Agri_mini\.venv" -ForegroundColor Yellow
    exit 1
}

# 3. Check Backend and Frontend Directories
if (-Not (Test-Path $BackendDir)) {
    Write-Host "[ERROR] Backend folder not found at: $BackendDir" -ForegroundColor Red
    exit 1
}

if (-Not (Test-Path $FrontendDir)) {
    Write-Host "[ERROR] Frontend folder not found at: $FrontendDir" -ForegroundColor Red
    exit 1
}

# 4. Check Port Availability (Ports 8001 and 5500)
function Test-PortInUse {
    param([int]$Port)

    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($null -ne $conn) {
            return $true
        }
    } catch {}

    try {
        $ipProperties = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
        $listeners = $ipProperties.GetActiveTcpListeners()
        if ($listeners.Port -contains $Port) {
            return $true
        }
    } catch {}

    return $false
}

$occupiedPorts = @()

if (Test-PortInUse 8001) {
    $occupiedPorts += 8001
}

if (Test-PortInUse 5500) {
    $occupiedPorts += 5500
}

if ($occupiedPorts.Count -gt 0) {
    Write-Host ""
    Write-Host "[ERROR] Startup aborted. The following port(s) are already in use:" -ForegroundColor Red
    foreach ($port in $occupiedPorts) {
        Write-Host "  - Port $port is already in use." -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Please stop the existing process(es) on these port(s) before running this script." -ForegroundColor Yellow
    exit 1
}

Write-Host "[INFO] Environment verified: $VenvPython" -ForegroundColor Cyan
Write-Host "[INFO] Ports 8001 and 5500 are available." -ForegroundColor Cyan

# 5. Start Backend and Frontend in Separate PowerShell Windows
$backendCommand = "`$Host.UI.RawUI.WindowTitle = 'Agri_mini - Backend (FastAPI :8001)'; & `"$VenvPython`" -m uvicorn app.main:app --host 127.0.0.1 --port 8001"
$frontendCommand = "`$Host.UI.RawUI.WindowTitle = 'Agri_mini - Frontend (HTTP Server :5500)'; & `"$VenvPython`" -m http.server 5500"

Write-Host "[INFO] Launching FastAPI backend in a separate window..." -ForegroundColor Cyan
Start-Process powershell.exe -WorkingDirectory $BackendDir -ArgumentList "-NoExit -Command `"$backendCommand`""

Write-Host "[INFO] Launching Frontend server in a separate window..." -ForegroundColor Cyan
Start-Process powershell.exe -WorkingDirectory $FrontendDir -ArgumentList "-NoExit -Command `"$frontendCommand`""

# Allow brief moment for services to bind and initialize
Start-Sleep -Seconds 2

# 6. Print Service Endpoints
Write-Host ""
Write-Host "Backend: http://127.0.0.1:8001" -ForegroundColor Green
Write-Host "Health: http://127.0.0.1:8001/health" -ForegroundColor Green
Write-Host "API Docs: http://127.0.0.1:8001/docs" -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:5500" -ForegroundColor Green
Write-Host ""

# 7. Automatically Open Frontend in Default Browser
Write-Host "[INFO] Opening frontend in default browser..." -ForegroundColor Cyan
Start-Process "http://127.0.0.1:5500"

Write-Host "[INFO] Both services are running in their respective windows." -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
