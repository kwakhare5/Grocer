import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.integrations.commerce.swiggy_oauth import default_oauth_manager
from backend.integrations.commerce.token_vault import default_token_vault
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.config import settings
from backend.identity import whatsapp_customer_id

logger = logging.getLogger("grocer.api.oauth")
router = APIRouter()

class LoginRequest(BaseModel):
    phone_number: str

@router.post("/auth/swiggy/login")
async def swiggy_login(req: LoginRequest) -> dict[str, str]:
    try:
        customer_id = whatsapp_customer_id(
            req.phone_number,
            default_whatsapp_adapter.app_secret or settings.WHATSAPP_APP_SECRET,
        )

        authorize_url, state = await default_oauth_manager.initiate_flow(
            customer_id=customer_id,
        )
        return {"authorize_url": authorize_url, "state": state}
    except ValueError as exc:
        logger.info("Swiggy connection request rejected: %s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Enter a valid WhatsApp phone number.") from exc
    except Exception as exc:
        logger.error("Swiggy connection could not start: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="We could not start your Swiggy connection. Please try again.",
        ) from exc

class CallbackRequest(BaseModel):
    code: str
    state: str

@router.post("/auth/swiggy/callback")
async def swiggy_callback(req: CallbackRequest) -> dict[str, bool]:
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
            return {"success": True}
        raise ValueError("Missing customer_id or access_token in exchange response")
    except Exception as exc:
        logger.error("Swiggy connection callback failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=400,
            detail="We could not complete your Swiggy connection. Please start again.",
        ) from exc

