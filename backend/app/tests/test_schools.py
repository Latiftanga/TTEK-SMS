"""
School profile endpoints — GET/PATCH /schools/me, logo upload.
Run inside Docker: docker compose exec api pytest app/tests/test_schools.py -v
"""
import io

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.school import School


def _tiny_png(color: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=color).save(buf, format="PNG")
    return buf.getvalue()


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
    # updated_at is server-generated (onupdate=func.now()) — a bare commit()
    # doesn't refresh it back into this Python object, and touching it
    # unrefreshed from a later synchronous context (SchoolRead's computed
    # field, via model_validate) raises MissingGreenlet. The real write
    # endpoints (update_school/upload_school_logo) now do this refresh
    # themselves; here it's the test bypassing them via a direct mutation
    # that needs it explicitly.
    await db_session.refresh(school)

    resp = await client.get("/schools/me", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["logo_path"] == "logos/test-logo.webp"
    expected_base = f"{settings.app_base_url.rstrip('/')}/uploads/logos/test-logo.webp"
    assert body["logo_url"].startswith(f"{expected_base}?v=")


@pytest.mark.asyncio
async def test_reupload_logo_succeeds_and_keeps_the_same_path(client: AsyncClient, auth: dict):
    """Integration-level guard for the real upload_school_logo() write path,
    exercised twice in a row: catches the MissingGreenlet regression a
    server-generated updated_at field can cause when read synchronously
    right after a bare flush() (see update_school()'s matching comment).
    logo_path itself is expected to stay identical across re-uploads —
    save_logo() always writes to the same "logos/{school_id}.webp" — which
    is exactly why a cache-busting suffix is needed at all; that specific
    behaviour is covered deterministically in test_logo_url_cache_busting
    below rather than here, since two requests in this test's shared
    transaction get an identical onupdate=func.now() value (Postgres
    freezes NOW() for a whole transaction) and can't prove it either way."""
    first = await client.post(
        "/schools/me/logo",
        files={"file": ("logo1.png", _tiny_png("red"), "image/png")},
        headers=auth,
    )
    assert first.status_code == 200
    assert first.json()["logo_url"] is not None

    second = await client.post(
        "/schools/me/logo",
        files={"file": ("logo2.png", _tiny_png("blue"), "image/png")},
        headers=auth,
    )
    assert second.status_code == 200
    assert second.json()["logo_path"] == first.json()["logo_path"]


def test_logo_url_cache_busting():
    """Pure-function coverage of the actual bug: save_logo() always writes
    to the same path, so a re-uploaded logo's logo_path never changes —
    without a query string derived from something that DOES change (here,
    updated_at), _logo_url() would return the exact same string for two
    genuinely different images, giving neither Svelte nor the browser's own
    HTTP cache any reason to re-fetch (the bug actually reported: the first
    upload worked, a second upload to a different image silently kept
    showing the old one, no error, because nothing was actually wrong
    server-side — the URL just never changed)."""
    from datetime import datetime, timedelta, timezone

    from app.schemas.school import _logo_url

    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = t1 + timedelta(seconds=1)

    url_a = _logo_url("logos/school.webp", t1)
    url_b = _logo_url("logos/school.webp", t2)
    url_a_again = _logo_url("logos/school.webp", t1)

    assert url_a != url_b, "a different updated_at must produce a different URL"
    assert url_a == url_a_again, "the same updated_at must produce the same URL (no needless cache-busting)"
    assert _logo_url(None, t1) is None, "no logo_path means no URL, cache-buster or not"
    assert _logo_url("logos/school.webp") == f"{settings.app_base_url.rstrip('/')}/uploads/logos/school.webp", \
        "updated_at is optional — every current caller passes it, but omitting it must still degrade to an unbusted URL"
