"""Swiggy OAuth 2.1 API routes for initiating auth and exchanging tokens."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from backend.integrations.commerce.swiggy_oauth import default_oauth_manager
from backend.integrations.commerce.token_vault import default_token_vault

router = APIRouter(prefix="/api/swiggy", tags=["swiggy-oauth"])


class TokenExchangeRequest(BaseModel):
    code: str
    state: str
    code_verifier: Optional[str] = None
    redirect_uri: Optional[str] = None
    customer_id: Optional[str] = None


class TokenExchangeResponse(BaseModel):
    success: bool
    customer_id: str
    authenticated: bool
    expires_in: int
    scope: str


class AuthStatusResponse(BaseModel):
    customer_id: str
    authenticated: bool
    expires_at: Optional[float] = None


class LogoutRequest(BaseModel):
    customer_id: str


@router.get("/authorize")
async def get_authorization_url(
    customer_id: str = Query(..., description="GROCER customer identifier"),
    redirect_uri: Optional[str] = Query(None, description="Allowlisted redirect URI"),
) -> dict[str, str]:
    """Generate PKCE challenge, state, and Swiggy authorization URL."""
    authorize_url, state = await default_oauth_manager.initiate_flow(
        customer_id=customer_id,
        redirect_uri=redirect_uri,
    )
    return {"authorize_url": authorize_url, "state": state}


@router.post("/token", response_model=TokenExchangeResponse)
async def exchange_token(payload: TokenExchangeRequest) -> TokenExchangeResponse:
    """Exchange authorization code and persist token in secure server vault."""
    try:
        token_data = await default_oauth_manager.exchange_code(
            code=payload.code,
            state=payload.state,
            code_verifier=payload.code_verifier,
            redirect_uri=payload.redirect_uri,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token exchange failed: {exc}",
        )

    customer_id = payload.customer_id or token_data.get("customer_id") or "cust-default"
    access_token = token_data["access_token"]
    expires_in = int(token_data.get("expires_in", 432000))
    token_type = token_data.get("token_type", "Bearer")
    scope = token_data.get("scope", "mcp:tools")
    client_id = token_data.get("client_id")

    default_token_vault.store_token(
        customer_id=customer_id,
        access_token=access_token,
        expires_in=expires_in,
        token_type=token_type,
        scope=scope,
        client_id=client_id,
    )

    return TokenExchangeResponse(
        success=True,
        customer_id=customer_id,
        authenticated=True,
        expires_in=expires_in,
        scope=scope,
    )


@router.get("/status", response_model=AuthStatusResponse)
async def check_auth_status(customer_id: str = Query(...)) -> AuthStatusResponse:
    """Check if customer currently has a valid, non-expired Swiggy session."""
    entry = default_token_vault.get_entry(customer_id)
    if entry and not entry.is_expired:
        return AuthStatusResponse(
            customer_id=customer_id,
            authenticated=True,
            expires_at=entry.expires_at,
        )
    return AuthStatusResponse(customer_id=customer_id, authenticated=False)


@router.post("/logout")
async def logout(payload: LogoutRequest) -> dict[str, bool]:
    """Revoke active Swiggy session and clear server-side credentials."""
    token = default_token_vault.revoke_token(payload.customer_id)
    if token:
        await default_oauth_manager.revoke_session(token)
    return {"success": True, "logged_out": True}
