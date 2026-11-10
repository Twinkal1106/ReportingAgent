# Start MCP HTTP Server
# This script activates the virtual environment and runs the HTTP server

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MCP HTTP Server Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Creating..." -ForegroundColor Yellow
    & "C:\Program Files\Python312\python.exe" -m venv .venv
    Write-Host "Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# Check if requirements are installed
Write-Host "Checking dependencies..." -ForegroundColor Yellow
$requirementsInstalled = $true
try {
    & ".\.venv\Scripts\python.exe" -c "import fastapi, uvicorn, httpx" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $requirementsInstalled = $false
    }
} catch {
    $requirementsInstalled = $false
}

if (-not $requirementsInstalled) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    & ".\.venv\Scripts\pip.exe" install -r requirements.txt
    Write-Host "Dependencies installed" -ForegroundColor Green
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host ""
    Write-Host "WARNING: .env file not found!" -ForegroundColor Yellow
    Write-Host "Please create .env file with required configuration" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting MCP HTTP Server..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Server will be available at:" -ForegroundColor Yellow
Write-Host "  - Health: http://127.0.0.1:8001/health" -ForegroundColor White
Write-Host "  - API Docs: http://127.0.0.1:8001/docs" -ForegroundColor White
Write-Host ""

# Load environment variables from .env file
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

# Run the HTTP server
& ".\.venv\Scripts\python.exe" server.py
