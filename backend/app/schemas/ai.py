"""Pydantic schemas for AI provider configuration."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.school import AiProvider


class AiConfigCreate(BaseModel):
    provider: AiProvider
    api_key: str = Field(..., min_length=1, description="Provider API key — stored, never returned.")
    model: str | None = Field(None, description="Optional model override. Leave blank for provider default.")
    daily_limit_per_teacher: int = Field(10, ge=1, le=200)


class AiConfigRead(BaseModel):
    id: uuid.UUID
    provider: AiProvider
    model: str | None
    daily_limit_per_teacher: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AiActivateRequest(BaseModel):
    provider: AiProvider


class AiTestResult(BaseModel):
    provider: AiProvider
    ok: bool
    message: str


# Provider metadata shown on the frontend setup card
class AiProviderInfo(BaseModel):
    provider: AiProvider
    name: str
    description: str
    free_tier: str | None
    default_model: str
    docs_url: str


PROVIDER_INFO: list[AiProviderInfo] = [
    AiProviderInfo(
        provider=AiProvider.GEMINI,
        name="Google Gemini",
        description="Google's Gemini Flash model. Best value — includes a generous free tier.",
        free_tier="1 500 requests/day free",
        default_model="gemini-2.0-flash",
        docs_url="https://aistudio.google.com/app/apikey",
    ),
    AiProviderInfo(
        provider=AiProvider.GROQ,
        name="Groq",
        description="Ultra-fast inference using Llama 3. Very generous free tier.",
        free_tier="~14 400 requests/day free",
        default_model="llama-3.3-70b-versatile",
        docs_url="https://console.groq.com/keys",
    ),
    AiProviderInfo(
        provider=AiProvider.ANTHROPIC,
        name="Anthropic Claude",
        description="Claude Haiku — Anthropic's fastest, most affordable model.",
        free_tier=None,
        default_model="claude-haiku-4-5-20251001",
        docs_url="https://console.anthropic.com/settings/keys",
    ),
    AiProviderInfo(
        provider=AiProvider.OPENAI,
        name="OpenAI",
        description="GPT-4o Mini — OpenAI's cheapest capable model.",
        free_tier=None,
        default_model="gpt-4o-mini",
        docs_url="https://platform.openai.com/api-keys",
    ),
]
