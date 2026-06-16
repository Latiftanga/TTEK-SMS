"""
Seed two generic demo schools for browser testing.

Run inside Docker:
    docker compose exec api python scripts/seed_demo_school.py

Creates:
  Basic School  (subdomain: basic)
    admin@basic.school / Demo1234!
    teacher@basic.school / Demo1234!
    finance@basic.school / Demo1234!

  Senior High School  (subdomain: shs)
    admin@shs.school / Demo1234!
    teacher@shs.school / Demo1234!
    finance@shs.school / Demo1234!

Visit http://localhost:5173 and enter school code: basic  OR  shs
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.auth import hash_password
from app.models import school as school_models, auth as auth_models, staff as staff_models  # noqa: F401
from app.models import academic, students, housing, attendance, assessments, fees, documents  # noqa: F401
from app.models.school import School, SchoolType, GhanaRegion, GhanaDistrict
from app.models.auth import User, LoginType, StaffPosition, PositionPermission
from app.models.staff import StaffMember

DEMO_PASSWORD = "Demo1234!"

DEMO_SCHOOLS = [
    {
        "subdomain": "basic",
        "school_code": "BASIC-DEMO",
        "name": "GES Basic School",
        "short_name": "Basic School",
        "school_type": "BASIC",
        "brand_color": "#15803d",  # green
        "motto": "Learning for Life",
        "email_domain": "basic.school",
    },
    {
        "subdomain": "shs",
        "school_code": "SHS-DEMO",
        "name": "GES Senior High School",
        "short_name": "Senior High School",
        "school_type": "SHS",
        "brand_color": "#1e40af",  # blue
        "motto": "Excellence in Education",
        "email_domain": "shs.school",
    },
]


async def get_or_create_position(db, school_id, name: str, perms: list[str]) -> StaffPosition:
    existing = await db.scalar(
        select(StaffPosition).where(
            StaffPosition.school_id == school_id,
            StaffPosition.name == name,
        )
    )
    if not existing:
        code = name.upper().replace(" ", "_")[:50]
        existing = StaffPosition(school_id=school_id, name=name, code=code, is_template=False)
        db.add(existing)
        await db.flush()

    # Sync permissions — add any that are missing (idempotent on re-runs).
    existing_perms = {
        (p.module, p.action)
        for p in await db.scalars(
            select(PositionPermission).where(PositionPermission.position_id == existing.id)
        )
    }
    for perm_str in perms:
        module, action = perm_str.split(".")
        if (module, action) not in existing_perms:
            db.add(PositionPermission(
                position_id=existing.id,
                module=module,
                action=action,
                is_allowed=True,
            ))
    return existing


async def create_staff_user(db, school_id, first: str, last: str, email: str, position) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing:
        print(f"  User already exists: {email}")
        return existing

    member = StaffMember(
        school_id=school_id,
        staff_number=f"STAFF-{first[:3].upper()}",
        first_name=first,
        last_name=last,
        email=email,
        is_active=True,
        position_id=position.id,
    )
    db.add(member)
    await db.flush()

    user = User(
        school_id=school_id,
        login_type=LoginType.EMAIL,
        email=email,
        password_hash=hash_password(DEMO_PASSWORD),
        is_active=True,
        staff_member_id=member.id,
    )
    db.add(user)
    return user


async def seed_school(db, cfg: dict, region_id, district_id):
    subdomain = cfg["subdomain"]
    domain = cfg["email_domain"]

    school = await db.scalar(select(School).where(School.subdomain == subdomain))
    if not school:
        school = School(
            name=cfg["name"],
            short_name=cfg["short_name"],
            school_code=cfg["school_code"],
            school_type=SchoolType[cfg["school_type"]],
            region_id=region_id,
            district_id=district_id,
            subdomain=subdomain,
            brand_color=cfg["brand_color"],
            motto=cfg["motto"],
            is_active=True,
        )
        db.add(school)
        await db.flush()
        print(f"\nCreated: {school.name}  (code: {subdomain})")
    else:
        print(f"\nExists:  {school.name}  (code: {subdomain})")

    school_id = school.id

    admin_pos = await get_or_create_position(db, school_id, "School Administrator", [
        "school.view", "school.edit", "school.manage_users",
        "academic.view", "academic.create", "academic.edit", "academic.delete",
        "students.view", "students.create", "students.edit",
        "staff.view", "staff.create",
        "attendance.view", "attendance.record", "attendance.approve",
        "assessments.view", "assessments.enter_scores", "assessments.approve_scores",
        "fees.view", "fees.create", "fees.collect",
        "housing.view", "housing.manage",
        "reports.view", "reports.generate",
    ])
    teacher_pos = await get_or_create_position(db, school_id, "Class Teacher", [
        "students.view",
        "attendance.view", "attendance.record",
        "assessments.view", "assessments.enter_scores",
    ])
    finance_pos = await get_or_create_position(db, school_id, "Finance Officer", [
        "students.view",
        "fees.view", "fees.create", "fees.collect",
    ])

    for first, last, role, pos in [
        ("Admin", "User",    "admin",   admin_pos),
        ("Teacher", "User",  "teacher", teacher_pos),
        ("Finance", "User",  "finance", finance_pos),
    ]:
        email = f"{role}@{domain}"
        await create_staff_user(db, school_id, first, last, email, pos)
        print(f"  {email} / {DEMO_PASSWORD}")


async def seed():
    async with AsyncSessionLocal() as db:
        # Use the first available region/district from reference data
        region = await db.scalar(select(GhanaRegion).limit(1))
        district = await db.scalar(select(GhanaDistrict).limit(1))
        if not region or not district:
            print("ERROR: Reference data not seeded. Run seed_reference_data.py first.")
            return

        for cfg in DEMO_SCHOOLS:
            await seed_school(db, cfg, region.id, district.id)
        await db.commit()

    print("\n─────────────────────────────────────────")
    print("Visit http://localhost:5173")
    print("School code 'basic'  →  GES Basic School (green)")
    print("School code 'shs'    →  GES Senior High School (blue)")
    print("─────────────────────────────────────────")


if __name__ == "__main__":
    asyncio.run(seed())
