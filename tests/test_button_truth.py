"""A button tap must never claim an action that did not happen."""

from __future__ import annotations

from backend.channels.button_router import dispatch_button_action


class RecordingWA:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def send_text_message(self, to_wa_id: str, text: str) -> None:
        self.texts.append(text)


async def test_pay_tap_without_database_is_honest() -> None:
    wa = RecordingWA()

    result = await dispatch_button_action(
        "pay:approval-1", "919999999999", pool=None, wa_client=wa
    )

    assert result["status"] == "checkout_unavailable"
    assert wa.texts, "the customer must be told nothing was charged"
    assert "nothing was charged" in wa.texts[-1].lower()


async def test_unknown_button_is_honest() -> None:
    wa = RecordingWA()

    result = await dispatch_button_action(
        "zzz:1", "919999999999", pool=None, wa_client=wa
    )

    assert result["status"] == "unknown_action"
    assert wa.texts, "the customer must be told the button is stale"
    assert "out of date" in wa.texts[-1].lower()
