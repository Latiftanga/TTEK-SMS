from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_auth
from app.schemas.dashboard import DashboardData
from app.services.dashboard import get_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardData)
async def get_my_dashboard(
    ids=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await get_dashboard(user_id, school_id, db)
