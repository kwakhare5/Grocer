"""Transport-neutral primitives used by the live WhatsApp adapter."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from backend.channels.models import ChannelType, NormalizedOutgoingResponse
from backend.config import settings
from backend.identity import whatsapp_customer_id


class BaseChannelAdapter(ABC):
    """Minimal transport boundary; conversation behavior belongs to ShoppingTask."""

    def __init__(self, channel_type: ChannelType) -> None:
        self.channel_type = channel_type

    def map_sender_to_customer_id(self, sender_id: str) -> str:
        """Map a transport sender to its stable, pseudonymous customer identity."""
        cleaned = re.sub(r"[^\w+]", "", sender_id)
        if self.channel_type == ChannelType.WHATSAPP:
            return whatsapp_customer_id(
                sender_id,
                getattr(self, "app_secret", None) or settings.WHATSAPP_APP_SECRET,
            )
        return f"cust_{cleaned}"

    @abstractmethod
    async def send_response(self, response: NormalizedOutgoingResponse) -> bool:
        """Deliver a normalized response to the transport."""
        raise NotImplementedError
