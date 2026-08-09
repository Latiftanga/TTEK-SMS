"""
Email integration tests — provider config management, driver dispatch, and
wiring into a real notification trigger.

Mirrors test_sms.py's strategy:
  - Config CRUD (upsert, list, activate, delete): pure DB operations, no HTTP
  - build_driver() dispatch: verified directly, no network
  - SendGrid/Brevo/Mailgun send: mocked via httpx.MockTransport
  - SMTP send: mocked via patching aiosmtplib.send directly (not an httpx call)
  - End-to-end: a real fee payment with an active SendGrid config + a primary
    guardian email on file writes a SENT EmailLog row

Run inside Docker: docker compose exec api pytest app/tests/test_email.py -v
"""
import unittest.mock as mock

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.fees import StudentFeeRecord
from app.models.school import EmailConfig, EmailLog, EmailProvider, School
from app.models.students import Guardian, Student, StudentGuardian
from app.services.email_driver import (
    BrevoDriver, MailgunDriver, SendGridDriver, SmtpDriver, build_driver,
)


# ── build_driver dispatch ─────────────────────────────────────────────────────

def test_build_driver_smtp():
    d = build_driver(EmailProvider.SMTP, "smtp.example.com", 587, "user", "pass", True, "School", "a@b.com")
    assert isinstance(d, SmtpDriver)


def test_build_driver_sendgrid():
    d = build_driver(EmailProvider.SENDGRID, None, None, "api-key", None, True, "School", "a@b.com")
    assert isinstance(d, SendGridDriver)


def test_build_driver_mailgun():
    d = build_driver(EmailProvider.MAILGUN, "mg.example.com", None, "api-key", None, True, "School", "a@b.com")
    assert isinstance(d, MailgunDriver)


def test_build_driver_brevo():
    d = build_driver(EmailProvider.BREVO, None, None, "api-key", None, True, "School", "a@b.com")
    assert isinstance(d, BrevoDriver)


# ── SMTP send (mocked at the smtplib layer, since it runs on a worker thread) ─

@pytest.mark.asyncio
async def test_smtp_driver_send_success():
    driver = SmtpDriver("smtp.example.com", 587, "user", "pass", True, "School", "a@b.com")
    with mock.patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp_cls.return_value.__enter__.return_value = mock.MagicMock()
        result = await driver.send("parent@example.com", "Subject", "Body")
    assert result.success is True


@pytest.mark.asyncio
async def test_smtp_driver_send_failure_returns_error():
    driver = SmtpDriver("smtp.example.com", 587, "user", "pass", True, "School", "a@b.com")
    with mock.patch("smtplib.SMTP", side_effect=Exception("connection refused")):
        result = await driver.send("parent@example.com", "Subject", "Body")
    assert result.success is False
    assert "connection refused" in result.error


