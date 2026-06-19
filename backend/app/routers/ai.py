"""
AI router — per-school AI provider configuration.

WORKFLOW FOR SCHOOL ADMINS
--------------------------
1. GET  /ai/providers           — list all supported providers with metadata
2. POST /ai/configs             — save credentials for a provider
3. GET  /ai/configs             — list configured providers (no api_key returned)
4. POST /ai/configs/activate    — set which provider is active
5. POST /ai/configs/test        — verify active provider key works
6. DELETE /ai/configs/{provider}— remove a provider config

Permission map:
  school.manage → configure, activate, delete, test
  school.view   → list configs only
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.school import AiProvider
from app.schemas.ai import (
    AiActivateRequest, AiConfigCreate, AiConfigRead,
    AiProviderInfo, AiTestResult, PROVIDER_INFO,
)
from app.services import ai_config as ai_svc

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/providers", response_model=list[AiProviderInfo])
async def list_providers():
    """Return metadata for every supported AI provider (name, free tier, docs link)."""
    return PROVIDER_INFO


@router.post("/configs", response_model=AiConfigRead, status_code=201)
async def upsert_ai_config(
    req: AiConfigCreate,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """
    Save or update credentials for an AI provider.

    Call this once per provider. The api_key is stored server-side and is
    NEVER returned in any GET response. After saving, call
    POST /ai/configs/activate to make it active.
    """
    _, school_id = ids
    return await ai_svc.upsert_ai_config(school_id, req, db)


@router.get("/configs", response_model=list[AiConfigRead])
async def list_ai_configs(
    ids=Depends(require_permission("school", "view")),
    db: AsyncSession = Depends(get_db),
):
    """List all configured AI providers for this school. API keys are never included."""
    _, school_id = ids
    return await ai_svc.list_ai_configs(school_id, db)


@router.post("/configs/activate", response_model=AiConfigRead)
async def activate_ai_provider(
    req: AiActivateRequest,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """
    Set one provider as the active AI engine for this school.

    All other configured providers are deactivated automatically.
    The provider must already have credentials saved via POST /ai/configs.
    """
    _, school_id = ids
    return await ai_svc.activate_ai_provider(school_id, req.provider, db)


@router.post("/configs/test", response_model=AiTestResult)
async def test_active_provider(
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a trivial prompt to the active provider to verify the API key works.

    Returns ok=true if the provider responds, ok=false with the error message
    if the request fails (wrong key, quota exceeded, network error).
    """
    _, school_id = ids
    try:
        driver = await ai_svc.get_active_driver(school_id, db)
    except HTTPException as exc:
        raise exc

    from app.models.school import AiConfig
    from sqlalchemy import select
    cfg = await db.scalar(
        select(AiConfig).where(
            AiConfig.school_id == school_id,
            AiConfig.is_active.is_(True),
        )
    )

    try:
        reply = await driver.test()
        return AiTestResult(provider=cfg.provider, ok=True, message=reply.strip())
    except Exception as exc:
        return AiTestResult(provider=cfg.provider, ok=False, message=str(exc))


@router.delete("/configs/{provider}", status_code=204)
async def delete_ai_config(
    provider: AiProvider,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Remove a provider's credentials from this school."""
    _, school_id = ids
    await ai_svc.delete_ai_config(school_id, provider, db)
