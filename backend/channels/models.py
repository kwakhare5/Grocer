"""Channel models for normalized message transport across Web and WhatsApp (Phase C)."""
from __future__ import annotations

import time
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    WEB = "web"
    WHATSAPP = "whatsapp"
    TEST = "test"


class InteractiveAction(BaseModel):
    """Normalized representation of an interactive button or list item."""
    action_type: str = "button"  # "button", "list_item", "url_button"
    id: str
    title: str
    description: Optional[str] = None
    url: Optional[str] = None


class NormalizedIncomingMessage(BaseModel):
    """Channel-agnostic incoming message sent to GrocerOrchestrator."""
    sender_id: str = Field(..., description="Unique sender address, e.g. wa:+919876543210 or cust-web")
    channel: ChannelType = ChannelType.WHATSAPP
    text: str = Field(..., description="Message text or user reply")
    message_id: str = Field(..., description="Unique transport message ID for deduplication")
    interactive_type: Optional[str] = None  # "button_reply", "list_reply"
    interactive_id: Optional[str] = None  # payload ID from button/list tap
    timestamp: float = Field(default_factory=time.time)
    raw_payload: Optional[dict[str, Any]] = None


class NormalizedOutgoingResponse(BaseModel):
    """Channel-agnostic outgoing response from GrocerOrchestrator."""
    recipient_id: str
    channel: ChannelType
    text: str
    conversation_state: str
    requires_confirmation: bool = False
    interactive_actions: list[InteractiveAction] = Field(default_factory=list)
    interactive_title: Optional[str] = None
    interactive_button_text: Optional[str] = None
    order_id: Optional[str] = None
    order_total: Optional[float] = None
    payment_bridge_url: Optional[str] = None
    events: list[str] = Field(default_factory=list)
