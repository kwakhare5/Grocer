"""
Centralized LLM client for agents.
Handles provider fallback (Groq -> NVIDIA) to ensure high availability
during rate limits.
"""

import logging
from langchain_groq import ChatGroq
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from backend.config import settings

logger = logging.getLogger(__name__)


def get_llm():
    """
    Returns a configured LangChain Chat model.
    Prefers Groq (Llama-3-70b), falls back to NVIDIA if Groq fails.
    """
    primary = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        api_key=settings.GROQ_API_KEY
    )
    fallback = ChatNVIDIA(
        model="meta/llama-3.1-70b-instruct",
        temperature=0.0,
        api_key=settings.NVIDIA_API_KEY
    )
    return primary.with_fallbacks([fallback])
