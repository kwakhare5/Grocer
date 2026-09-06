"""Web channel adapter for browser and workbench sessions (Phase C)."""
from __future__ import annotations

from backend.channels.base import BaseChannelAdapter
from backend.channels.models import ChannelType, NormalizedOutgoingResponse


class WebChannelAdapter(BaseChannelAdapter):
    """Channel adapter for web browser sessions."""

    def __init__(self) -> None:
        super().__init__(channel_type=ChannelType.WEB)
        self.sent_responses: list[NormalizedOutgoingResponse] = []

    async def send_response(self, response: NormalizedOutgoingResponse) -> bool:
        """For web, responses are returned directly via HTTP response."""
        self.sent_responses.append(response)
        return True
