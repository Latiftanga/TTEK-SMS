"""
Auth flow integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_auth.py -v

TWO SEPARATE LOGIN ENDPOINTS
----------------------------
POST /auth/login              — regular school users (staff/guardian/student).
                                 school_code is required (schema-enforced) —
                                 no unscoped/global lookup exists anywhere in
                                 this path. See services/auth_lookup.py.
POST /auth/superadmin-login    — platform-admin only. Never touches
                                 school_code at all — a fully separate
                                 function/lookup, not a variant of login()
                                 with a flag. See services/auth.py.

The two are deliberately non-interchangeable: a superadmin account cannot
log in via /auth/login (school_id is always None for a superadmin, so no
school_code could ever match it), and a regular user cannot log in via
/auth/superadmin-login (filtered to is_superadmin=True only).
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.config import settings
from app.models.auth import LoginType, User
from app.models.school import School


@pytest_asyncio.fixture
async def active_user(db_session: AsyncSession, school: School) -> User:
    """A normal active staff user with EMAIL login, scoped to `school`."""
    user = User(
        school_id=school.id,
        login_type=LoginType.EMAIL,
        email="teacher@testschool.edu.gh",
        password_hash=hash_password("password123"),
        is_active=True,
        is_superadmin=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession, school: School) -> User:
    """A deactivated user — login must be rejected."""
    user = User(
        school_id=school.id,
        login_type=LoginType.EMAIL,
        email="suspended@testschool.edu.gh",
        password_hash=hash_password("password123"),
        is_active=False,
        is_superadmin=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ── Login ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, active_user: User, school: School):
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_returns_valid_jwt(client: AsyncClient, active_user: User, school: School):
    """The access_token must be a properly signed JWT with the expected claims."""
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    token = resp.json()["access_token"]
    payload = jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
    assert "sub" in payload
    assert "exp" in payload


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, active_user: User, school: School):
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "wrongpassword",
        "school_code": school.school_code,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client: AsyncClient, school: School):
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "nobody@nowhere.com",
        "password": "password123",
        "school_code": school.school_code,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_deactivated_user_rejected(client: AsyncClient, inactive_user: User, school: School):
    """A suspended user must not receive a token even with the correct password."""
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "suspended@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    assert resp.status_code == 403


# ── school_code is mandatory — no directory, no global fallback ────────────────

@pytest.mark.asyncio
async def test_login_missing_school_code_rejected(client: AsyncClient, active_user: User):
    """A request with no school_code at all is invalid at the schema level
    (422, from FastAPI's own validation) — there is no runtime branch that
    falls back to an unscoped lookup for a regular login."""
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_bogus_school_code_404(client: AsyncClient, active_user: User):
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": "NO-SUCH-SCHOOL",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_login_wrong_school_code_rejected(
    client: AsyncClient, active_user: User, db_session: AsyncSession,
):
    """A real, correct identifier + password, but scoped to a DIFFERENT
    (also real) school — must not match. Same 401 as any other wrong
    credential, not a leak that the account exists elsewhere."""
    from sqlalchemy import select
    from app.models.school import GhanaDistrict, GhanaRegion, SchoolType

    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other = School(
        name="Other Auth Test School", school_code="OTHER_AUTH", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other)
    await db_session.flush()

    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": other.school_code,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_rejected_for_deactivated_school(
    client: AsyncClient, active_user: User, school: School, db_session: AsyncSession,
):
    """Deactivating a school (School.is_active=False) must actually block
    sign-in for everyone there, not just hide it from list_schools/branding
    lookups — resolve_school_id() excludes inactive schools, so correct
    credentials + a correct school_code still 404 the same as a nonexistent
    school_code. Regression for the gap found while building the superadmin
    "Deactivate" control."""
    school.is_active = False
    await db_session.flush()

    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_active_session_rejected_after_school_deactivated(
    client: AsyncClient, active_user: User, school: School, db_session: AsyncSession,
):
    """The other half of "deactivating a school is a real, immediate access
    block": test_login_rejected_for_deactivated_school (above) only proves
    NEW logins are blocked. A JWT access token is otherwise self-contained
    and never touches the DB (core/dependencies.py::require_auth used to be
    pure token decode, no DB call at all) — so before this fix, a session
    that was already live when the school got deactivated kept working
    normally for its full remaining lifetime. This proves the exact same
    still-valid token is rejected the moment the school is disabled, with
    no new login and no token expiry needed."""
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    still_active = await client.get("/auth/me", headers=headers)
    assert still_active.status_code == 200

    school.is_active = False
    await db_session.flush()

    resp = await client.get("/auth/me", headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejected_after_school_deactivated(
    client: AsyncClient, active_user: User, school: School, db_session: AsyncSession,
):
    """Mirrors test_active_session_rejected_after_school_deactivated for the
    refresh-token flow — services/auth.py::refresh() is a completely
    separate code path from require_auth (a raw refresh-token request, not
    an access-token Bearer request) and needed its own matching check."""
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    refresh_token = login_resp.json()["refresh_token"]

    school.is_active = False
    await db_session.flush()

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_superadmin_unaffected_by_disabling_their_own_linked_school(
    client: AsyncClient, school_admin: User, school: School, db_session: AsyncSession,
):
    """school_admin (conftest.py) is a superadmin whose token DOES carry a
    real school_id — a shape distinct from the real production superadmin
    (scripts/create_superadmin.py, always school_id=None), but a real one
    nonetheless (and the exact shape that first exposed this as a genuine
    edge case, not just a test-fixture quirk: a superadmin must never be
    locked out of managing a school by that same school's own disabled
    state — including the one they're actively trying to re-enable)."""
    login_resp = await client.post("/auth/superadmin-login", json={
        "identifier": "admin@presec-test.edu.gh", "password": "admin1234",
    })
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    school.is_active = False
    await db_session.flush()

    resp = await client.get("/auth/me", headers=headers)
    assert resp.status_code == 200


# ── Superadmin login — a fully separate endpoint ────────────────────────────────

@pytest.mark.asyncio
async def test_superadmin_login_succeeds(client: AsyncClient, school_admin: User):
    """school_admin (conftest.py) is a superadmin — see its own docstring."""
    resp = await client.post("/auth/superadmin-login", json={
        "identifier": "admin@presec-test.edu.gh",
        "password": "admin1234",
    })
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_superadmin_login_rejects_regular_user(client: AsyncClient, active_user: User):
    """A real, correct-password regular account is not a superadmin — must
    be rejected the same way as any other wrong credential (401), not a
    different error that would reveal the account exists but isn't eligible."""
    resp = await client.post("/auth/superadmin-login", json={
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regular_login_rejects_superadmin(
    client: AsyncClient, school_admin: User, school: School,
):
    """The reverse direction — a superadmin's school_id is always None
    (scripts/create_superadmin.py), so no school_code could ever resolve to
    a match for them via the regular endpoint."""
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "admin@presec-test.edu.gh",
        "password": "admin1234",
        "school_code": school.school_code,
    })
    assert resp.status_code == 401


# ── Token rotation ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_rotates_token(client: AsyncClient, active_user: User, school: School):
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    old_refresh = login_resp.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    assert resp.json()["refresh_token"] != old_refresh


@pytest.mark.asyncio
async def test_refresh_old_token_rejected(client: AsyncClient, active_user: User, school: School):
    """A refresh token must be invalidated after first use (rotation)."""
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    old_refresh = login_resp.json()["refresh_token"]

    await client.post("/auth/refresh", json={"refresh_token": old_refresh})

    resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logout_revokes_refresh(client: AsyncClient, active_user: User, school: School):
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    tokens = login_resp.json()

    resp = await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 204

    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient, active_user: User, school: School):
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    access_token = login_resp.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "teacher@testschool.edu.gh"
    assert data["is_superadmin"] is False


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 403


# ── Change password ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, active_user: User, school: School):
    """After changing the password, old credentials must be rejected."""
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    access_token = login_resp.json()["access_token"]

    resp = await client.post(
        "/auth/change-password",
        json={"current_password": "password123", "new_password": "NewSecure!99"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 204

    # Old password must now be rejected
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, active_user: User, school: School):
    """Providing the wrong current password must be rejected with 400."""
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
        "school_code": school.school_code,
    })
    access_token = login_resp.json()["access_token"]

    resp = await client.post(
        "/auth/change-password",
        json={"current_password": "notmypassword", "new_password": "NewSecure!99"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 400