# ── Config upsert ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_email_config(client: AsyncClient, auth: dict):
    resp = await client.post("/email/configs", json={
        "provider": "SENDGRID",
        "username": "test-api-key",
        "from_name": "Test School",
        "from_address": "noreply@testschool.edu.gh",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "SENDGRID"
    assert data["from_address"] == "noreply@testschool.edu.gh"
    assert data["is_active"] is False
    # Credentials must NOT appear in the response
    assert "username" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_upsert_smtp_without_host_rejected(client: AsyncClient, auth: dict):
    resp = await client.post("/email/configs", json={
        "provider": "SMTP",
        "username": "user",
        "from_name": "Test School",
        "from_address": "noreply@testschool.edu.gh",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upsert_email_config_updates_existing(client: AsyncClient, auth: dict):
    await client.post("/email/configs", json={
        "provider": "BREVO", "username": "key-v1",
        "from_name": "Old Name", "from_address": "old@testschool.edu.gh",
    }, headers=auth)
    resp = await client.post("/email/configs", json={
        "provider": "BREVO", "username": "key-v2",
        "from_name": "New Name", "from_address": "new@testschool.edu.gh",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["from_name"] == "New Name"

    configs = (await client.get("/email/configs", headers=auth)).json()
    brevo_rows = [c for c in configs if c["provider"] == "BREVO"]
    assert len(brevo_rows) == 1, "Upsert should not create duplicates"


# ── List configs ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_email_configs_empty(client: AsyncClient, auth: dict):
    resp = await client.get("/email/configs", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


# ── Activate provider ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_activate_config_sets_active(client: AsyncClient, auth: dict):
    created = (await client.post("/email/configs", json={
        "provider": "SENDGRID", "username": "k",
        "from_name": "School", "from_address": "a@testschool.edu.gh",
    }, headers=auth)).json()
    resp = await client.post("/email/configs/activate",
        json={"config_id": created["id"]}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_activate_deactivates_others(client: AsyncClient, auth: dict):
    sendgrid = (await client.post("/email/configs", json={
        "provider": "SENDGRID", "username": "k",
        "from_name": "School", "from_address": "a@testschool.edu.gh",
    }, headers=auth)).json()
    brevo = (await client.post("/email/configs", json={
        "provider": "BREVO", "username": "k",
        "from_name": "School", "from_address": "a@testschool.edu.gh",
    }, headers=auth)).json()

    await client.post("/email/configs/activate", json={"config_id": sendgrid["id"]}, headers=auth)
    await client.post("/email/configs/activate", json={"config_id": brevo["id"]}, headers=auth)

    configs = (await client.get("/email/configs", headers=auth)).json()
    active = [c for c in configs if c["is_active"]]
    assert len(active) == 1, "Exactly one provider should be active"
    assert active[0]["provider"] == "BREVO"


@pytest.mark.asyncio
async def test_activate_rejects_missing_required_username(client: AsyncClient, auth: dict):
    """SendGrid/Mailgun/Brevo repurpose `username` as the API key — a config
    saved without one can't send anything. Activating it must fail loudly
    here, not just accumulate silent FAILED rows in /email/logs. Mirrors
    test_sms.py::test_activate_rejects_missing_required_secret."""
    created = (await client.post("/email/configs", json={
        "provider": "SENDGRID", "username": "",
        "from_name": "School", "from_address": "a@testschool.edu.gh",
    }, headers=auth)).json()
    resp = await client.post("/email/configs/activate",
        json={"config_id": created["id"]}, headers=auth,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_activate_rejects_mailgun_missing_host(client: AsyncClient, auth: dict):
    """Mailgun's `host` field doubles as the sending domain — required at
    send time even though the schema only enforces `host` for SMTP at
    create time."""
    created = (await client.post("/email/configs", json={
        "provider": "MAILGUN", "username": "k",
        "from_name": "School", "from_address": "a@testschool.edu.gh",
    }, headers=auth)).json()
    resp = await client.post("/email/configs/activate",
        json={"config_id": created["id"]}, headers=auth,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_activate_allows_smtp_without_username(client: AsyncClient, auth: dict):
    """SMTP genuinely doesn't require auth on some relays — must still
    activate cleanly since PROVIDERS_REQUIRING_USERNAME doesn't include it."""
    created = (await client.post("/email/configs", json={
        "provider": "SMTP", "username": "", "host": "smtp.testschool.edu.gh",
        "from_name": "School", "from_address": "a@testschool.edu.gh",
    }, headers=auth)).json()
    resp = await client.post("/email/configs/activate",
        json={"config_id": created["id"]}, headers=auth,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_activate_unconfigured_id_returns_404(client: AsyncClient, auth: dict):
    resp = await client.post("/email/configs/activate",
        json={"config_id": "00000000-0000-0000-0000-000000000000"}, headers=auth,
    )
    assert resp.status_code == 404


# ── Delete config ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_email_config(client: AsyncClient, auth: dict):
    created = (await client.post("/email/configs", json={
        "provider": "MAILGUN", "username": "k", "host": "mg.testschool.edu.gh",
        "from_name": "School", "from_address": "a@testschool.edu.gh",
    }, headers=auth)).json()
    resp = await client.delete(f"/email/configs/{created['id']}", headers=auth)
    assert resp.status_code == 204
    configs = (await client.get("/email/configs", headers=auth)).json()
    assert not any(c["id"] == created["id"] for c in configs)


@pytest.mark.asyncio
async def test_delete_nonexistent_config_returns_404(client: AsyncClient, auth: dict):
    resp = await client.delete(
        "/email/configs/00000000-0000-0000-0000-000000000000", headers=auth,
    )
    assert resp.status_code == 404


# ── Email log endpoint ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_email_logs_empty(client: AsyncClient, auth: dict):
    resp = await client.get("/email/logs", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


# ── End-to-end: fee payment triggers a real email send + log ────────────────

@pytest.mark.asyncio
async def test_fee_payment_sends_email_to_primary_guardian(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, academic_term: AcademicTerm, fee_record: StudentFeeRecord,
):
    """Regression-style coverage for the gap found in the 2026-07-14 audit:
    email notifications previously didn't exist at all — this proves the
    whole chain (active config → guardian email lookup → send → log) works
    for a real trigger, not just the driver in isolation."""
    guardian = Guardian(
        school_id=school.id, first_name="Kofi", last_name="Boateng",
        phone="0244000001", email="kofi.boateng@example.com",
    )
    db_session.add(guardian)
    await db_session.flush()
    db_session.add(StudentGuardian(
        school_id=school.id, student_id=student.id, guardian_id=guardian.id,
        relation_type="Father", is_primary=True,
    ))
    db_session.add(EmailConfig(
        school_id=school.id, provider=EmailProvider.SENDGRID,
        username="test-sendgrid-key", from_name="Test School",
        from_address="noreply@testschool.edu.gh", is_active=True,
    ))
    await db_session.flush()

    original_init = httpx.AsyncClient.__init__

    class _MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(202, json={})

    with mock.patch("httpx.AsyncClient.__init__", lambda self, **kw: original_init(
        self, transport=_MockTransport(), **{k: v for k, v in kw.items() if k != "transport"}
    )):
        resp = await client.post("/fees/payments", json={
            "fee_record_id": str(fee_record.id),
            "amount_paid": "200.00",
            "payment_method": "CASH",
            "payment_date": "2024-10-01",
        }, headers=auth)

    assert resp.status_code == 201

    log = await db_session.scalar(
        select(EmailLog).where(
            EmailLog.school_id == school.id, EmailLog.entity_type == "FEE_PAYMENT",
        )
    )
    assert log is not None
    assert log.status.value == "SENT"
    assert log.recipient == "kofi.boateng@example.com"
