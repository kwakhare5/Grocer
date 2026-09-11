"""Interactive Terminal WhatsApp Simulator for GROCER v2.

Allows testing the exact 4-turn WhatsApp replenishment conversation
without needing ngrok, webhooks, or phone setup.

Usage:
    python backend/scripts/simulate_whatsapp_chat.py
"""
from __future__ import annotations

import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from backend.channels.models import NormalizedIncomingMessage
from backend.channels.whatsapp import WhatsAppChannelAdapter
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.intent.orchestrator import GrocerOrchestrator


async def main() -> None:
    is_mock = "--mock" in sys.argv
    print("=" * 65)
    print("🤖 GROCER v2 — INTERACTIVE WHATSAPP TERMINAL SIMULATOR")
    print("=" * 65)
    print(f"Commerce Mode: {'SIMULATED (MockCommerceAdapter)' if is_mock else 'LIVE SWIGGY MCP'}")
    print("Simulating live WhatsApp chat with Grocer replenishment assistant.")
    print("Type your message and press Enter. Type 'exit' or 'quit' to stop.\n")

    adapter = WhatsAppChannelAdapter(record_only=True)
    commerce_adapter = MockCommerceAdapter() if is_mock else None
    orchestrator = GrocerOrchestrator(commerce_adapter=commerce_adapter)
    sender_id = "919876543210"

    print("👉 Suggested First Message: 'Need 1L milk and brown bread'\n")

    while True:
        try:
            user_input = input("You (WhatsApp) > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Session ended.")
            break

        incoming = NormalizedIncomingMessage(
            channel_type=adapter.channel_type,
            sender_id=sender_id,
            text=user_input,
            message_id=f"sim_msg_{os.urandom(4).hex()}",
        )

        response = await adapter.dispatch(incoming, orchestrator)
        print("\n" + "─" * 45)
        print("🤖 Grocer Bot (WhatsApp Reply):")
        print("─" * 45)
        print(response.text)
        print("─" * 45 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
