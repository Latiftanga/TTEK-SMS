"""
Platform-default AI provider — Tagnatek's own shared configuration, superadmin
only. A school with no AiConfig of its own falls back to this row (see
services/ai_config.py::resolve_driver_for_generation) so every school has a
working AI assistant with zero setup; a school's own key, once configured,
always takes priority.

Mirrors routers/ai.py's shape exactly, scoped to school_id=None instead of
the caller's own school (require_permission's tuple), and gated on
require_superadmin instead of a school permission.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_superadmin
from app.models.school import AiConfig, AiProvider
from app.schemas.ai import (
    AiActivateRequest, AiConfigCreate, AiConfigRead,
    AiProviderInfo, AiTestResult, PROVIDER_INFO,
)
from app.services import ai_config as ai_svc

router = APIRouter(prefix="/ai/platform-default", tags=["ai-platform-default"])


@router.get("/providers", response_model=list[AiProviderInfo])
async def list_providers(_ids=Depends(require_superadmin)):
    return PROVIDER_INFO


@router.post("/configs", response_model=AiConfigRead, status_code=201)
async def upsert_platform_config(
    req: AiConfigCreate,
    _ids=Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Save or update Tagnatek's own credentials for a provider, as the
    platform-wide default. Same api_key-never-returned contract as the
    school-facing POST /ai/configs."""
    return await ai_svc.upsert_ai_config(None, req, db)


@router.get("/configs", response_model=list[AiConfigRead])
async def list_platform_configs(
    _ids=Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    return await ai_svc.list_ai_configs(None, db)


@router.post("/configs/activate", response_model=AiConfigRead)
async def activate_platform_config(
    req: AiActivateRequest,
    _ids=Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Set one provider as THE platform default every school without its own
    config falls back to. All other platform-default rows are deactivated."""
    return await ai_svc.activate_ai_provider(None, req.provider, db)


@router.post("/configs/test", response_model=AiTestResult)
async def test_platform_config(
    _ids=Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Verify the active platform-default key actually works."""
    driver = await ai_svc.get_active_driver_for_platform(db)

    from sqlalchemy import select
    cfg = await db.scalar(
        select(AiConfig).where(AiConfig.school_id.is_(None), AiConfig.is_active.is_(True))
    )
    try:
        reply = await driver.test()
        return AiTestResult(provider=cfg.provider, ok=True, message=reply.strip())
    except Exception as exc:
        return AiTestResult(provider=cfg.provider, ok=False, message=str(exc))


@router.delete("/configs/{provider}", status_code=204)
async def delete_platform_config(
    provider: AiProvider,
    _ids=Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    await ai_svc.delete_ai_config(None, provider, db)
