"""
Platform-default AI provider — a school with no AiConfig of its own falls
back to the single Tagnatek-configured row (school_id IS NULL); a school's
own config, when present, always wins. Also covers the superadmin-only
platform-default router.

Run inside Docker: docker compose exec api pytest app/tests/test_ai_config.py -v
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import AiConfig, AiProvider
from app.models.school import School
from app.services import ai_config as ai_config_module


@pytest.fixture(autouse=True)
async def _clean_platform_config(db_session: AsyncSession):
    """No platform-default row should leak between tests."""
    yield
    rows = list(await db_session.scalars(select(AiConfig).where(AiConfig.school_id.is_(None))))
    for r in rows:
        await db_session.delete(r)
    await db_session.flush()


# ── resolve_driver_for_generation ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_falls_back_to_platform_default_when_school_has_none(
    db_session: AsyncSession, school: School,
):
    db_session.add(AiConfig(
        school_id=None, provider=AiProvider.GEMINI, api_key="platform-key",
        daily_limit_per_teacher=5, is_active=True,
    ))
    await db_session.flush()

    driver, cfg = await ai_config_module.resolve_driver_for_generation(school.id, db_session)
    assert cfg.school_id is None
    assert cfg.provider == AiProvider.GEMINI


@pytest.mark.asyncio
async def test_schools_own_config_wins_over_platform_default(
    db_session: AsyncSession, school: School,
):
    db_session.add(AiConfig(
        school_id=None, provider=AiProvider.GEMINI, api_key="platform-key",
        daily_limit_per_teacher=5, is_active=True,
    ))
    db_session.add(AiConfig(
        school_id=school.id, provider=AiProvider.GROQ, api_key="school-key",
        daily_limit_per_teacher=10, is_active=True,
    ))
    await db_session.flush()

    driver, cfg = await ai_config_module.resolve_driver_for_generation(school.id, db_session)
    assert cfg.school_id == school.id
    assert cfg.provider == AiProvider.GROQ


@pytest.mark.asyncio
async def test_503_when_neither_school_nor_platform_configured(
    db_session: AsyncSession, school: School,
):
    with pytest.raises(Exception) as exc_info:
        await ai_config_module.resolve_driver_for_generation(school.id, db_session)
    assert "503" in str(exc_info.value) or getattr(exc_info.value, "status_code", None) == 503


# ── usage governance ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_platform_wide_cap_independent_of_per_school_limit(
    db_session: AsyncSession, school: School, redis_permissions: None,
):
    """The platform-wide cap only ever applies when the resolved config IS
    the platform default — a school's own BYOK config is never checked
    against it."""
    platform_cfg = AiConfig(
        school_id=None, provider=AiProvider.GEMINI, api_key="platform-key",
        daily_limit_per_teacher=100, is_active=True,  # per-teacher limit high, irrelevant here
    )
    db_session.add(platform_cfg)
    await db_session.flush()

    from app.core.config import settings
    from app.core.redis import redis_client
    platform_key = f"ai_usage:platform:{date.today().isoformat()}"
    await redis_client.set(platform_key, str(settings.platform_ai_daily_limit))
    try:
        with pytest.raises(Exception) as exc_info:
            await ai_config_module.check_daily_limit(school.id, "00000000-0000-0000-0000-000000000000", platform_cfg, db_session)
        assert getattr(exc_info.value, "status_code", None) == 429
    finally:
        await redis_client.delete(platform_key)


@pytest.mark.asyncio
async def test_schools_own_config_unaffected_by_exhausted_platform_cap(
    db_session: AsyncSession, school: School, redis_permissions: None,
):
    school_cfg = AiConfig(
        school_id=school.id, provider=AiProvider.GROQ, api_key="school-key",
        daily_limit_per_teacher=10, is_active=True,
    )
    db_session.add(school_cfg)
    await db_session.flush()

    from app.core.config import settings
    from app.core.redis import redis_client
    platform_key = f"ai_usage:platform:{date.today().isoformat()}"
    await redis_client.set(platform_key, str(settings.platform_ai_daily_limit))  # fully exhausted
    try:
        remaining = await ai_config_module.check_daily_limit(
            school.id, "00000000-0000-0000-0000-000000000000", school_cfg, db_session,
        )
        assert remaining == 10  # unaffected — never checked against the platform key at all
    finally:
        await redis_client.delete(platform_key)


# ── superadmin platform-default router ──────────────────────────────────────

@pytest.mark.asyncio
async def test_platform_default_router_rejects_school_scoped_token(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    from app.tests.test_lesson_plans import _login_as_position
    teacher_auth, _ = await _login_as_position(client, auth, db_session, school, "TEACHER")
    resp = await client.get("/ai/platform-default/configs", headers=teacher_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_platform_default_crud_via_superadmin_router(client: AsyncClient, auth: dict):
    created = await client.post("/ai/platform-default/configs", headers=auth, json={
        "provider": "GEMINI", "api_key": "fake-platform-key", "daily_limit_per_teacher": 20,
    })
    assert created.status_code == 201, created.text
    assert "api_key" not in created.json()

    activated = await client.post(
        "/ai/platform-default/configs/activate", headers=auth, json={"provider": "GEMINI"},
    )
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True

    listed = await client.get("/ai/platform-default/configs", headers=auth)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = await client.delete("/ai/platform-default/configs/GEMINI", headers=auth)
    assert deleted.status_code == 204
