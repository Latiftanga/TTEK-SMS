"""
School profile endpoints — GET/PATCH /schools/me, logo upload.
Run inside Docker: docker compose exec api pytest app/tests/test_schools.py -v
"""
import io

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.config import settings
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import GhanaDistrict, GhanaRegion, School, SchoolType
from app.models.students import Student


async def _login_as_head(client: AsyncClient, auth: dict, db_session: AsyncSession, school: School) -> dict:
    """Create a real (non-superadmin) staff login holding HEAD — which grants
    school.edit — to prove the {school_id}-path endpoints reject a normal
    school admin, not just a superadmin. The default `auth` fixture is
    itself a superadmin (see conftest.py::school_admin), so it can't be used
    to test this."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == "HEAD"))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json={
        "staff_number": "TST-HEAD", "first_name": "Test", "last_name": "Head",
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email="head@presec-test.edu.gh",
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    ))
    await db_session.flush()
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": "head@presec-test.edu.gh", "password": "Whatever123!",
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _other_school(db_session: AsyncSession) -> School:
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other = School(
        name="Other School Router Test", school_code="OTHER_SCH_RT", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other)
    await db_session.flush()
    return other


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


# ── {school_id}-path endpoints must reject a normal (non-superadmin) caller ──
# Previously gated by require_auth/require_permission("school","edit"), which
# only checks the CALLER's own permission/school and never that the path id
# matches — a school.edit holder could read/edit/list ANY school by
# substituting a different UUID. Now superadmin-only, matching the existing
# POST /{school_id}/logo convention. The frontend never calls these — only
# /schools/me and friends — so this is a pure lockdown, no behaviour lost.

@pytest.mark.asyncio
async def test_get_school_by_id_rejects_non_superadmin(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    head_auth = await _login_as_head(client, auth, db_session, school)
    other = await _other_school(db_session)
    resp = await client.get(f"/schools/{other.id}", headers=head_auth)
    assert resp.status_code == 403

    own_resp = await client.get(f"/schools/{school.id}", headers=head_auth)
    assert own_resp.status_code == 403, "even the caller's OWN school_id must 403 here — /schools/me is the self-service path"


@pytest.mark.asyncio
async def test_update_school_by_id_rejects_non_superadmin(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    head_auth = await _login_as_head(client, auth, db_session, school)
    other = await _other_school(db_session)
    resp = await client.patch(f"/schools/{other.id}", json={"name": "Hijacked"}, headers=head_auth)
    assert resp.status_code == 403

    await db_session.refresh(other)
    assert other.name == "Other School Router Test"


# ── No multi-tenancy leak on an unrecognized subdomain/custom domain ───────────
# Both endpoints are public/unauthenticated (hit before login) — the raw
# response is visible to anyone who opens their browser's network tab, not
# just what the frontend chooses to render, so the 404 detail itself must
# never confirm a per-tenant lookup exists ("no SCHOOL found" would).

@pytest.mark.asyncio
async def test_public_branding_404_does_not_reveal_school_lookup(client: AsyncClient):
    resp = await client.get("/schools/public/wrong")
    assert resp.status_code == 404
    detail = resp.json()["detail"].lower()
    assert "school" not in detail
    assert "wrong" not in detail


@pytest.mark.asyncio
async def test_by_domain_404_does_not_reveal_school_lookup(client: AsyncClient):
    resp = await client.get("/schools/by-domain", params={"h": "wrong.example.com"})
    assert resp.status_code == 404
    detail = resp.json()["detail"].lower()
    assert "school" not in detail
    assert "wrong.example.com" not in detail


# ── Domain-change lockdown (PATCH /schools/me vs PATCH /schools/{id}) ──────────
# A school's own sign-in link is how every staff/student bookmark, invite
# email, and (for custom_domain) real DNS/TLS record points at them — only
# the platform superadmin may change it, never a school's own admin.

@pytest.mark.asyncio
async def test_update_my_school_rejects_subdomain_change(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    head_auth = await _login_as_head(client, auth, db_session, school)
    original = school.subdomain
    resp = await client.patch("/schools/me", json={"subdomain": "hijacked-slug"}, headers=head_auth)
    assert resp.status_code == 403

    await db_session.refresh(school)
    assert school.subdomain == original


@pytest.mark.asyncio
async def test_update_my_school_rejects_custom_domain_change(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    head_auth = await _login_as_head(client, auth, db_session, school)
    resp = await client.patch("/schools/me", json={"custom_domain": "portal.example.com"}, headers=head_auth)
    assert resp.status_code == 403

    await db_session.refresh(school)
    assert school.custom_domain is None


@pytest.mark.asyncio
async def test_update_my_school_allows_ordinary_fields(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    """The domain lockdown must not block every other self-service field."""
    head_auth = await _login_as_head(client, auth, db_session, school)
    resp = await client.patch("/schools/me", json={"name": "Renamed School"}, headers=head_auth)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed School"


@pytest.mark.asyncio
async def test_update_school_by_id_allows_subdomain_change_for_superadmin(
    client: AsyncClient, auth: dict, school: School,
):
    resp = await client.patch(f"/schools/{school.id}", json={"subdomain": "superadmin-renamed"}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["subdomain"] == "superadmin-renamed"


@pytest.mark.asyncio
async def test_list_schools_rejects_non_superadmin(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    head_auth = await _login_as_head(client, auth, db_session, school)
    resp = await client.get("/schools", headers=head_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_school_config_by_id_rejects_non_superadmin(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    head_auth = await _login_as_head(client, auth, db_session, school)
    other = await _other_school(db_session)
    put_resp = await client.put(
        f"/schools/{other.id}/config", json={"key": "timezone", "value": "hijacked"}, headers=head_auth,
    )
    assert put_resp.status_code == 403
    get_resp = await client.get(f"/schools/{other.id}/config", headers=head_auth)
    assert get_resp.status_code == 403


@pytest.mark.asyncio
async def test_sms_config_by_id_rejects_non_superadmin(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    head_auth = await _login_as_head(client, auth, db_session, school)
    other = await _other_school(db_session)
    resp = await client.put(f"/schools/{other.id}/sms-config", json={
        "provider": "ARKESEL", "api_key": "hijacked-key",
    }, headers=head_auth)
    assert resp.status_code == 403


# ── Auto-generated subdomain on creation ───────────────────────────────────────
# Every school should get a branded <slug>.ttek-sms.com sign-in page by
# default, with zero admin action required — see services/school.py::
# _generate_unique_subdomain. A blank subdomain used to be left null forever.

async def _region_district(db_session: AsyncSession) -> tuple:
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    return region, district


@pytest.mark.asyncio
async def test_create_school_auto_generates_subdomain_when_blank(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    region, district = await _region_district(db_session)
    resp = await client.post("/schools", json={
        "name": "Achimota School", "school_code": "AUTOSLUG01", "school_type": "SHS",
        "region_id": str(region.id), "district_id": str(district.id),
    }, headers=auth)
    assert resp.status_code == 201, resp.text
    assert resp.json()["subdomain"] == "achimota-school"


@pytest.mark.asyncio
async def test_create_school_dedupes_subdomain_on_collision(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    region, district = await _region_district(db_session)
    first = await client.post("/schools", json={
        "name": "Slug Collision School", "school_code": "COLL01", "school_type": "SHS",
        "region_id": str(region.id), "district_id": str(district.id),
    }, headers=auth)
    second = await client.post("/schools", json={
        "name": "Slug Collision School", "school_code": "COLL02", "school_type": "SHS",
        "region_id": str(region.id), "district_id": str(district.id),
    }, headers=auth)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["subdomain"] == "slug-collision-school"
    assert second.json()["subdomain"] == "slug-collision-school-2"


@pytest.mark.asyncio
async def test_create_school_respects_explicit_subdomain(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    region, district = await _region_district(db_session)
    resp = await client.post("/schools", json={
        "name": "Some Long School Name", "school_code": "EXPLICIT01", "school_type": "SHS",
        "region_id": str(region.id), "district_id": str(district.id),
        "subdomain": "custom-slug",
    }, headers=auth)
    assert resp.status_code == 201, resp.text
    assert resp.json()["subdomain"] == "custom-slug"


@pytest.mark.asyncio
async def test_create_school_auto_slug_avoids_reserved_word(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    """A school literally named "API" or "Admin" must not silently claim a
    reserved platform subdomain (frontend/src/lib/stores/subdomain.ts's
    RESERVED set) — it would collide with the platform's own routes."""
    region, district = await _region_district(db_session)
    resp = await client.post("/schools", json={
        "name": "Admin", "school_code": "RESERVED01", "school_type": "SHS",
        "region_id": str(region.id), "district_id": str(district.id),
    }, headers=auth)
    assert resp.status_code == 201, resp.text
    assert resp.json()["subdomain"] != "admin"
    assert resp.json()["subdomain"] == "admin-school"


