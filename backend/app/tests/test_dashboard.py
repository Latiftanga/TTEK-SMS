"""
Dashboard tests — the composed staff view (Class Teacher / Subject Teacher /
Housemaster, any combination) plus the multi-role signal booleans.

A staff member can be ClassTeacher for more than one class in the same year
(nothing in the schema prevents it — only one class teacher per class, not
one class per class teacher), so my_classes is a list, not a single class.
Same shape for HouseMaster: assign_house_master() never checks whether the
incoming staff member already runs a different house, so my_houses is a list
too. And a staff member can hold any combination of these three roles at
once — the dashboard composes whichever sections apply rather than picking
one "winning" view, which is the whole point of this file.

Run inside Docker: docker compose exec api pytest app/tests/test_dashboard.py -v
"""
from datetime import date, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, AcademicYear, Class, ClassSubject, ClassTeacher, Subject, SubjectTeacher, TimetableSlot
from app.models.assessments import Assessment, AssessmentType
from app.models.attendance import DayOfWeek, DayType, SchoolCalendar, SchoolPeriod
from app.models.auth import LoginType, StaffPosition, User
from app.models.housing import House, HouseGender, HouseMaster
from app.models.school import School
from app.models.staff import StaffMember


async def _teacher_login(
    client: AsyncClient, db_session: AsyncSession, school: School, staff: StaffMember,
) -> dict:
    """A staff member with no StaffPosition/permissions at all falls through
    get_dashboard()'s permission checks straight to staff_view()."""
    email = f"{staff.staff_number.lower()}@presec-test.edu.gh"
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email=email,
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff.id,
    ))
    await db_session.flush()
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": email, "password": "Whatever123!",
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _login_as_housemaster(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
) -> tuple[dict, StaffMember]:
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == "HOUSEMASTER"))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json={
        "staff_number": "TST-HOUSEMASTER", "first_name": "Test", "last_name": "Housemaster",
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    email = "housemaster@presec-test.edu.gh"
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email=email,
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    ))
    await db_session.flush()

    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": email, "password": "Whatever123!",
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    staff = await db_session.get(StaffMember, staff_id)
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff


async def _add_subject_teacher(
    db_session: AsyncSession, school: School, cls: Class, staff: StaffMember,
    academic_year: AcademicYear, *, code: str, name: str,
) -> Subject:
    subject = Subject(school_id=school.id, code=code, name=name, is_active=True)
    db_session.add(subject)
    await db_session.flush()
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=cls.id, subject_id=subject.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    return subject


