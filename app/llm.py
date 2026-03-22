from __future__ import annotations

from typing import Any, Optional

from app.config import get_settings


def get_gemini_model() -> str:
    return get_settings().gemini_model


def get_gemini_client():
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("Gemini API key is not configured.")
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


def build_gemini_config(
    *,
    response_mime_type: Optional[str] = None,
    temperature: Optional[float] = None,
    structured: bool = True,
) -> dict[str, Any]:
    settings = get_settings()
    resolved_temperature = temperature
    if resolved_temperature is None:
        resolved_temperature = (
            settings.gemini_structured_temperature
            if structured
            else settings.gemini_chat_temperature
        )

    config: dict[str, Any] = {
        "temperature": resolved_temperature,
    }
    if response_mime_type:
        config["response_mime_type"] = response_mime_type
    return config
