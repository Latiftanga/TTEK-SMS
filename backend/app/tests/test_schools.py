"""
School profile endpoints — GET/PATCH /schools/me, logo upload.
Run inside Docker: docker compose exec api pytest app/tests/test_schools.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.school import School


@pytest.mark.asyncio
async def test_get_my_school_logo_url_is_absolute(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    """SchoolRead.logo_url is a computed field derived from logo_path — the
    Setup page and sidebar both broke because they used to reconstruct their
    own (root-relative, same-origin-assuming) URL from the raw path instead.
    A missing/None logo_path must still degrade to a null logo_url, not an
    empty-string URL."""
    resp_no_logo = await client.get("/schools/me", headers=auth)
    assert resp_no_logo.status_code == 200
    assert resp_no_logo.json()["logo_url"] is None

    school.logo_path = "logos/test-logo.webp"
    await db_session.commit()

    resp = await client.get("/schools/me", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["logo_path"] == "logos/test-logo.webp"
    assert body["logo_url"] == f"{settings.app_base_url.rstrip('/')}/uploads/logos/test-logo.webp"
