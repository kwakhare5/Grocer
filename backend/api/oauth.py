from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import logging

from backend.integrations.commerce.swiggy_oauth import default_oauth_manager
from backend.integrations.commerce.token_vault import default_token_vault
from backend.channels.whatsapp import WhatsAppChannelAdapter
from backend.config import settings

logger = logging.getLogger("grocer.api.oauth")
router = APIRouter()

class LoginRequest(BaseModel):
    phone_number: str

@router.post("/auth/swiggy/login")
async def swiggy_login(req: LoginRequest):
    adapter = WhatsAppChannelAdapter(
        verify_token=settings.WHATSAPP_VERIFY_TOKEN,
        app_secret=settings.WHATSAPP_APP_SECRET,
        access_token=settings.WHATSAPP_ACCESS_TOKEN,
        phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID,
    )
    try:
        customer_id = adapter.map_sender_to_customer_id(req.phone_number)
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
