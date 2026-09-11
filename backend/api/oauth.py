from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import logging

import hashlib
import hmac

from backend.integrations.commerce.swiggy_oauth import default_oauth_manager
from backend.integrations.commerce.token_vault import default_token_vault
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.config import settings

logger = logging.getLogger("grocer.api.oauth")
router = APIRouter()

class LoginRequest(BaseModel):
    phone_number: str

@router.post("/auth/swiggy/login")
async def swiggy_login(req: LoginRequest):
    try:
        secret = (
            default_whatsapp_adapter.app_secret
            or getattr(settings, "WHATSAPP_APP_SECRET", None)
            or "grocer_app_secret_fallback"
        )
        normalized = "".join(c for c in req.phone_number if c.isdigit())
        if not normalized:
            raise ValueError("Invalid phone number: must contain digits.")
        digest = hmac.new(
            secret.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        customer_id = f"cust_wa_{digest[:24]}"

        authorize_url, state = await default_oauth_manager.initiate_flow(
            customer_id=customer_id,
        )
        return {"authorize_url": authorize_url, "state": state}
    except Exception as exc:
        logger.error(f"Login failed: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))

class CallbackRequest(BaseModel):
    code: str
    state: str

@router.post("/auth/swiggy/callback")
async def swiggy_callback(req: CallbackRequest):
    try:
        token_data = await default_oauth_manager.exchange_code(
            code=req.code,
            state=req.state,
        )
        customer_id = token_data.get("customer_id")
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)
        
        if customer_id and access_token:
            default_token_vault.store_token(
                customer_id=customer_id,
                access_token=access_token,
                expires_in=expires_in,
            )
            return {"success": True, "customer_id": customer_id}
        raise ValueError("Missing customer_id or access_token in exchange response")
    except Exception as exc:
        logger.error(f"Callback failed: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/auth/swiggy/status")
async def swiggy_status(phone_number: str | None = None):
    secret = (
        default_whatsapp_adapter.app_secret
        or getattr(settings, "WHATSAPP_APP_SECRET", None)
        or "grocer_app_secret_fallback"
    )
    if phone_number:
        normalized = "".join(c for c in phone_number if c.isdigit())
        digest = hmac.new(
            secret.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        customer_id = f"cust_wa_{digest[:24]}"
        token = default_token_vault.get_token(customer_id)
        return {"customer_id": customer_id, "authenticated": token is not None}
    return {"authenticated_count": len(default_token_vault._tokens)}

