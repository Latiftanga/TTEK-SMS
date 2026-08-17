"""
SMS driver abstraction — one class per provider, one shared interface.

ADDING A NEW PROVIDER
---------------------
1. Subclass SmsDriver and implement send().
2. Add the new value to SmsProvider enum in models/school.py.
3. Register it in build_driver() below.
4. Document the required api_key / api_secret fields in SmsConfigCreate.

CREDENTIAL STORAGE NOTE
-----------------------
api_key and api_secret are stored as plaintext in sms_config.
Before production, encrypt at the column level or store in a secrets
manager (AWS Secrets Manager, HashiCorp Vault, etc).

ENDPOINT NOTES (verify against current provider docs before go-live)
---------------------------------------------------------------------
AfricasTalking — api_key = AT api key, api_secret = AT username
Hubtel         — api_key = client ID, api_secret = client secret
Arkesel        — api_key = Arkesel API key, api_secret not required
WiGal          — api_key = WiGal API key, api_secret not required
Twilio         — api_key = Account SID, api_secret = Auth Token
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from app.models.school import SmsProvider


@dataclass
class SmsResult:
    success: bool
    provider: SmsProvider
    error: str | None = None


_QUERY_STRING_RE = re.compile(r"(https?://[^\s'\"?]+)\?[^\s'\"]*")


def _scrub_error(exc: Exception) -> str:
    """Strip query strings from any URL embedded in an exception's message
    before it's ever returned or logged. Hubtel/Arkesel send provider
    credentials as GET query params (see their send() below) — an unscrubbed
    httpx.HTTPStatusError's default str() embeds the full request URL,
    which would otherwise leak the live api_key/api_secret straight into
    SmsLog.error_message, a table gated by a much weaker permission
    (school.view) than the credentials themselves. Applied uniformly across
    every driver, not just the two known to leak via query params, as
    defense-in-depth against any future provider doing the same."""
    return _QUERY_STRING_RE.sub(r"\1?<redacted>", str(exc))


def _normalize_phone(phone: str) -> str:
    """Convert a Ghana phone number to E.164 international format (+233...)."""
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("+"):
        return p
    if p.startswith("00"):
        return "+" + p[2:]
    if p.startswith("0") and len(p) == 10:
        return "+233" + p[1:]
    if len(p) == 9:
        return "+233" + p
    return p  # best-effort for non-Ghana numbers


class SmsDriver(ABC):
    provider: SmsProvider

    @abstractmethod
    async def send(self, to: str, message: str) -> SmsResult: ...

    def _normalize(self, phone: str) -> str:
        return _normalize_phone(phone)


class AfricasTalkingDriver(SmsDriver):
    """
    AfricasTalking SMS API.
    api_key    → AT API key (header)
    api_secret → AT username (form field)
    """
    provider = SmsProvider.AFRICAS_TALKING
    _URL = "https://api.africastalking.com/version1/messaging"

    def __init__(self, api_key: str, api_secret: str, sender_id: str):
        self._api_key = api_key
        self._username = api_secret  # AT calls it "username"
        self._sender_id = sender_id

    async def send(self, to: str, message: str) -> SmsResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self._URL,
                    headers={"apiKey": self._api_key, "Accept": "application/json"},
                    data={
                        "username": self._username,
                        "to": self._normalize(to),
                        "message": message,
                        "from": self._sender_id,
                    },
                )
            resp.raise_for_status()
            return SmsResult(success=True, provider=self.provider)
        except Exception as exc:
            return SmsResult(success=False, provider=self.provider, error=_scrub_error(exc))


class HubtelDriver(SmsDriver):
    """
    Hubtel SMS API.
    api_key    → Hubtel client ID
    api_secret → Hubtel client secret
    """
    provider = SmsProvider.HUBTEL
    _URL = "https://smsc.hubtel.com/v1/messages/send"

    def __init__(self, api_key: str, api_secret: str, sender_id: str):
        self._client_id = api_key
        self._client_secret = api_secret
        self._sender_id = sender_id

    async def send(self, to: str, message: str) -> SmsResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self._URL,
                    params={
                        "clientid": self._client_id,
                        "clientsecret": self._client_secret,
                        "from": self._sender_id,
                        "to": self._normalize(to),
                        "content": message,
                    },
                )
            resp.raise_for_status()
            return SmsResult(success=True, provider=self.provider)
        except Exception as exc:
            return SmsResult(success=False, provider=self.provider, error=_scrub_error(exc))


class ArkeselDriver(SmsDriver):
    """
    Arkesel SMS API.
    api_key    → Arkesel API key
    api_secret → not required
    """
    provider = SmsProvider.ARKESEL
    _URL = "https://sms.arkesel.com/sms/api"

    def __init__(self, api_key: str, api_secret: str | None, sender_id: str):
        self._api_key = api_key
        self._sender_id = sender_id

    async def send(self, to: str, message: str) -> SmsResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self._URL,
                    params={
                        "action": "send-sms",
                        "api_key": self._api_key,
                        "to": self._normalize(to),
                        "from": self._sender_id,
                        "sms": message,
                    },
                )
            resp.raise_for_status()
            return SmsResult(success=True, provider=self.provider)
        except Exception as exc:
            return SmsResult(success=False, provider=self.provider, error=_scrub_error(exc))


class WiGalDriver(SmsDriver):
    """
    WiGal SMS API (Ghana).
    api_key    → WiGal API key
    api_secret → not required
    Verify endpoint at https://wigal.com.gh/developers before go-live.
    """
    provider = SmsProvider.WIGAL
    _URL = "https://app.wigal.com.gh/sendsms"

    def __init__(self, api_key: str, api_secret: str | None, sender_id: str):
        self._api_key = api_key
        self._sender_id = sender_id

    async def send(self, to: str, message: str) -> SmsResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self._URL,
                    headers={"Api-Key": self._api_key},
                    json={
                        "from": self._sender_id,
                        "to": self._normalize(to),
                        "sms": message,
                    },
                )
            resp.raise_for_status()
            return SmsResult(success=True, provider=self.provider)
        except Exception as exc:
            return SmsResult(success=False, provider=self.provider, error=_scrub_error(exc))


class TwilioDriver(SmsDriver):
    """
    Twilio SMS API (international fallback).
    api_key    → Twilio Account SID
    api_secret → Twilio Auth Token
    """
    provider = SmsProvider.TWILIO

    def __init__(self, api_key: str, api_secret: str, sender_id: str):
        self._account_sid = api_key
        self._auth_token = api_secret
        self._from_number = sender_id

    async def send(self, to: str, message: str) -> SmsResult:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}/Messages.json"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    auth=(self._account_sid, self._auth_token),
                    data={
                        "From": self._from_number,
                        "To": self._normalize(to),
                        "Body": message,
                    },
                )
            resp.raise_for_status()
            return SmsResult(success=True, provider=self.provider)
        except Exception as exc:
            return SmsResult(success=False, provider=self.provider, error=_scrub_error(exc))


_DRIVER_MAP: dict[SmsProvider, type[SmsDriver]] = {
    SmsProvider.AFRICAS_TALKING: AfricasTalkingDriver,
    SmsProvider.HUBTEL: HubtelDriver,
    SmsProvider.ARKESEL: ArkeselDriver,
    SmsProvider.WIGAL: WiGalDriver,
    SmsProvider.TWILIO: TwilioDriver,
}

# Providers that cannot function without api_secret (see ENDPOINT NOTES above).
# Checked by activate_sms_provider() — a provider missing this can be saved
# (credentials are often gathered in stages) but must not be made active.
PROVIDERS_REQUIRING_SECRET: frozenset[SmsProvider] = frozenset({
    SmsProvider.AFRICAS_TALKING, SmsProvider.HUBTEL, SmsProvider.TWILIO,
})


def build_driver(
    provider: SmsProvider, api_key: str, api_secret: str | None, sender_id: str
) -> SmsDriver:
    cls = _DRIVER_MAP[provider]
    return cls(api_key=api_key, api_secret=api_secret, sender_id=sender_id)
