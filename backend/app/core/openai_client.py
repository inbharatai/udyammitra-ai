"""Thin async OpenAI client wrapper.

When settings.offline_mode is True, no client is created and agents use their
deterministic fallback narratives — the pipeline runs with zero network calls.
"""
from __future__ import annotations

from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings

_client: Optional[AsyncOpenAI] = None


def get_client() -> Optional[AsyncOpenAI]:
    global _client
    if settings.offline_mode:
        return None
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


def model_id() -> str:
    return settings.openai_model