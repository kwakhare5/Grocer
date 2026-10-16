# 1-Click Verification Script for GROCER
# Runs invariant domain test suite, optional Docker Postgres E2E suite, and frontend linter.

$ErrorActionPreference = "Stop"

Write-Host "`n=== 1. Running Invariant & Domain Tests ===" -ForegroundColor Cyan
pytest backend/tests/test_invariants.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Invariant tests failed with exit code $LASTEXITCODE"
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
    Write-Error "PostgreSQL container is not reachable on 127.0.0.1:5432. Zero test skips allowed. Run: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16-alpine"
    exit 1
}

Write-Host "`n=== 3. Running Frontend Linter ===" -ForegroundColor Cyan
npm run lint
if ($LASTEXITCODE -ne 0) {
    Write-Error "Next.js lint failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "`n Verification passed successfully (Tests + Lint exit 0)." -ForegroundColor Green
exit 0
