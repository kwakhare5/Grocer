import logging
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from backend.integrations.commerce.swiggy_oauth import default_oauth_manager
from backend.integrations.commerce.token_vault import default_token_vault
from backend.config import settings
from backend.integrations.commerce.connect_tickets import default_connect_tickets

logger = logging.getLogger("grocer.api.oauth")
router = APIRouter()

class LoginRequest(BaseModel):
    ticket: str | None = None
    phone_number: str | None = None

@router.post("/auth/swiggy/login")
async def swiggy_login(req: LoginRequest) -> dict[str, str]:
    customer_id = await default_connect_tickets.consume(req.ticket or "")
    if customer_id is None:
        raise HTTPException(status_code=403, detail="Open a fresh connection link from WhatsApp.")
    try:
        authorize_url, state = await default_oauth_manager.initiate_flow(
            customer_id=customer_id,
        )
        return {"authorize_url": authorize_url, "state": state}
    except ValueError as exc:
        logger.info("Swiggy connection request rejected: %s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Request a fresh connection link in WhatsApp.") from exc
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
            await default_token_vault.store_token_durable(
                customer_id=customer_id,
                access_token=access_token,
                expires_in=expires_in,
                token_type=str(token_data.get("token_type", "Bearer")),
                scope=str(token_data.get("scope", "mcp:tools")),
                client_id=token_data.get("client_id"),
            )
            return {"success": True}
        raise ValueError("Missing customer_id or access_token in exchange response")
    except Exception as exc:
        logger.error("Swiggy connection callback failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=400,
            detail="We could not complete your Swiggy connection. Please start again.",
        ) from exc


@router.post("/auth/token/sync")
async def sync_token() -> None:
    """Close the legacy arbitrary-customer token import."""
    raise HTTPException(status_code=410, detail="Connect your own account through WhatsApp OAuth.")


@router.get("/connect")
async def connect_page(
    request: Request,
) -> RedirectResponse:
    """Redirect to the official whitelisted Vercel landing page."""
    target = (settings.CONNECT_BASE_URL or "https://grocerr.vercel.app").rstrip("/") + "/"
    return RedirectResponse(url=target, status_code=307)


@router.get("/auth/callback", response_class=HTMLResponse)
async def swiggy_callback_browser(code: str, state: str) -> HTMLResponse:
    """Direct browser callback handler from Swiggy Instamart OAuth."""
    try:
        token_data = await default_oauth_manager.exchange_code(
            code=code,
            state=state,
        )
        customer_id = token_data.get("customer_id")
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 86400 * 5)

        if customer_id and access_token:
            await default_token_vault.store_token_durable(
                customer_id=customer_id,
                access_token=access_token,
                expires_in=expires_in,
                token_type=str(token_data.get("token_type", "Bearer")),
                scope=str(token_data.get("scope", "mcp:tools")),
                client_id=token_data.get("client_id"),
            )
            logger.info("Successfully connected and saved Swiggy token for %s", customer_id)

            public_number = (settings.WHATSAPP_PUBLIC_NUMBER or "").removeprefix("+")
            whatsapp_link = (
                f'<a href="https://wa.me/{public_number}" style="display: inline-block; background: #25D366; color: white; text-decoration: none; padding: 14px 28px; border-radius: 9999px; font-weight: 600; font-size: 16px;">Open WhatsApp</a>'
                if re.fullmatch(r"91[6-9][0-9]{9}", public_number)
                else "<p>Return to your WhatsApp chat to continue.</p>"
            )

            return HTMLResponse(
                f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Swiggy Instamart Connected</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #0f172a; display: flex; align-items: center; justify-content: center; min-height: 90vh; margin: 0; padding: 16px;">
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 20px; max-width: 380px; width: 100%; padding: 32px 24px; text-align: center; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05);">
        <div style="font-size: 52px; margin-bottom: 16px;">🎉</div>
        <h2 style="margin: 0 0 8px; font-size: 22px; font-weight: 700; color: #0f172a;">Swiggy Connected!</h2>
        <p style="color: #64748b; font-size: 15px; line-height: 1.5; margin: 0 0 28px;">
            Your grocery assistant is now authorized. You can switch back to WhatsApp and continue shopping!
        </p>
        {whatsapp_link}
    </div>
</body>
</html>"""
            )
        raise ValueError("Missing customer_id or access_token in exchange response")
    except Exception as exc:
        logger.error("Browser callback failed: %s", type(exc).__name__)
        return HTMLResponse(
            """<!DOCTYPE html>
<html>
<head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Connection Error</title></head>
<body style="font-family: -apple-system, sans-serif; text-align: center; padding: 40px 16px; background: #fff5f5;">
    <h2 style="color: #e53e3e;">Connection Failed</h2>
    <p style="color: #4a5568;">We could not complete your Swiggy connection.</p>
    <p>Please try reconnecting again from WhatsApp.</p>
</body>
</html>""",
            status_code=400,
        )


