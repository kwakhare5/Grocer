# ==============================================================================
# Grocer — Universal Verification Script (Lauren Tan Method)
# Default run is offline: schema check, lint, offline tests, web build.
# DB and live external calls are opt-in.
# ==============================================================================

param(
    [switch]$Db,
    [switch]$Live
)

Write-Host "=== 1. Checking Database Connectivity & Schema ===" -ForegroundColor Cyan
python scripts/verify_db.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Database verification failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== 2. Running Code Quality & Lint Checks ===" -ForegroundColor Cyan
ruff check backend tests
if ($LASTEXITCODE -ne 0) {
    Write-Host "Code quality lint checks failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== 3. Running Offline Test Suite ===" -ForegroundColor Cyan
pytest -q -m "not db and not live"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Offline test suite failed!" -ForegroundColor Red
    exit 1
}

if ($Db) {
    Write-Host "`n=== 3b. Running Database Suite (grocer_test) ===" -ForegroundColor Cyan
    pytest -q -m "db"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Database test suite failed!" -ForegroundColor Red
        exit 1
    }
}

if ($Live) {
    Write-Host "`n=== 3c. Running Live External Suite ===" -ForegroundColor Yellow
    Write-Host "This calls real Swiggy, LLM, WhatsApp and makes test writes. Check credentials first." -ForegroundColor Yellow
    pytest -q -m "live"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Live test suite failed!" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n=== 4. Checking Next.js Web Build ===" -ForegroundColor Cyan
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Next.js web build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== [PASS] Grocer verification complete ===" -ForegroundColor Green
exit 0