# ── EMAIL login always requires school_code — no school directory ─────────────
# The "Find my school" search endpoint (and the global-lookup-when-omitted
# behavior in find_user_by_identifier) was removed outright: a searchable
# school directory lets anyone see which schools use the platform, directly
# undermining "this app was built specifically for us." Every school is
# reached only via its own subdomain/custom domain, which resolves
# school_code automatically before the request is ever sent — see
# services/auth.py::superadmin_login for the one legitimate exception
# (platform-admin, a fully separate endpoint) and test_auth.py for the
# full regular-vs-superadmin login coverage.

@pytest.mark.asyncio
async def test_email_login_requires_school_code(
    client: AsyncClient, db_session: AsyncSession, school: School,
):
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email="noschoolcode@presec-test.edu.gh",
        password_hash=hash_password("Whatever123!"), is_active=True,
    ))
    await db_session.flush()
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": "noschoolcode@presec-test.edu.gh", "password": "Whatever123!",
    })
    assert resp.status_code == 422, resp.text


# ── GET /schools — usage stats, search, active_only default ────────────────────

@pytest.mark.asyncio
async def test_list_schools_includes_inactive_by_default(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    school.is_active = False
    await db_session.flush()
    resp = await client.get("/schools", headers=auth)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert str(school.id) in ids


@pytest.mark.asyncio
async def test_list_schools_active_only_excludes_disabled(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    school.is_active = False
    await db_session.flush()
    resp = await client.get("/schools", params={"active_only": True}, headers=auth)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert str(school.id) not in ids


@pytest.mark.asyncio
async def test_list_schools_search_matches_name_and_code(
    client: AsyncClient, auth: dict, school: School,
):
    resp = await client.get("/schools", params={"search": school.school_code}, headers=auth)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert str(school.id) in ids

    resp2 = await client.get("/schools", params={"search": "definitely-does-not-exist-xyz"}, headers=auth)
    assert resp2.json() == []


@pytest.mark.asyncio
async def test_list_schools_reports_usage_stats(
    client: AsyncClient, auth: dict, school: School, student: Student, staff_member,
):
    # The `auth` fixture itself is a school_admin User linked to `school`
    # that just logged in to obtain its token — so last_login_at is
    # expected to be populated, not null, by the time this runs.
    resp = await client.get("/schools", params={"search": school.school_code}, headers=auth)
    row = next(s for s in resp.json() if s["id"] == str(school.id))
    assert row["student_count"] == 1
    assert row["staff_count"] == 1
    assert row["last_login_at"] is not None


# ── DELETE /schools/{id} — narrow cleanup-only delete ───────────────────────────

async def _empty_disabled_school(db_session: AsyncSession) -> School:
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    s = School(
        name="Empty Disabled School", school_code="EMPTY_DISABLED", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=False,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.mark.asyncio
async def test_delete_school_rejects_non_superadmin(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    head_auth = await _login_as_head(client, auth, db_session, school)
    other = await _empty_disabled_school(db_session)
    resp = await client.delete(f"/schools/{other.id}", headers=head_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_school_rejects_active_school(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    s = School(
        name="Still Active School", school_code="STILL_ACTIVE", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(s)
    await db_session.flush()

    resp = await client.delete(f"/schools/{s.id}", headers=auth)
    assert resp.status_code == 422
    assert (await db_session.get(School, s.id)) is not None


@pytest.mark.asyncio
async def test_delete_school_rejects_school_with_students_or_staff(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, staff_member,
):
    school.is_active = False
    await db_session.flush()

    resp = await client.delete(f"/schools/{school.id}", headers=auth)
    assert resp.status_code == 422
    assert "student" in resp.json()["detail"].lower()
    assert (await db_session.get(School, school.id)) is not None


@pytest.mark.asyncio
async def test_delete_school_succeeds_for_empty_disabled_school(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    s = await _empty_disabled_school(db_session)
    resp = await client.delete(f"/schools/{s.id}", headers=auth)
    assert resp.status_code == 204
    assert (await db_session.get(School, s.id)) is None
