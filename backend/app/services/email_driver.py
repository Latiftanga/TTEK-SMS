"""
Email driver abstraction — one class per provider, one shared interface.

Mirrors sms_driver.py's shape exactly: an ABC, one dataclass result type,
and a build_driver() factory keyed by the provider enum.

ADDING A NEW PROVIDER
---------------------
1. Subclass EmailDriver and implement send().
2. Add the new value to EmailProvider enum in models/school.py.
3. Register it in build_driver() below.

FIELD REUSE PER PROVIDER (EmailConfig has one shared shape for all providers)
------------------------------------------------------------------------------
SMTP     — host/port/username/password/use_tls all used as-is.
SendGrid — username = API key; host/port/password/use_tls unused.
Mailgun  — username = API key, host = sending domain (e.g. "mg.example.com");
           port/password/use_tls unused.
Brevo    — username = API key; host/port/password/use_tls unused.

CREDENTIAL STORAGE NOTE
-----------------------
password/username are stored as plaintext in email_config, same caveat as
sms_config — encrypt at the column level or use a secrets manager before
production.

ENDPOINT NOTES (verify against current provider docs before go-live)
---------------------------------------------------------------------
SendGrid — POST https://api.sendgrid.com/v3/mail/send, Bearer API key
Mailgun  — POST https://api.mailgun.net/v3/{domain}/messages, Basic auth ("api", key)
Brevo    — POST https://api.brevo.com/v3/smtp/email, api-key header
"""
from __future__ import annotations

import asyncio
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage

import httpx

from app.models.school import EmailProvider


@dataclass
class EmailResult:
    success: bool
    provider: EmailProvider
    error: str | None = None


class EmailDriver(ABC):
    provider: EmailProvider

    @abstractmethod
    async def send(self, to: str, subject: str, body: str) -> EmailResult: ...


class SmtpDriver(EmailDriver):
    provider = EmailProvider.SMTP

    def __init__(
        self, host: str, port: int | None, username: str, password: str | None,
        use_tls: bool, from_name: str, from_address: str,
    ):
        self._host = host
        self._port = port or (465 if use_tls else 587)
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_name = from_name
        self._from_address = from_address

    def _send_sync(self, to: str, subject: str, body: str) -> None:
        """Runs on a worker thread via asyncio.to_thread — smtplib is blocking."""
        msg = EmailMessage()
        msg["From"] = f"{self._from_name} <{self._from_address}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        # Port 465 = implicit TLS from connect; otherwise plain connect + STARTTLS
        # if requested (port 587 convention). Mirrors Django's EMAIL_USE_SSL vs
        # EMAIL_USE_TLS split, collapsed into the single use_tls flag we store.
        smtp_cls = smtplib.SMTP_SSL if self._port == 465 else smtplib.SMTP
        with smtp_cls(self._host, self._port, timeout=15) as smtp:
            if self._port != 465 and self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password or "")
            smtp.send_message(msg)

    async def send(self, to: str, subject: str, body: str) -> EmailResult:
        try:
            await asyncio.to_thread(self._send_sync, to, subject, body)
            return EmailResult(success=True, provider=self.provider)
        except Exception as exc:
            return EmailResult(success=False, provider=self.provider, error=str(exc))


class SendGridDriver(EmailDriver):
    provider = EmailProvider.SENDGRID
    _URL = "https://api.sendgrid.com/v3/mail/send"

    def __init__(self, api_key: str, from_name: str, from_address: str):
        self._api_key = api_key
        self._from_name = from_name
        self._from_address = from_address

    async def send(self, to: str, subject: str, body: str) -> EmailResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self._URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "personalizations": [{"to": [{"email": to}]}],
                        "from": {"email": self._from_address, "name": self._from_name},
                        "subject": subject,
                        "content": [{"type": "text/plain", "value": body}],
                    },
                )
            resp.raise_for_status()
            return EmailResult(success=True, provider=self.provider)
        except Exception as exc:
            return EmailResult(success=False, provider=self.provider, error=str(exc))


class MailgunDriver(EmailDriver):
    """domain (e.g. "mg.example.com") is stored in EmailConfig.host."""
    provider = EmailProvider.MAILGUN

    def __init__(self, api_key: str, domain: str, from_name: str, from_address: str):
        self._api_key = api_key
        self._domain = domain
        self._from_name = from_name
        self._from_address = from_address

    async def send(self, to: str, subject: str, body: str) -> EmailResult:
        url = f"https://api.mailgun.net/v3/{self._domain}/messages"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    auth=("api", self._api_key),
                    data={
                        "from": f"{self._from_name} <{self._from_address}>",
                        "to": to,
                        "subject": subject,
                        "text": body,
                    },
                )
            resp.raise_for_status()
            return EmailResult(success=True, provider=self.provider)
        except Exception as exc:
            return EmailResult(success=False, provider=self.provider, error=str(exc))


class BrevoDriver(EmailDriver):
    provider = EmailProvider.BREVO
    _URL = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, api_key: str, from_name: str, from_address: str):
        self._api_key = api_key
        self._from_name = from_name
        self._from_address = from_address

    async def send(self, to: str, subject: str, body: str) -> EmailResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self._URL,
                    headers={"api-key": self._api_key, "Content-Type": "application/json"},
                    json={
                        "sender": {"name": self._from_name, "email": self._from_address},
                        "to": [{"email": to}],
                        "subject": subject,
                        "textContent": body,
                    },
                )
            resp.raise_for_status()
            return EmailResult(success=True, provider=self.provider)
        except Exception as exc:
            return EmailResult(success=False, provider=self.provider, error=str(exc))


PROVIDERS_REQUIRING_USERNAME: frozenset[EmailProvider] = frozenset({
    EmailProvider.SENDGRID, EmailProvider.MAILGUN, EmailProvider.BREVO,
})
"""SendGrid/Mailgun/Brevo repurpose `username` as the API key — with it blank
the driver still builds cleanly but every send 401s. Mirrors
sms_driver.py::PROVIDERS_REQUIRING_SECRET, checked at activation time in
services/email_config.py."""


def build_driver(
    provider: EmailProvider,
    host: str | None,
    port: int | None,
    username: str,
    password: str | None,
    use_tls: bool,
    from_name: str,
    from_address: str,
) -> EmailDriver:
    if provider == EmailProvider.SMTP:
        return SmtpDriver(host, port, username, password, use_tls, from_name, from_address)
    if provider == EmailProvider.SENDGRID:
        return SendGridDriver(username, from_name, from_address)
    if provider == EmailProvider.MAILGUN:
        return MailgunDriver(username, host or "", from_name, from_address)
    if provider == EmailProvider.BREVO:
        return BrevoDriver(username, from_name, from_address)
    raise ValueError(f"Unsupported email provider: {provider}")
