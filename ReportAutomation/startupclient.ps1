# Start ReportAutomation Client
# This script activates the virtual environment and runs the FastAPI client

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ReportAutomation Client Startup" -ForegroundColor Cyan
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
    & ".\.venv\Scripts\python.exe" -c "import fastapi, uvicorn, autogen_agentchat, autogen_ext" 2>$null
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
    Write-Host "Creating from .env.example..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host ".env file created" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "Please edit .env file with your configuration:" -ForegroundColor Cyan
    Write-Host "  - OPENAI_API_KEY (required for AutoGen agent)" -ForegroundColor White
    Write-Host ""
    $response = Read-Host "Do you want to edit it now? (y/n)"
    if ($response -eq "y") {
        notepad .env
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting ReportAutomation Client..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Application will be available at:" -ForegroundColor Yellow
Write-Host "  - UI: http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  - API Docs: http://127.0.0.1:8000/docs" -ForegroundColor White
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

# Run the FastAPI application using the venv Python
& ".\.venv\Scripts\uvicorn.exe" src.AutogenReports.main:app --host 127.0.0.1 --port 8000 --reload
