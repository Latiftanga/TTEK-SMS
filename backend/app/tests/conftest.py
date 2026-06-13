"""
Shared test fixtures.

Tests run inside the Docker container against the real PostgreSQL database
(alembic upgrade head has already created all tables).

Run with:  docker compose exec api pytest -v

NullPool is used so asyncpg connections are never cached between tests —
this prevents "Future attached to a different loop" errors when pytest-asyncio
creates a new event loop per test function.
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from datetime import date

from app.core.auth import hash_password
from app.core.config import settings
from app.core.database import get_db
from app.main import app
# All models must be imported so SQLAlchemy resolves FK references across files
from app.models import school, auth, staff, academic, students, housing, attendance, assessments, fees, documents  # noqa: F401
from app.models.academic import AcademicTerm, AcademicYear, Class
from app.models.attendance import DayType, SchoolCalendar
from app.models.school import SmsConfig, SmsProvider
from app.models.auth import LoginType, User
from app.models.fees import FeeStructure, FeeType, StudentFeeRecord
from app.models.school import GhanaDistrict, GhanaRegion, School, SchoolType
from app.models.staff import StaffMember
from app.models.students import Student


@pytest_asyncio.fixture
async def db_session():
    """
    Yields a session backed by a fresh NullPool engine per test.
    Wraps all writes in a rolled-back transaction so tests leave no data behind.
    """
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """HTTPX async client wired to the test DB session."""
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def school(db_session: AsyncSession) -> School:
    """A school record, scoped to whatever region/district exists in the seeded DB."""
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    s = School(
        name="Presec Test School",
        school_code="PRESEC_TEST",
        school_type=SchoolType.SHS,
        region_id=region.id,
        district_id=district.id,
        brand_color="#1e40af",
        is_active=True,
        has_boarding=True,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest_asyncio.fixture
async def school_admin(db_session: AsyncSession, school: School) -> User:
    """Superadmin user linked to the test school — bypasses all permission checks."""
    user = User(
        login_type=LoginType.EMAIL,
        email="admin@presec-test.edu.gh",
        password_hash=hash_password("admin1234"),
        is_active=True,
        is_superadmin=True,
        school_id=school.id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def academic_year(db_session: AsyncSession, school: School) -> AcademicYear:
    year = AcademicYear(
        school_id=school.id, name="2024/2025",
        start_date=date(2024, 9, 1), end_date=date(2025, 7, 31), is_current=True,
    )
    db_session.add(year)
    await db_session.flush()
    return year


@pytest_asyncio.fixture
async def academic_term(db_session: AsyncSession, school: School, academic_year: AcademicYear) -> AcademicTerm:
    term = AcademicTerm(
        school_id=school.id, academic_year_id=academic_year.id,
        term_number=1, name="Term 1",
        start_date=date(2024, 9, 1), end_date=date(2024, 12, 20), is_current=True,
    )
    db_session.add(term)
    await db_session.flush()
    return term


@pytest_asyncio.fixture
async def school_class(db_session: AsyncSession, school: School, academic_year: AcademicYear) -> Class:
    cls = Class(
        school_id=school.id, academic_year_id=academic_year.id,
        level="SHS", year_group=2, stream="A", is_active=True,
    )
    db_session.add(cls)
    await db_session.flush()
    return cls


@pytest_asyncio.fixture
async def staff_member(db_session: AsyncSession, school: School) -> StaffMember:
    member = StaffMember(
        school_id=school.id,
        staff_number="HMS001",
        first_name="House",
        last_name="Master",
        is_active=True,
    )
    db_session.add(member)
    await db_session.flush()
    return member


@pytest_asyncio.fixture
async def school_calendar(
    db_session: AsyncSession, school: School, academic_term: AcademicTerm
) -> SchoolCalendar:
    cal = SchoolCalendar(
        school_id=school.id,
        date=date(2024, 9, 2),
        day_type=DayType.SCHOOL_DAY,
        academic_term_id=academic_term.id,
    )
    db_session.add(cal)
    await db_session.flush()
    return cal


@pytest_asyncio.fixture
async def student(db_session: AsyncSession, school: School) -> Student:
    s = Student(
        school_id=school.id,
        admission_number="STU001",
        first_name="Kwame",
        last_name="Asante",
        is_active=True,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest_asyncio.fixture
async def fee_type(db_session: AsyncSession, school: School) -> FeeType:
    ft = FeeType(
        school_id=school.id,
        name="Tuition",
        code="TUITION",
        is_recurring=True,
        is_active=True,
    )
    db_session.add(ft)
    await db_session.flush()
    return ft


@pytest_asyncio.fixture
async def fee_structure(
    db_session: AsyncSession, school: School, academic_term: AcademicTerm, fee_type: FeeType
) -> FeeStructure:
    fs = FeeStructure(
        school_id=school.id,
        academic_term_id=academic_term.id,
        fee_type_id=fee_type.id,
        amount=500,
        is_mandatory=True,
    )
    db_session.add(fs)
    await db_session.flush()
    return fs


@pytest_asyncio.fixture
async def fee_record(
    db_session: AsyncSession, school: School, student: Student,
    academic_term: AcademicTerm, fee_structure: FeeStructure,
) -> StudentFeeRecord:
    rec = StudentFeeRecord(
        school_id=school.id,
        student_id=student.id,
        academic_term_id=academic_term.id,
        fee_structure_id=fee_structure.id,
        amount_due=500,
        is_waived=False,
    )
    db_session.add(rec)
    await db_session.flush()
    return rec


@pytest_asyncio.fixture
async def auth(client: AsyncClient, school_admin: User) -> dict:
    """Bearer token headers for the school admin."""
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "admin@presec-test.edu.gh",
        "password": "admin1234",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
