# 1-Click Verification Script for GROCER
# Runs all unit & integration test suites, optional Docker Postgres E2E suite, and frontend linter.

$ErrorActionPreference = "Stop"

Write-Host "`n=== 1. Running Unit & Integration Tests (Layers 1-4, Invariants, Advocate) ===" -ForegroundColor Cyan
pytest --ignore=backend/tests/test_whatsapp_postgres_e2e.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Unit & integration tests failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "`n=== 2. Checking PostgreSQL Container for E2E Suite ===" -ForegroundColor Cyan
$pgAvailable = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect("127.0.0.1", 5432, $null, $null)
    $success = $iar.AsyncWaitHandle.WaitOne(1000, $false)
    if ($success -and $tcp.Connected) {
        $pgAvailable = $true
        $tcp.EndConnect($iar)
    }
    $tcp.Close()
} catch {
    $pgAvailable = $false
}

if ($pgAvailable) {
    Write-Host "PostgreSQL is reachable on port 5432. Running full WhatsApp Postgres E2E suite..." -ForegroundColor Green
    pytest backend/tests/test_whatsapp_postgres_e2e.py
    if ($LASTEXITCODE -ne 0) {
        Write-Error "E2E tests failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
} else {
    Write-Host "Note: Local PostgreSQL container not running on 5432. E2E suite skipped for unit verification pass." -ForegroundColor Yellow
}

Write-Host "`n=== 3. Running Frontend Linter ===" -ForegroundColor Cyan
npm run lint
if ($LASTEXITCODE -ne 0) {
    Write-Error "Next.js lint failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "`n Verification passed successfully (Tests + Lint exit 0)." -ForegroundColor Green
exit 0
