"""
SMS integration tests — provider config management and manual send.

Real HTTP calls to providers are NOT made in these tests.  The test strategy:
  - Config CRUD (upsert, list, activate, delete): pure DB operations, no HTTP
  - Manual send with NO active config → 503
  - Manual send with active config → mocked via httpx.MockTransport
  - Phone normalization tested directly via the module function

Run inside Docker: docker compose exec api pytest app/tests/test_sms.py -v
"""
import pytest
import httpx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School, SmsConfig, SmsProvider
from app.services.sms_driver import _normalize_phone


# ── Phone normalization ───────────────────────────────────────────────────────

def test_normalize_local_10_digit():
    assert _normalize_phone("0244123456") == "+233244123456"


def test_normalize_already_international():
    assert _normalize_phone("+233244123456") == "+233244123456"


def test_normalize_nine_digit():
    assert _normalize_phone("244123456") == "+233244123456"


def test_normalize_spaces_stripped():
    assert _normalize_phone("024 412 3456") == "+233244123456"


# ── Config upsert ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_sms_config(client: AsyncClient, auth: dict):
    resp = await client.post("/sms/configs", json={
        "provider": "AFRICAS_TALKING",
        "api_key": "test-api-key",
        "api_secret": "test-username",
        "sender_id": "PRESEC",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "AFRICAS_TALKING"
    assert data["sender_id"] == "PRESEC"
    assert data["is_active"] is False
    # Credentials must NOT appear in the response
    assert "api_key" not in data
    assert "api_secret" not in data


@pytest.mark.asyncio
async def test_upsert_sms_config_ignores_client_supplied_is_active(
    client: AsyncClient, auth: dict,
):
    """is_active isn't a field on SmsConfigCreate — only /sms/configs/activate
    may flip it, so that it always deactivates every other provider first.
    A raw request smuggling is_active:true must not create a second active row."""
    await client.post("/sms/configs", json={
        "provider": "AFRICAS_TALKING", "api_key": "k1",
        "api_secret": "s1", "sender_id": "SCHOOL",
    }, headers=auth)
    await client.post("/sms/configs/activate",
        json={"provider": "AFRICAS_TALKING"}, headers=auth,
    )
    resp = await client.post("/sms/configs", json={
        "provider": "ARKESEL", "api_key": "k2", "sender_id": "SCHOOL",
        "is_active": True,
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["is_active"] is False

    configs = (await client.get("/sms/configs", headers=auth)).json()
    active = [c for c in configs if c["is_active"]]
    assert len(active) == 1
    assert active[0]["provider"] == "AFRICAS_TALKING"


@pytest.mark.asyncio
async def test_upsert_sms_config_updates_existing(client: AsyncClient, auth: dict):
    await client.post("/sms/configs", json={
        "provider": "HUBTEL", "api_key": "key-v1",
        "api_secret": "secret-v1", "sender_id": "OLD",
    }, headers=auth)
    resp = await client.post("/sms/configs", json={
        "provider": "HUBTEL", "api_key": "key-v2",
        "api_secret": "secret-v2", "sender_id": "NEW",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["sender_id"] == "NEW"

    configs = (await client.get("/sms/configs", headers=auth)).json()
    hubtel_rows = [c for c in configs if c["provider"] == "HUBTEL"]
    assert len(hubtel_rows) == 1, "Upsert should not create duplicates"


# ── List configs ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_sms_configs_empty(client: AsyncClient, auth: dict):
    resp = await client.get("/sms/configs", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_sms_configs_shows_all_providers(client: AsyncClient, auth: dict):
    for provider in ["AFRICAS_TALKING", "ARKESEL"]:
        await client.post("/sms/configs", json={
            "provider": provider, "api_key": "k", "sender_id": "SCHOOL",
        }, headers=auth)
    resp = await client.get("/sms/configs", headers=auth)
    assert resp.status_code == 200
    providers = [c["provider"] for c in resp.json()]
    assert "AFRICAS_TALKING" in providers
    assert "ARKESEL" in providers


# ── Activate provider ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_activate_provider_sets_active(client: AsyncClient, auth: dict):
    await client.post("/sms/configs", json={
        "provider": "AFRICAS_TALKING", "api_key": "k", "api_secret": "s", "sender_id": "SCHOOL",
    }, headers=auth)
    resp = await client.post("/sms/configs/activate",
        json={"provider": "AFRICAS_TALKING"}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_activate_deactivates_others(client: AsyncClient, auth: dict):
    await client.post("/sms/configs", json={
        "provider": "AFRICAS_TALKING", "api_key": "k", "api_secret": "s", "sender_id": "SCHOOL",
    }, headers=auth)
    await client.post("/sms/configs", json={
        "provider": "ARKESEL", "api_key": "k", "sender_id": "SCHOOL",
    }, headers=auth)
    await client.post("/sms/configs/activate",
        json={"provider": "AFRICAS_TALKING"}, headers=auth,
    )
    await client.post("/sms/configs/activate",
        json={"provider": "ARKESEL"}, headers=auth,
    )
    configs = (await client.get("/sms/configs", headers=auth)).json()
    active = [c for c in configs if c["is_active"]]
    assert len(active) == 1, "Exactly one provider should be active"
    assert active[0]["provider"] == "ARKESEL"


@pytest.mark.asyncio
async def test_activate_unconfigured_provider_returns_404(client: AsyncClient, auth: dict):
    resp = await client.post("/sms/configs/activate",
        json={"provider": "WIGAL"}, headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_activate_rejects_missing_required_secret(client: AsyncClient, auth: dict):
    """AfricasTalking/Hubtel/Twilio can't function without api_secret — activating
    one that was saved without it must fail loudly, not just log FAILED sends later."""
    await client.post("/sms/configs", json={
        "provider": "AFRICAS_TALKING", "api_key": "k", "sender_id": "SCHOOL",
    }, headers=auth)
    resp = await client.post("/sms/configs/activate",
        json={"provider": "AFRICAS_TALKING"}, headers=auth,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_activate_allows_provider_without_secret_requirement(client: AsyncClient, auth: dict):
    """Arkesel/WiGal genuinely don't need api_secret — must still activate cleanly."""
    await client.post("/sms/configs", json={
        "provider": "ARKESEL", "api_key": "k", "sender_id": "SCHOOL",
    }, headers=auth)
    resp = await client.post("/sms/configs/activate",
        json={"provider": "ARKESEL"}, headers=auth,
    )
    assert resp.status_code == 200


# ── Delete config ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_sms_config(client: AsyncClient, auth: dict):
    await client.post("/sms/configs", json={
        "provider": "TWILIO", "api_key": "SID",
        "api_secret": "TOKEN", "sender_id": "+15550000",
    }, headers=auth)
    resp = await client.delete("/sms/configs/TWILIO", headers=auth)
    assert resp.status_code == 204
    configs = (await client.get("/sms/configs", headers=auth)).json()
    assert not any(c["provider"] == "TWILIO" for c in configs)


@pytest.mark.asyncio
async def test_delete_nonexistent_config_returns_404(client: AsyncClient, auth: dict):
    resp = await client.delete("/sms/configs/HUBTEL", headers=auth)
    assert resp.status_code == 404


# ── Manual send ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_without_active_config_returns_503(client: AsyncClient, auth: dict):
    resp = await client.post("/sms/send", json={
        "phones": ["0244123456"],
        "message": "Test message",
    }, headers=auth)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_send_message_too_long_rejected(client: AsyncClient, auth: dict):
    resp = await client.post("/sms/send", json={
        "phones": ["0244123456"],
        "message": "X" * 161,
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_succeeds_with_active_config(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession, school: School,
):
    """Send via Arkesel with a mocked HTTP transport — verifies log is written."""
    from sqlalchemy import select

    # Set up active Arkesel config
    config = SmsConfig(
        school_id=school.id,
        provider=SmsProvider.ARKESEL,
        api_key="test-arkesel-key",
        sender_id="TESTSCHOOL",
        is_active=True,
    )
    db_session.add(config)
    await db_session.flush()

    # Patch httpx at the client level using httpx mock transport
    original_init = httpx.AsyncClient.__init__

    class _MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, json={"status": "ok"})

    import unittest.mock as mock
    with mock.patch("httpx.AsyncClient.__init__", lambda self, **kw: original_init(
        self, transport=_MockTransport(), **{k: v for k, v in kw.items() if k != "transport"}
    )):
        resp = await client.post("/sms/send", json={
            "phones": ["0244123456"],
            "message": "Test from TTEK-SMS",
        }, headers=auth)

    assert resp.status_code == 200
    data = resp.json()
    assert data["sent"] == 1
    assert data["failed"] == 0

    # Verify log entry written — recipient must be the normalized number actually
    # dialed (+233...), not the raw "0244123456" the admin typed in.
    from app.models.school import SmsLog
    log = await db_session.scalar(
        select(SmsLog).where(SmsLog.school_id == school.id)
    )
    assert log is not None
    assert log.message == "Test from TTEK-SMS"
    assert log.recipient == "+233244123456"


# ── SMS log endpoint ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_sms_logs_empty(client: AsyncClient, auth: dict):
    resp = await client.get("/sms/logs", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


# ── Credential leak / robustness (module review) ────────────────────────────────

def test_scrub_error_strips_query_string():
    from app.services.sms_driver import _scrub_error
    exc = Exception(
        "Client error '401 Unauthorized' for url "
        "'https://smsc.hubtel.com/v1/messages/send?clientid=ID123&clientsecret=SECRET456&from=X'"
    )
    scrubbed = _scrub_error(exc)
    assert "SECRET456" not in scrubbed
    assert "ID123" not in scrubbed
    assert "https://smsc.hubtel.com/v1/messages/send?<redacted>" in scrubbed


@pytest.mark.asyncio
async def test_send_failure_does_not_leak_credentials_in_log(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    """Regression: HubtelDriver/ArkeselDriver send credentials as GET query
    params — an unscrubbed httpx.HTTPStatusError's str() embeds the full
    request URL, so a failed send used to write the live api_key/api_secret
    straight into SmsLog.error_message."""
    from sqlalchemy import select
    from app.models.school import SmsLog

    config = SmsConfig(
        school_id=school.id,
        provider=SmsProvider.ARKESEL,
        api_key="super-secret-arkesel-key",
        sender_id="TESTSCHOOL",
        is_active=True,
    )
    db_session.add(config)
    await db_session.flush()

    original_init = httpx.AsyncClient.__init__

    class _Mock401Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(401, json={"error": "unauthorized"})

    import unittest.mock as mock
    with mock.patch("httpx.AsyncClient.__init__", lambda self, **kw: original_init(
        self, transport=_Mock401Transport(), **{k: v for k, v in kw.items() if k != "transport"}
    )):
        resp = await client.post("/sms/send", json={
            "phones": ["0244123456"], "message": "Test",
        }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["failed"] == 1

    log = await db_session.scalar(select(SmsLog).where(SmsLog.school_id == school.id))
    assert log is not None
    assert log.error_message is not None
    assert "super-secret-arkesel-key" not in log.error_message


@pytest.mark.asyncio
async def test_send_oversized_normalized_phone_does_not_crash(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    """Regression: _normalize_phone() is best-effort passthrough for anything
    that doesn't match a recognized Ghana pattern — a garbage manual-send
    entry could normalize to a string longer than SmsLog.recipient's
    String(20) column, raising an unhandled DataError instead of a clean
    failed result (and, before the per-item savepoint fix, rolling back
    every already-logged send earlier in the same batch)."""
    config = SmsConfig(
        school_id=school.id, provider=SmsProvider.ARKESEL,
        api_key="key", sender_id="TESTSCHOOL", is_active=True,
    )
    db_session.add(config)
    await db_session.flush()

    resp = await client.post("/sms/send", json={
        "phones": ["not-a-real-phone-number-at-all-way-too-long"],
        "message": "Test",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["failed"] == 1


@pytest.mark.asyncio
async def test_upsert_sms_config_oversized_sender_id_rejected(client: AsyncClient, auth: dict):
    resp = await client.post("/sms/configs", json={
        "provider": "ARKESEL", "api_key": "key", "sender_id": "X" * 21,
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_phones_list_capped(client: AsyncClient, auth: dict):
    resp = await client.post("/sms/send", json={
        "phones": ["0244123456"] * 1001, "message": "Test",
    }, headers=auth)
    assert resp.status_code == 422
