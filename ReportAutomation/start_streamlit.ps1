# Start FedEx Reporting Agent - Streamlit Application
# This script activates the virtual environment and starts Streamlit on port 8501

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FedEx Reporting Agent - Streamlit" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Activate virtual environment
if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    Write-Host "Virtual environment not found! Please run startupclient.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

Write-Host ""
Write-Host "Starting Streamlit..." -ForegroundColor Green
Write-Host "  - Local URL: http://localhost:8501" -ForegroundColor Cyan
Write-Host ""

# Run Streamlit
& ".\.venv\Scripts\streamlit.exe" run src\AutogenReports\streamlit_app.py --server.port 8501 --server.headless false --browser.gatherUsageStats false
