"""
AI provider drivers for lesson note generation.

Each school configures one AI provider. The school admin provides the API key;
teachers never see or pay for it directly.

DEFAULT MODELS (used when AiConfig.model is NULL):
  GEMINI     → gemini-2.0-flash          (free tier: 1 500 req/day)
  GROQ       → llama-3.3-70b-versatile   (free tier: fast, generous quota)
  ANTHROPIC  → claude-haiku-4-5-20251001 (cheapest Anthropic model, ~$0.001/note)
  OPENAI     → gpt-4o-mini               (cheapest OpenAI model)

All drivers implement:
  generate(prompt, system="") → str    (single-turn, full response)
  test()                       → str   (sends "Reply OK" to verify the key works)
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

import httpx

from app.models.school import AiProvider

T = TypeVar("T", bound=BaseModel)


class AiDriver(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system: str = "") -> str: ...

    async def test(self) -> str:
        return await self.generate("Reply with the single word OK and nothing else.")


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    """Models routinely wrap JSON in a markdown code fence despite being
    told not to — strip it before parsing rather than failing on it."""
    m = _JSON_FENCE_RE.search(text)
    return m.group(1) if m else text.strip()


async def generate_json(driver: AiDriver, prompt: str, system: str, schema: type[T]) -> T:
    """Structured-output helper layered on top of the existing single-turn
    generate() — none of the four drivers below have native JSON-mode/
    function-calling, so this is prompt-engineering + parse/validate, not a
    provider API change. Retries once (a fresh, more forceful instruction) on
    a parse/validation failure before raising a clean 502 the caller can
    surface to the teacher rather than a raw exception."""
    json_instruction = (
        f"{system}\n\nRespond with ONLY valid JSON matching this exact shape "
        f"(no markdown, no commentary, no code fence):\n{schema.model_json_schema()}"
    )
    last_error: Exception | None = None
    for attempt in range(2):
        raw = await driver.generate(prompt, json_instruction)
        try:
            return schema.model_validate(json.loads(_extract_json(raw)))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            json_instruction += (
                "\n\nYour previous response could not be parsed as valid JSON "
                "matching the shape above. Respond again with ONLY the JSON object."
            )
    raise HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        f"The AI response could not be parsed into the expected format: {last_error}",
    )


# ── Gemini ────────────────────────────────────────────────────────────────────

class GeminiDriver(AiDriver):
    _BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str, model: str | None) -> None:
        self._key  = api_key
        self._model = model or "gemini-2.0-flash"

    async def generate(self, prompt: str, system: str = "") -> str:
        parts = []
        if system:
            parts.append({"text": system + "\n\n"})
        parts.append({"text": prompt})
        payload = {"contents": [{"parts": parts}]}
        url = f"{self._BASE}/{self._model}:generateContent?key={self._key}"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


# ── Groq ──────────────────────────────────────────────────────────────────────

class GroqDriver(AiDriver):
    _URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str | None) -> None:
        self._key   = api_key
        self._model = model or "llama-3.3-70b-versatile"

    async def generate(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self._model, "messages": messages}
        headers = {"Authorization": f"Bearer {self._key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self._URL, json=payload, headers=headers)
            resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ── Anthropic ─────────────────────────────────────────────────────────────────

class AnthropicDriver(AiDriver):
    _URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str | None) -> None:
        self._key   = api_key
        self._model = model or "claude-haiku-4-5-20251001"

    async def generate(self, prompt: str, system: str = "") -> str:
        payload: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": self._key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self._URL, json=payload, headers=headers)
            resp.raise_for_status()
        return resp.json()["content"][0]["text"]


# ── OpenAI ────────────────────────────────────────────────────────────────────

class OpenAIDriver(AiDriver):
    _URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str | None) -> None:
        self._key   = api_key
        self._model = model or "gpt-4o-mini"

    async def generate(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self._model, "messages": messages}
        headers = {"Authorization": f"Bearer {self._key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self._URL, json=payload, headers=headers)
            resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ── Factory ───────────────────────────────────────────────────────────────────

def build_ai_driver(provider: AiProvider, api_key: str, model: str | None) -> AiDriver:
    match provider:
        case AiProvider.GEMINI:    return GeminiDriver(api_key, model)
        case AiProvider.GROQ:      return GroqDriver(api_key, model)
        case AiProvider.ANTHROPIC: return AnthropicDriver(api_key, model)
        case AiProvider.OPENAI:    return OpenAIDriver(api_key, model)
    raise ValueError(f"Unknown AI provider: {provider}")
