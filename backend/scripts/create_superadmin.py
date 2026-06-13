"""
One-time script to create the superadmin user.

Run from backend/ directory:
    python scripts/create_superadmin.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.auth import hash_password
from app.core.config import settings
# Import all models so SQLAlchemy resolves FK references
from app.models import school, auth, staff, academic, students, housing, attendance, assessments, fees, documents  # noqa: F401
from app.models.auth import User, LoginType


async def create_superadmin():
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(
            select(User).where(User.email == settings.superadmin_email)
        )
        if existing:
            print(f"Superadmin already exists: {settings.superadmin_email}")
            return

        user = User(
            login_type=LoginType.EMAIL,
            email=settings.superadmin_email,
            password_hash=hash_password(settings.superadmin_password),
            is_active=True,
            is_superadmin=True,
            school_id=None,
        )
        db.add(user)
        await db.commit()
        print(f"Superadmin created: {settings.superadmin_email}")


if __name__ == "__main__":
    asyncio.run(create_superadmin())
