"""WhatsApp media (audio voice notes & grocery list photos) downloader and Gemini multimodal extractor."""
from __future__ import annotations

import base64
import logging
from typing import Optional
import httpx

from backend.config import settings
from backend.agent.gemini import GeminiClient
from backend.channels.whatsapp import META_GRAPH_API_URL

logger = logging.getLogger("grocer.channels.media")


async def download_whatsapp_media(
    media_id: str,
    access_token: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> tuple[Optional[bytes], str]:
    """Fetch media metadata from Meta Graph API and download binary media payload."""
    token = access_token or settings.WHATSAPP_ACCESS_TOKEN
    if not token or not media_id:
        logger.warning("Cannot download media: access_token or media_id is missing.")
        return None, ""

    headers = {"Authorization": f"Bearer {token}"}
    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=25.0)
        should_close = True

    try:
        # Step 1: Query media endpoint to retrieve download URL
        meta_url = f"{META_GRAPH_API_URL}/{media_id}"
        meta_res = await client.get(meta_url, headers=headers)
        if meta_res.status_code != 200:
            logger.error("Meta media lookup failed with status %d: %s", meta_res.status_code, meta_res.text[:200])
            return None, ""

        meta_data = meta_res.json()
        download_url = meta_data.get("url")
        mime_type = meta_data.get("mime_type", "application/octet-stream")

        if not download_url:
            logger.error("Meta media metadata missing download URL: %s", meta_data)
            return None, ""

        # Step 2: Download raw binary bytes
        media_res = await client.get(download_url, headers=headers)
        if media_res.status_code != 200:
            logger.error("Meta media download failed with status %d", media_res.status_code)
            return None, ""

        return media_res.content, mime_type
    except Exception as exc:
        logger.exception("Error downloading WhatsApp media_id=%s: %s", media_id, exc)
        return None, ""
    finally:
        if should_close:
            await client.aclose()


async def extract_groceries_from_media(
    gemini_client: GeminiClient,
    media_bytes: bytes,
    mime_type: str,
    media_type: str,
    caption: str = "",
) -> str:
    """Multimodal extraction of grocery shopping requests from photos or voice notes using Gemini 3.5 Flash."""
    if not media_bytes or not gemini_client:
        return "NO_GROCERIES_FOUND"

    clean_mime = mime_type.split(";")[0].strip()
    encoded = base64.b64encode(media_bytes).decode("utf-8")
    inline_part = {
        "inlineData": {
            "mimeType": clean_mime,
            "data": encoded,
        }
    }

    if media_type == "image":
        prompt_text = (
            "You are Grocer's multimodal vision engine. Inspect this image.\n"
            "If it is a handwritten grocery list, pantry photo, shopping note, receipt, or food items, "
            "extract every grocery item with its quantity and pack size into a clean shopping request.\n"
            "Format the output as a clear request for groceries, e.g.: 'Please add: 2 packets toned milk, 1 loaf brown bread, 500g butter'.\n"
        )
        if caption:
            prompt_text += f"The user also wrote this caption: '{caption}'. Include items or notes from the caption.\n"
        prompt_text += (
            "If the image contains NO groceries, no food, and no shopping list (e.g. random selfie, pet, blurry blank image), "
            "reply with ONLY the exact text: NO_GROCERIES_FOUND."
        )
    else:  # audio / voice note
        prompt_text = (
            "You are Grocer's audio assistant. Listen to this customer voice note.\n"
            "Transcribe all requested grocery items, quantities, and instructions into a clean shopping request, "
            "e.g.: 'Please add: 2 liters Amul milk, 1 brown bread, 6 eggs'.\n"
            "Support English, Hindi, and Hinglish naturally.\n"
            "If the audio is completely silent, unintelligible, or does not mention any groceries or shopping requests, "
            "reply with ONLY the exact text: NO_GROCERIES_FOUND."
        )

    contents = [
        {
            "role": "user",
            "parts": [
                {"text": prompt_text},
                inline_part,
            ],
        }
    ]

    try:
        response_data = await gemini_client.generate_content(
            contents=contents,
            system_text="You extract grocery shopping lists from photos and voice notes into clean natural shopping requests.",
            temperature=0.1,
        )
        if not response_data:
            return "NO_GROCERIES_FOUND"

        candidates = response_data.get("candidates", [])
        if not candidates:
            return "NO_GROCERIES_FOUND"

        parts = candidates[0].get("content", {}).get("parts", [])
        text_result = "".join(p.get("text", "") for p in parts).strip()

        if "NO_GROCERIES_FOUND" in text_result:
            return "NO_GROCERIES_FOUND"
        return text_result or "NO_GROCERIES_FOUND"
    except Exception as exc:
        logger.exception("Gemini media extraction error: %s", exc)
        return "NO_GROCERIES_FOUND"
