"""
generate_safe() — the one place every AI call site reaches driver.generate()
through. Prompted by a real live failure: a genuine Gemini key hit both a
deterministic httpx.HTTPStatusError (a deprecated model) and, separately, a
transient httpx.RequestError with an empty message that succeeded on a
plain manual retry — this file locks in the resulting retry-vs-fail-fast
distinction.

Run inside Docker: docker compose exec api pytest app/tests/test_ai_driver.py -v
"""
import httpx
import pytest
from fastapi import HTTPException

from app.services.ai_driver import generate_safe


class _StatusErrorDriver:
    """A real 4xx/5xx response — a bad key, a deprecated model, a rate
    limit. Never retried: it would just fail again identically."""
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt: str, system: str = "") -> str:
        self.calls += 1
        request = httpx.Request("POST", "https://example.invalid")
        response = httpx.Response(404, request=request, text="model not found")
        raise httpx.HTTPStatusError("404 Not Found", request=request, response=response)


class _TransientThenSucceedsDriver:
    """No response was ever received (connection reset, timeout) — this
    class of failure has been observed live to be transient, so it's
    retried once."""
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt: str, system: str = "") -> str:
        self.calls += 1
        if self.calls == 1:
            raise httpx.ConnectError("connection reset")
        return "real reply"


class _AlwaysTransientFailureDriver:
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt: str, system: str = "") -> str:
        self.calls += 1
        raise httpx.ReadTimeout("timed out")


@pytest.mark.asyncio
async def test_status_error_fails_immediately_no_retry():
    driver = _StatusErrorDriver()
    with pytest.raises(HTTPException) as exc_info:
        await generate_safe(driver, "prompt", "system")
    assert exc_info.value.status_code == 502
    assert "HTTPStatusError" in exc_info.value.detail
    assert driver.calls == 1  # never retried


@pytest.mark.asyncio
async def test_transient_request_error_retried_once_and_succeeds():
    driver = _TransientThenSucceedsDriver()
    result = await generate_safe(driver, "prompt", "system")
    assert result == "real reply"
    assert driver.calls == 2


@pytest.mark.asyncio
async def test_transient_request_error_still_fails_after_retry():
    driver = _AlwaysTransientFailureDriver()
    with pytest.raises(HTTPException) as exc_info:
        await generate_safe(driver, "prompt", "system")
    assert exc_info.value.status_code == 502
    assert "ReadTimeout" in exc_info.value.detail
    assert driver.calls == 2  # tried, retried once, then gave up
