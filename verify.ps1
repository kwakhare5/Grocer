# ==============================================================================
# Grocer v1.0 — Universal Verification Script (Lauren Tan Method)
# Checks environment, database connection, and runs full test suite.
# ==============================================================================

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

Write-Host "`n=== 3. Running Contract & Invariant Test Suite ===" -ForegroundColor Cyan
pytest -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "Test suite failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== 4. Checking Next.js Web Build ===" -ForegroundColor Cyan
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Next.js web build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== [PASS] Grocer v1.0 Universal Verification Complete! 100% Green ===" -ForegroundColor Green
exit 0