async def _add_unpublished_assessment(
    db_session: AsyncSession, school: School, cls: Class, subject: Subject, term: AcademicTerm, *, code: str,
) -> Assessment:
    atype = AssessmentType(school_id=school.id, name=code, code=code, weight=100)
    db_session.add(atype)
    await db_session.flush()
    a = Assessment(
        school_id=school.id, class_id=cls.id, subject_id=subject.id,
        assessment_type_id=atype.id, academic_term_id=term.id,
        recorded_date=date.today(), max_score=100, is_published=False,
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_staff_dashboard_nothing_assigned(
    client: AsyncClient, db_session: AsyncSession, school: School,
    staff_member: StaffMember, academic_term: AcademicTerm, redis_permissions: None,
):
    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "staff"
    assert data["my_classes"] == []
    assert data["my_subjects"] == []
    assert data["my_houses"] == []
    assert data["is_class_teacher"] is False
    assert data["is_subject_teacher"] is False
    assert data["is_housemaster"] is False


@pytest.mark.asyncio
async def test_class_teacher_multiple_classes(
    client: AsyncClient, db_session: AsyncSession, school: School, staff_member: StaffMember,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_class: Class,
    redis_permissions: None,
):
    second_class = Class(school_id=school.id, level="SHS", year_group=1, stream="B", is_active=True)
    db_session.add(second_class)
    await db_session.flush()

    for cls in (school_class, second_class):
        db_session.add(ClassTeacher(
            school_id=school.id, class_id=cls.id, staff_member_id=staff_member.id,
            academic_year_id=academic_year.id, is_active=True,
        ))
    await db_session.flush()

    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "staff"
    assert data["is_class_teacher"] is True
    assert len(data["my_classes"]) == 2
    assert {c["id"] for c in data["my_classes"]} == {str(school_class.id), str(second_class.id)}


@pytest.mark.asyncio
async def test_housemaster_no_house(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    hm_auth, _ = await _login_as_housemaster(client, auth, db_session, school)
    resp = await client.get("/dashboard", headers=hm_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "staff"
    assert data["my_houses"] == []
    assert data["is_housemaster"] is False


@pytest.mark.asyncio
async def test_housemaster_multiple_houses_includes_capacity(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, redis_permissions: None,
):
    house_a = House(school_id=school.id, name="Ashanti House", code="ASH", gender=HouseGender.MIXED, capacity=50)
    house_b = House(school_id=school.id, name="Volta House", code="VOL", gender=HouseGender.MIXED, capacity=None)
    db_session.add_all([house_a, house_b])
    await db_session.flush()

    hm_auth, staff = await _login_as_housemaster(client, auth, db_session, school)

    for house in (house_a, house_b):
        db_session.add(HouseMaster(
            school_id=school.id, house_id=house.id, staff_member_id=staff.id,
            academic_year_id=academic_year.id, is_active=True,
        ))
    await db_session.flush()

    resp = await client.get("/dashboard", headers=hm_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "staff"
    assert data["is_housemaster"] is True
    assert len(data["my_houses"]) == 2
    by_id = {h["id"]: h for h in data["my_houses"]}
    assert by_id[str(house_a.id)]["capacity"] == 50
    assert by_id[str(house_b.id)]["capacity"] is None


# ── My Subjects — the subject-only teacher gap ───────────────────────────────
# Previously a caller with SubjectTeacher rows but no ClassTeacher row got a
# functionally blank dashboard (teacher_view() only ever queried
# ClassTeacher). staff_view() now surfaces this directly.

@pytest.mark.asyncio
async def test_subject_only_teacher_gets_my_subjects(
    client: AsyncClient, db_session: AsyncSession, school: School, staff_member: StaffMember,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_class: Class, redis_permissions: None,
):
    subject = await _add_subject_teacher(
        db_session, school, school_class, staff_member, academic_year, code="ECON", name="Economics",
    )
    await _add_unpublished_assessment(db_session, school, school_class, subject, academic_term, code="MID1")

    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "staff"
    assert data["is_subject_teacher"] is True
    assert data["is_class_teacher"] is False
    assert data["my_classes"] == []
    assert len(data["my_subjects"]) == 1
    entry = data["my_subjects"][0]
    assert entry["subject_id"] == str(subject.id)
    assert entry["class_id"] == str(school_class.id)
    assert entry["pending_score_assessments"] == 1


@pytest.mark.asyncio
async def test_class_teacher_subject_taught_elsewhere_not_double_counted(
    client: AsyncClient, db_session: AsyncSession, school: School, staff_member: StaffMember,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_class: Class, redis_permissions: None,
):
    """The caller class-teaches school_class and separately subject-teaches
    a DIFFERENT class — my_subjects should include the other class's subject
    but not one taught inside their own homeroom (already counted in
    my_classes' own pending_score_assessments)."""
    own_subject = await _add_subject_teacher(
        db_session, school, school_class, staff_member, academic_year, code="MATH", name="Mathematics",
    )
    await _add_unpublished_assessment(db_session, school, school_class, own_subject, academic_term, code="MID1")

    other_class = Class(school_id=school.id, level="SHS", year_group=1, stream="C", is_active=True)
    db_session.add(other_class)
    await db_session.flush()
    other_subject = await _add_subject_teacher(
        db_session, school, other_class, staff_member, academic_year, code="FREN", name="French",
    )
    await _add_unpublished_assessment(db_session, school, other_class, other_subject, academic_term, code="MID2")

    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_member.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_class_teacher"] is True
    assert data["is_subject_teacher"] is True
    assert len(data["my_classes"]) == 1
    assert data["pending_score_assessments"] == 1  # own homeroom's Math assessment
    assert len(data["my_subjects"]) == 1  # only the OTHER class's French, not own-homeroom Math
    assert data["my_subjects"][0]["subject_id"] == str(other_subject.id)
    assert data["my_subjects"][0]["pending_score_assessments"] == 1


# ── Multi-role: independent signals, no seniority pick ───────────────────────
# A staff member can hold any combination of Class Teacher/Subject Teacher/
# Housemaster at once — the composed staff view surfaces all of them
# directly (no badge strip needed for this tier).

@pytest.mark.asyncio
async def test_multi_role_staff_gets_all_sections_at_once(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_class: Class, redis_permissions: None,
):
    house = House(school_id=school.id, name="Eastern House", code="EAS", gender=HouseGender.MIXED)
    db_session.add(house)
    await db_session.flush()

    hm_auth, staff = await _login_as_housemaster(client, auth, db_session, school)

    db_session.add(HouseMaster(
        school_id=school.id, house_id=house.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    other_class = Class(school_id=school.id, level="SHS", year_group=1, stream="D", is_active=True)
    db_session.add(other_class)
    await db_session.flush()
    await _add_subject_teacher(
        db_session, school, other_class, staff, academic_year, code="ICT", name="ICT",
    )

    resp = await client.get("/dashboard", headers=hm_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "staff"
    assert data["is_class_teacher"] is True
    assert data["is_subject_teacher"] is True
    assert data["is_housemaster"] is True
    assert len(data["my_classes"]) == 1
    assert len(data["my_subjects"]) == 1
    assert len(data["my_houses"]) == 1
    # This tier already shows everything directly — no redundant badge strip.
    assert data["other_roles"] == []


@pytest.mark.asyncio
async def test_plain_class_teacher_has_no_other_roles(
    client: AsyncClient, db_session: AsyncSession, school: School,
    staff_member: StaffMember, academic_year: AcademicYear, academic_term: AcademicTerm,
    school_class: Class, redis_permissions: None,
):
    """The common case (one responsibility, no housing/finance/approval
    role) must not show a pointless empty 'you also...' strip."""
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_member.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "staff"
    assert data["is_class_teacher"] is True
    assert data["other_roles"] == []


# ── Tomorrow's schedule — "what do I teach tomorrow?" ────────────────────────

async def _make_tomorrow_slot(
    db_session: AsyncSession, school: School, cls: Class, subject: Subject,
    year: AcademicYear, staff: StaffMember,
) -> None:
    tomorrow = date.today() + timedelta(days=1)
    day_of_week = list(DayOfWeek)[tomorrow.weekday()]
    period = SchoolPeriod(
        school_id=school.id, name="Period 1", day_of_week=day_of_week,
        period_number=1, start_time=time(10, 0), end_time=time(10, 45),
    )
    db_session.add(period)
    await db_session.flush()
    db_session.add(TimetableSlot(
        school_id=school.id, class_id=cls.id, subject_id=subject.id,
        academic_year_id=year.id, period_id=period.id,
    ))
    await db_session.flush()


@pytest.mark.asyncio
async def test_tomorrow_schedule_shows_real_lesson(
    client: AsyncClient, db_session: AsyncSession, school: School, staff_member: StaffMember,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_class: Class, redis_permissions: None,
):
    subject = await _add_subject_teacher(
        db_session, school, school_class, staff_member, academic_year, code="COMP", name="Computing",
    )
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subject.id, is_active=True))
    await db_session.flush()
    await _make_tomorrow_slot(db_session, school, school_class, subject, academic_year, staff_member)

    tomorrow = date.today() + timedelta(days=1)
    db_session.add(SchoolCalendar(
        school_id=school.id, date=tomorrow, day_type=DayType.SCHOOL_DAY, academic_term_id=academic_term.id,
    ))
    await db_session.flush()

    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tomorrow_is_school_day"] is True
    assert len(data["tomorrow_schedule"]) == 1
    assert data["tomorrow_schedule"][0]["subject_id"] == str(subject.id)
    assert data["tomorrow_schedule"][0]["class_id"] == str(school_class.id)


@pytest.mark.asyncio
async def test_tomorrow_schedule_empty_on_holiday(
    client: AsyncClient, db_session: AsyncSession, school: School, staff_member: StaffMember,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_class: Class, redis_permissions: None,
):
    subject = await _add_subject_teacher(
        db_session, school, school_class, staff_member, academic_year, code="ART", name="Art",
    )
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subject.id, is_active=True))
    await db_session.flush()
    await _make_tomorrow_slot(db_session, school, school_class, subject, academic_year, staff_member)

    tomorrow = date.today() + timedelta(days=1)
    db_session.add(SchoolCalendar(
        school_id=school.id, date=tomorrow, day_type=DayType.PUBLIC_HOLIDAY, academic_term_id=academic_term.id,
    ))
    await db_session.flush()

    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tomorrow_is_school_day"] is False
    assert data["tomorrow_schedule"] == []
