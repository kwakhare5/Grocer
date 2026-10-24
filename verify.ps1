# verify.ps1 — 1-Click Automated Project Verification Runner
# PURPOSE: Executes deterministic sanity checks across tests and build/lint.
# Uses real live Supabase Postgres and real live Swiggy MCP configuration.
# Exit code 0 = Green / Passed. Non-zero = Red / Failed.

$ErrorActionPreference = "Stop"
$StartTime = Get-Date

Write-Host "`n===============================================" -ForegroundColor Cyan
Write-Host "   GROCER PROJECT VERIFICATION SUITE" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# Step 1: Verify Live Supabase Connection
Write-Host "`n[1/3] Checking Live Supabase Postgres connectivity..." -ForegroundColor Yellow
python -c "from dotenv import load_dotenv; load_dotenv(); from backend.config import settings; import asyncio, asyncpg; dsn=settings.DATABASE_URL; clean=dsn.split('?')[0] if dsn else ''; 
async def test():
    if not clean:
        raise RuntimeError('DATABASE_URL is not configured in .env')
    conn = await asyncpg.connect(clean, ssl='require')
    val = await conn.fetchval('SELECT 1')
    await conn.close()
    if val != 1:
        raise RuntimeError('Unexpected DB ping result: ' + str(val))
asyncio.run(test())"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Supabase database connectivity check failed."
    exit $LASTEXITCODE
}
Write-Host "  -> Supabase Postgres: CONNECTED" -ForegroundColor Green

# Step 2: Python Automated Test Suite
Write-Host "`n[2/3] Running Python automated test suite..." -ForegroundColor Yellow
pytest
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python tests failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host "  -> Python tests: PASSED" -ForegroundColor Green

# Step 3: Frontend Linter
Write-Host "`n[3/3] Checking frontend code quality (ESLint)..." -ForegroundColor Yellow
npm run lint
if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend lint failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host "  -> Frontend lint: PASSED" -ForegroundColor Green

$Elapsed = [math]::Round(((Get-Date) - $StartTime).TotalSeconds, 2)
Write-Host "`n===============================================" -ForegroundColor Green
Write-Host "   VERIFICATION PASSED (Completed in ${Elapsed}s)" -ForegroundColor Green
Write-Host "===============================================`n" -ForegroundColor Green

exit 0
