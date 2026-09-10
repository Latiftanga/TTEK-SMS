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


@pytest.mark.asyncio
async def test_usage_counter_does_not_carry_over_between_configs(
    db_session: AsyncSession, school: School, redis_permissions: None,
):
    """A school's own config (used up today) and the platform-default config
    it falls back to after that config is removed must NOT share one Redis
    counter — regression for the bug where switching configs mid-day
    inherited the previous config's usage."""
    from app.core.redis import redis_client

    own_cfg = AiConfig(
        school_id=school.id, provider=AiProvider.GROQ, api_key="school-key",
        daily_limit_per_teacher=10, is_active=True,
    )
    db_session.add(own_cfg)
    await db_session.flush()
    user_id = "00000000-0000-0000-0000-000000000001"

    for _ in range(8):
        await ai_config_module.increment_usage(school.id, user_id, own_cfg)

    platform_cfg = AiConfig(
        school_id=None, provider=AiProvider.GEMINI, api_key="platform-key",
        daily_limit_per_teacher=3, is_active=True,
    )
    db_session.add(platform_cfg)
    await db_session.flush()
    try:
        remaining = await ai_config_module.check_daily_limit(school.id, user_id, platform_cfg, db_session)
        assert remaining == 3  # fresh counter for this config, not 3 - 8
    finally:
        await redis_client.delete(f"ai_usage:{school.id}:{user_id}:{own_cfg.id}:{date.today().isoformat()}")
        await redis_client.delete(f"ai_usage:{school.id}:{user_id}:{platform_cfg.id}:{date.today().isoformat()}")


@pytest.mark.asyncio
async def test_redis_unavailable_fails_closed_for_platform_default(
    db_session: AsyncSession, school: School, monkeypatch,
):
    """With Redis unavailable there is no way to enforce the platform-wide
    shared-budget cap, so the platform-default path must fail closed (503),
    not silently allow every fallback-relying school unlimited use of
    Tagnatek's own key."""
    monkeypatch.setattr("app.core.redis.redis_client", None)
    platform_cfg = AiConfig(
        school_id=None, provider=AiProvider.GEMINI, api_key="platform-key",
        daily_limit_per_teacher=5, is_active=True,
    )
    db_session.add(platform_cfg)
    await db_session.flush()

    with pytest.raises(Exception) as exc_info:
        await ai_config_module.check_daily_limit(
            school.id, "00000000-0000-0000-0000-000000000001", platform_cfg, db_session,
        )
    assert getattr(exc_info.value, "status_code", None) == 503


@pytest.mark.asyncio
async def test_redis_unavailable_still_allows_schools_own_key(
    db_session: AsyncSession, school: School, monkeypatch,
):
    """A school's own funded key carries no shared-budget risk, so it should
    stay allow-through (as before) when Redis is briefly unavailable."""
    monkeypatch.setattr("app.core.redis.redis_client", None)
    own_cfg = AiConfig(
        school_id=school.id, provider=AiProvider.GROQ, api_key="school-key",
        daily_limit_per_teacher=7, is_active=True,
    )
    db_session.add(own_cfg)
    await db_session.flush()

    remaining = await ai_config_module.check_daily_limit(
        school.id, "00000000-0000-0000-0000-000000000001", own_cfg, db_session,
    )
    assert remaining == 7


@pytest.mark.asyncio
async def test_two_active_platform_default_rows_rejected_at_db_level(db_session: AsyncSession):
    """uq_ai_config_one_active_per_scope (migration d6e7f8a9b0c1) backstops
    activate_ai_provider()'s non-atomic deactivate-then-activate against a
    genuine concurrent race — two active school_id=NULL rows must collide."""
    from sqlalchemy.exc import IntegrityError

    db_session.add(AiConfig(school_id=None, provider=AiProvider.GEMINI, api_key="k1", is_active=True))
    await db_session.flush()
    db_session.add(AiConfig(school_id=None, provider=AiProvider.GROQ, api_key="k2", is_active=True))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


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
