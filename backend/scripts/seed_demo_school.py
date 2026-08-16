"""
Seed two generic demo schools for browser testing.

Run inside Docker:
    docker compose exec api python scripts/seed_demo_school.py

Creates:
  GES Basic School  (subdomain: basic, ownership: PUBLIC)
    admin@basic.school   / Demo1234!  — School Administrator
    teacher@basic.school / Demo1234!  — Teacher
    finance@basic.school / Demo1234!  — Finance Officer

  Demonstration Senior High School  (subdomain: shs, ownership: PUBLIC)
    admin@shs.school   / Demo1234!  — School Administrator
    teacher@shs.school / Demo1234!  — Teacher
    finance@shs.school / Demo1234!  — Finance Officer

Safe to re-run: skips existing rows and fills any gaps.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.auth import hash_password
# All models must be imported so SQLAlchemy resolves FK references
from app.models import school as _sm, auth as _am, staff as _stm, staff_history as _sth  # noqa: F401
from app.models import academic, students, housing, attendance, assessments, fees, documents  # noqa: F401
from app.models.school import School, SchoolType, SchoolOwnership, GhanaRegion, GhanaDistrict
from app.models.auth import User, LoginType, StaffPosition, PositionPermission
from app.models.staff import StaffMember, StaffCategory, staff_member_positions

DEMO_PASSWORD = "Demo1234!"

DEMO_SCHOOLS = [
    {
        "subdomain":    "basic",
        "school_code":  "BASIC-DEMO",
        "name":         "Basic School",
        "short_name":   "Basic School",
        "school_type":  "BASIC",
        "ownership":    "PUBLIC",
        "brand_color":  "#15803d",
        "motto":        "Learning for Life",
        "email_domain": "basic.school",
    },
    {
        "subdomain":    "shs",
        "school_code":  "SHS-DEMO",
        "name":         "Senior High School",
        "short_name":   "SHS",
        "school_type":  "SHS",
        "ownership":    "PUBLIC",
        "brand_color":  "#1e40af",
        "motto":        "Excellence in Education",
        "email_domain": "shs.school",
    },
]

# Category codes seeded by seed_reference_data.py
CATEGORY_BY_ROLE = {
    "admin":   "ADMINISTRATIVE",
    "teacher": "TEACHING",
    "finance": "ACCOUNTING",
}


async def get_category_id(db, code: str) -> object:
    cat = await db.scalar(
        select(StaffCategory).where(
            StaffCategory.code == code,
            StaffCategory.school_id.is_(None),  # GES template
        )
    )
    return cat.id if cat else None


async def get_template_position(db, code: str) -> StaffPosition:
    """Look up one of the real shared templates seed_reference_data.py owns
    (school_id IS NULL) — this script used to hand-roll its own ad hoc
    "School Administrator"/"Finance Officer"/"Teacher" positions with a
    second, smaller, partly-invalid permission list (fees.create and
    staff.approve_leave aren't real permissions — see PERMISSION_MATRIX),
    a second position-definition path that duplicated HEAD/BURSAR/TEACHER
    under different names. Reusing the real templates means there is
    exactly one place position permissions are ever defined."""
    pos = await db.scalar(
        select(StaffPosition).where(StaffPosition.code == code, StaffPosition.school_id.is_(None))
    )
    assert pos is not None, f"StaffPosition {code!r} not found — run seed_reference_data.py first."
    return pos


async def _migrate_off_legacy_ad_hoc_position(db, school_id, staff_member_id) -> None:
    """Self-heal a demo staff member created before this script stopped
    hand-rolling its own "School Administrator"/"Finance Officer"/per-school
    "Teacher" positions (see get_template_position's docstring). Unlinks any
    such legacy position still held by this staff member and, if nobody else
    is left holding it, deletes the now-orphaned row entirely — so re-running
    this script against a stack that still carries the old duplicate data
    converges it onto the single real template, not just adds to it."""
    legacy = (await db.scalars(
        select(StaffPosition).where(
            StaffPosition.school_id == school_id,
            StaffPosition.is_template.is_(False),
            (StaffPosition.name.in_(["School Administrator", "Finance Officer"]))
            | (StaffPosition.code == "TEACHER"),
        )
    )).all()
    for pos in legacy:
        link = await db.scalar(
            select(staff_member_positions).where(
                staff_member_positions.c.staff_member_id == staff_member_id,
                staff_member_positions.c.position_id == pos.id,
            )
        )
        if link is None:
            continue
        await db.execute(
            staff_member_positions.delete().where(
                staff_member_positions.c.staff_member_id == staff_member_id,
                staff_member_positions.c.position_id == pos.id,
            )
        )
        print(f"  Migrated off legacy position: {pos.name}")
        still_used = await db.scalar(
            select(staff_member_positions).where(staff_member_positions.c.position_id == pos.id)
        )
        if still_used is None:
            await db.execute(
                PositionPermission.__table__.delete().where(PositionPermission.position_id == pos.id)
            )
            await db.delete(pos)


async def create_staff_user(
    db, school_id, role: str, first: str, last: str,
    email: str, staff_num: str, position: StaffPosition, category_id,
) -> None:
    existing_user = await db.scalar(select(User).where(User.email == email))
    if existing_user:
        # Patch category_id if missing
        if existing_user.staff_member_id and category_id:
            member = await db.get(StaffMember, existing_user.staff_member_id)
            if member and member.category_id is None:
                member.category_id = category_id
                print(f"  Patched category for {email}")
        # Ensure position link
        if existing_user.staff_member_id:
            await _migrate_off_legacy_ad_hoc_position(db, school_id, existing_user.staff_member_id)
            has_pos = await db.scalar(
                select(staff_member_positions).where(
                    staff_member_positions.c.staff_member_id == existing_user.staff_member_id,
                    staff_member_positions.c.position_id == position.id,
                )
            )
            if not has_pos:
                await db.execute(
                    staff_member_positions.insert().values(
                        staff_member_id=existing_user.staff_member_id,
                        position_id=position.id,
                    )
                )
        print(f"  Exists:  {email}")
        return

    member = StaffMember(
        school_id=school_id,
        staff_number=staff_num,
        first_name=first,
        last_name=last,
        email=email,
        is_active=True,
        category_id=category_id,
    )
    db.add(member)
    await db.flush()
    await db.execute(
        staff_member_positions.insert().values(
            staff_member_id=member.id, position_id=position.id,
        )
    )
    db.add(User(
        school_id=school_id,
        login_type=LoginType.EMAIL,
        email=email,
        password_hash=hash_password(DEMO_PASSWORD),
        is_active=True,
        staff_member_id=member.id,
    ))
    print(f"  Created: {email} / {DEMO_PASSWORD}")


async def seed_school(db, cfg: dict, region_id, district_id) -> None:
    subdomain = cfg["subdomain"]
    domain    = cfg["email_domain"]

    school = await db.scalar(select(School).where(School.subdomain == subdomain))
    if not school:
        school = School(
            name=cfg["name"],
            short_name=cfg["short_name"],
            school_code=cfg["school_code"],
            school_type=SchoolType[cfg["school_type"]],
            ownership=SchoolOwnership[cfg["ownership"]],
            region_id=region_id,
            district_id=district_id,
            subdomain=subdomain,
            brand_color=cfg["brand_color"],
            motto=cfg["motto"],
            is_active=True,
        )
        db.add(school)
        await db.flush()
        print(f"\nCreated: {school.name}  ({subdomain})")
    else:
        print(f"\nExists:  {school.name}  ({subdomain})")

    school_id = school.id

    admin_pos   = await get_template_position(db, "HEAD")
    teacher_pos = await get_template_position(db, "TEACHER")
    finance_pos = await get_template_position(db, "BURSAR")

    admin_cat   = await get_category_id(db, CATEGORY_BY_ROLE["admin"])
    teacher_cat = await get_category_id(db, CATEGORY_BY_ROLE["teacher"])
    finance_cat = await get_category_id(db, CATEGORY_BY_ROLE["finance"])

    staff_defs = [
        ("admin",   "Admin",   "User", f"admin@{domain}",   f"{subdomain.upper()}-ADM-001", admin_pos,   admin_cat),
        ("teacher", "Teacher", "User", f"teacher@{domain}", f"{subdomain.upper()}-TEA-001", teacher_pos, teacher_cat),
        ("finance", "Finance", "User", f"finance@{domain}", f"{subdomain.upper()}-FIN-001", finance_pos, finance_cat),
    ]
    for role, first, last, email, staff_num, pos, cat_id in staff_defs:
        await create_staff_user(db, school_id, role, first, last, email, staff_num, pos, cat_id)


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        region   = await db.scalar(select(GhanaRegion).limit(1))
        district = await db.scalar(select(GhanaDistrict).limit(1))
        if not region or not district:
            print("ERROR: Run seed_reference_data.py first.")
            return

        for cfg in DEMO_SCHOOLS:
            await seed_school(db, cfg, region.id, district.id)

        await db.commit()

    print("\n─────────────────────────────────────────────")
    print("Visit http://localhost:5173")
    print("  basic  →  GES Basic School        (green)")
    print("  shs    →  Demo Senior High School  (blue)")
    print("  Password for all accounts: Demo1234!")
    print("─────────────────────────────────────────────")


if __name__ == "__main__":
    asyncio.run(seed())
