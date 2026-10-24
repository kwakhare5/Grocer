---
name: verify-grocer
description: "Verify Grocer WhatsApp Swiggy Instamart concierge behavior end-to-end: start the FastAPI server, run health doctor, exercise WhatsApp webhook & simulator chat, test shopping lists, coupon optimization, address selection, and 1-tap UPI checkout."
---

# Verify Grocer

Project-local verification skill for **Grocer** (WhatsApp Swiggy Instamart concierge).

## 1. Launch

Start the FastAPI application in the background on port 8000 with environment configuration loaded from `.env`.

```powershell
# From repo root (d:\Grocer)
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Readiness Check
Grocer is ready when `http://127.0.0.1:8000/api/ready` returns HTTP 200:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ready" -Method Get
```

Expected response:
```json
{
  "status": "ready",
  "missing": {},
  "checkout_mode": "review"
}
```

---

## 2. Doctor

Run this quick read-only check before driving the app to verify ports, health, and credentials:

```powershell
$resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get
if ($resp.status -ne "alive") {
    Write-Error "Grocer health check failed: $($resp | ConvertTo-Json)"
    exit 1
}
Write-Host "Grocer health check: OK" -ForegroundColor Green
```

---

## 3. Drive

Drive conversational shopping flows via the local Simulator API (`/api/simulator/chat`), which signs and dispatches Meta WhatsApp webhooks internally.

### Driving Headers
```powershell
$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer grocer-local-simulator-token-16chars"
}
```

### Example Drive: Natural Grocery Intake
```powershell
$body = @{
    text = "Need 1 pack toned milk and 1 loaf brown bread"
} | ConvertTo-Json

$reply = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/simulator/chat" -Method Post -Headers $headers -Body $body
Write-Host "Bot Reply:"
Write-Host $reply.text
```

### Example Drive: Fast-Path Button Dispatch
```powershell
$confirmBody = @{
    text = "Confirm Order"
    interactive_id = "confirm_order"
} | ConvertTo-Json

$reply = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/simulator/chat" -Method Post -Headers $headers -Body $confirmBody
Write-Host "Checkout Response:"
Write-Host $reply.text
```

---

## 4. Evidence

Capture evidence as follows:
- Capture the bot's itemized receipt in Indian Rupees (`₹`).
- Verify the receipt lists: items, quantities, prices, delivery fee, taxes, and coupon savings badge.
- Verify `upi://pay` deep link or interactive actions in the response payload.
- All evidence logs save to `.scratch/verify-proof/` (e.g., `01-intake-proof.json`).

---

## 5. Cleanup

Kill the specific uvicorn process running on port 8000:

```powershell
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    Stop-Process -Id $conn.OwningProcess -Force
    Write-Host "Stopped Grocer server process on port 8000." -ForegroundColor Green
}
```

---

## 6. Helpers

Use `.\verify.ps1` from the project root for 1-click test suite and lint verification.
