"""
Document upload/list/download/delete integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_documents.py -v
"""
import io
import uuid
from datetime import date
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.config import settings
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import GhanaDistrict, GhanaRegion, School, SchoolType
from app.models.students import Student


async def _second_school_auth(client: AsyncClient, db_session: AsyncSession) -> dict:
    """Create a second school + superadmin and return their auth headers —
    mirrors test_academic.py's _second_shs_school_auth."""
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    school = School(
        name="Second Doc Test School", school_code="DOC002",
        school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(school)
    await db_session.flush()
    user = User(
        login_type=LoginType.EMAIL, email="second-doc-admin@test.gh",
        password_hash=hash_password("pw"), is_active=True,
        is_superadmin=True, school_id=school.id,
    )
    db_session.add(user)
    await db_session.flush()
    resp = await client.post("/auth/superadmin-login", json={
        "identifier": "second-doc-admin@test.gh", "password": "pw",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> tuple[dict, str]:
    """Create a staff member holding `position_code`, give them a login, and
    return (their bearer-token auth headers, their staff_member id) —
    mirrors test_student_export.py's helper."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json={
        "staff_number": f"TST-{position_code}", "first_name": "Test", "last_name": position_code.title(),
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    email = f"{position_code.lower()}-docs@presec-test.edu.gh"
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
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff_id


@pytest.mark.asyncio
async def test_upload_document(
    client: AsyncClient, auth: dict, student: Student
):
    pdf_bytes = b"%PDF-1.4 test"
    resp = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": ("cert.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=auth,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["file_name"] == "cert.pdf"
    assert data["entity_type"] == "student"
    assert str(data["entity_id"]) == str(student.id)
    assert data["document_type"] == "certificate"


@pytest.mark.asyncio
async def test_upload_disallowed_mime_type(
    client: AsyncClient, auth: dict, student: Student
):
    resp = await client.post(
        f"/documents/student/{student.id}?document_type=data",
        files={"file": ("data.csv", io.BytesIO(b"a,b,c"), "text/csv")},
        headers=auth,
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_list_documents(
    client: AsyncClient, auth: dict, student: Student
):
    await client.post(
        f"/documents/student/{student.id}?document_type=photo",
        files={"file": ("photo.jpg", io.BytesIO(b"\xff\xd8\xff\xe0fake-jpeg-body"), "image/jpeg")},
        headers=auth,
    )
    resp = await client.get(f"/documents/student/{student.id}", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_list_documents_wrong_school(
    client: AsyncClient, auth: dict
):
    """Documents for a random entity_id return empty list, not 404."""
    resp = await client.get(f"/documents/student/{uuid.uuid4()}", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_download_document(
    client: AsyncClient, auth: dict, student: Student
):
    pdf_bytes = b"%PDF-1.4 sample"
    upload = await client.post(
        f"/documents/student/{student.id}?document_type=letter",
        files={"file": ("letter.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=auth,
    )
    doc_id = upload.json()["id"]
    resp = await client.get(f"/documents/{doc_id}/download", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
async def test_delete_document(
    client: AsyncClient, auth: dict, student: Student
):
    upload = await client.post(
        f"/documents/student/{student.id}?document_type=form",
        files={"file": ("form.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=auth,
    )
    doc_id = upload.json()["id"]
    del_resp = await client.delete(f"/documents/{doc_id}", headers=auth)
    assert del_resp.status_code == 204
    # Confirm gone
    dl_resp = await client.get(f"/documents/{doc_id}/download", headers=auth)
    assert dl_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_document(
    client: AsyncClient, auth: dict
):
    resp = await client.delete(f"/documents/{uuid.uuid4()}", headers=auth)
    assert resp.status_code == 404


# ── Cross-tenant ownership ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_rejects_cross_school_entity(
    client: AsyncClient, auth: dict, db_session: AsyncSession, student: Student,
):
    """A student belonging to a different school can't have a document
    uploaded against them just because the id was guessable."""
    other_school_auth = await _second_school_auth(client, db_session)
    resp = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=other_school_auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_entity_type(
    client: AsyncClient, auth: dict,
):
    resp = await client.post(
        f"/documents/widget/{uuid.uuid4()}?document_type=whatever",
        files={"file": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=auth,
    )
    assert resp.status_code == 422


# ── MIME-type spoofing ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_rejects_content_not_matching_declared_type(
    client: AsyncClient, auth: dict, student: Student,
):
    """Content-Type is client-declared and trivially spoofable — the actual
    bytes must match the claimed type, not just the allowlist check."""
    resp = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": ("not-a-pdf.pdf", io.BytesIO(b"<html>fake</html>"), "application/pdf")},
        headers=auth,
    )
    assert resp.status_code == 415


# ── Filename collision ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_same_filename_uploaded_twice_does_not_alias(
    client: AsyncClient, auth: dict, student: Student,
):
    """Two uploads with the identical original filename for the same
    student must not silently overwrite each other on disk — each
    DocumentRecord must serve back its own content."""
    first = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4 FIRST"), "application/pdf")},
        headers=auth,
    )
    second = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4 SECOND"), "application/pdf")},
        headers=auth,
    )
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    dl_first = await client.get(f"/documents/{first.json()['id']}/download", headers=auth)
    dl_second = await client.get(f"/documents/{second.json()['id']}/download", headers=auth)
    assert dl_first.content == b"%PDF-1.4 FIRST"
    assert dl_second.content == b"%PDF-1.4 SECOND"


# ── Permission model / per-entity scoping ─────────────────────────────────────

@pytest.mark.asyncio
async def test_class_teacher_can_manage_documents_for_own_student(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school, student: Student,
    school_class, academic_year, redis_permissions: None,
):
    """Previously gated on the unrelated reports.generate permission, which
    CLASS_TEACHER never held — they couldn't even list or download a
    document for their own student. Now gated on documents.view/manage,
    scoped (core/student_scope.py) to students in a class the caller is an
    active ClassTeacher of."""
    from app.models.academic import ClassTeacher
    from app.models.students import StudentClassAssignment

    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")

    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    upload = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=teacher_auth,
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    list_resp = await client.get(f"/documents/student/{student.id}", headers=teacher_auth)
    assert list_resp.status_code == 200

    dl_resp = await client.get(f"/documents/{doc_id}/download", headers=teacher_auth)
    assert dl_resp.status_code == 200

    del_resp = await client.delete(f"/documents/{doc_id}", headers=teacher_auth)
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_class_teacher_cannot_manage_documents_for_unassigned_student(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school, student: Student,
    redis_permissions: None,
):
    """The bug this scoping closes: a class teacher with documents.manage
    but NO ClassTeacher assignment to this student's class must not be able
    to upload/list/download/delete their documents at all."""
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")

    upload = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=teacher_auth,
    )
    assert upload.status_code == 404

    list_resp = await client.get(f"/documents/student/{student.id}", headers=teacher_auth)
    assert list_resp.status_code == 404

    # A real document uploaded by the (unrestricted) admin must also be
    # unreachable to this out-of-scope class teacher.
    admin_upload = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=auth,
    )
    doc_id = admin_upload.json()["id"]
    dl_resp = await client.get(f"/documents/{doc_id}/download", headers=teacher_auth)
    assert dl_resp.status_code == 404
    del_resp = await client.delete(f"/documents/{doc_id}", headers=teacher_auth)
    assert del_resp.status_code == 404


@pytest.mark.asyncio
async def test_class_teacher_cannot_manage_documents_for_other_staff_member(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school, redis_permissions: None,
):
    """entity_type=staff documents (id cards, contracts) require the same
    self-or-staff.edit tier as editing that staff member directly — a class
    teacher holding documents.manage must not reach a colleague's files."""
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    other_staff_id = (await client.post("/staff", json={
        "staff_number": "DOCS-OTHER", "first_name": "Other", "last_name": "Colleague",
    }, headers=auth)).json()["id"]

    upload = await client.post(
        f"/documents/staff/{other_staff_id}?document_type=id_card",
        files={"file": ("id.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=teacher_auth,
    )
    assert upload.status_code == 403

    admin_upload = await client.post(
        f"/documents/staff/{other_staff_id}?document_type=id_card",
        files={"file": ("id.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=auth,
    )
    doc_id = admin_upload.json()["id"]
    dl_resp = await client.get(f"/documents/{doc_id}/download", headers=teacher_auth)
    assert dl_resp.status_code == 403


# ── Secure storage (unauthenticated static-mount exposure fix) ────────────────

@pytest.mark.asyncio
async def test_uploaded_document_not_reachable_via_public_uploads_mount(
    client: AsyncClient, auth: dict, student: Student,
):
    """DocumentRecord files live under secure_upload_dir, which main.py never
    mounts as a static route (unlike local_upload_dir, mounted at /uploads
    for logos/photos). Confirms a document can't be fetched unauthenticated
    just by guessing/replaying the same relative path the old code used to
    write under local_upload_dir."""
    upload = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4 secret"), "application/pdf")},
        headers=auth,
    )
    assert upload.status_code == 201
    rec_id = upload.json()["id"]
    file_name = upload.json()["file_name"]

    # The exact relative path shape upload_document() builds — proves the
    # file is neither reachable at that path nor anywhere else under the
    # public mount, without needing the unauthenticated client to know the
    # real stored (uuid-prefixed) filename.
    guessed = f"/uploads/documents/{student.school_id}/student/{student.id}/{rec_id}_{file_name}"
    resp = await client.get(guessed)
    assert resp.status_code == 404

    # The authenticated, scoped download endpoint still works from the same
    # storage location — proves this isn't reachable because it was never
    # written at all, only because it isn't publicly mounted.
    dl_resp = await client.get(f"/documents/{rec_id}/download", headers=auth)
    assert dl_resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_document_removes_file_from_disk(
    client: AsyncClient, auth: dict, student: Student,
):
    upload = await client.post(
        f"/documents/student/{student.id}?document_type=form",
        files={"file": ("form.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=auth,
    )
    rel_path = f"documents/{student.school_id}/student/{student.id}/"
    doc_id = upload.json()["id"]
    matches = list((Path(settings.secure_upload_dir) / rel_path).glob(f"{doc_id}_*"))
    assert len(matches) == 1
    on_disk = matches[0]
    assert on_disk.exists()

    del_resp = await client.delete(f"/documents/{doc_id}", headers=auth)
    assert del_resp.status_code == 204
    assert not on_disk.exists()


# ── Input length validation ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_rejects_oversized_filename(
    client: AsyncClient, auth: dict, student: Student,
):
    long_name = "a" * 250 + ".pdf"
    resp = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": (long_name, io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=auth,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_rejects_oversized_document_type(
    client: AsyncClient, auth: dict, student: Student,
):
    resp = await client.post(
        f"/documents/student/{student.id}?document_type={'x' * 150}",
        files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=auth,
    )
    assert resp.status_code == 422


# ── Housemaster boarding-document scope ───────────────────────────────────────

@pytest.mark.asyncio
async def test_housemaster_can_manage_documents_for_student_in_own_house(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school, student: Student,
    academic_year, redis_permissions: None,
):
    """HOUSEMASTER holds documents.manage for exactly this reason (exeat
    letters, incident forms) but had no scoping check that ever recognised
    the role at all — previously fell through to a plain 404 for every
    student, HouseMaster row or not. Confirms the new
    is_house_master_of_student() branch actually grants access to a student
    genuinely resident in the house they run."""
    from app.models.housing import House, HouseGender, HouseMaster, StudentHouseAssignment

    hm_auth, staff_id = await _login_as_position(client, auth, db_session, school, "HOUSEMASTER")

    house = House(
        school_id=school.id, name="Hall Doc", code="DOCH", gender=HouseGender.MIXED, is_active=True,
    )
    db_session.add(house)
    await db_session.flush()
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    db_session.add(StudentHouseAssignment(
        school_id=school.id, student_id=student.id, house_id=house.id,
        academic_year_id=academic_year.id, assigned_at=date.today(),
    ))
    await db_session.flush()

    upload = await client.post(
        f"/documents/student/{student.id}?document_type=exeat_letter",
        files={"file": ("exeat.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=hm_auth,
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    dl_resp = await client.get(f"/documents/{doc_id}/download", headers=hm_auth)
    assert dl_resp.status_code == 200

    del_resp = await client.delete(f"/documents/{doc_id}", headers=hm_auth)
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_housemaster_cannot_manage_documents_for_student_in_other_house(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school, student: Student,
    academic_year, redis_permissions: None,
):
    """The student is resident in a DIFFERENT house than the one this
    housemaster runs — must still 404, same as any other out-of-scope
    student."""
    from app.models.housing import House, HouseGender, HouseMaster, StudentHouseAssignment

    hm_auth, staff_id = await _login_as_position(client, auth, db_session, school, "HOUSEMASTER")

    own_house = House(
        school_id=school.id, name="Hall Own", code="OWNH", gender=HouseGender.MIXED, is_active=True,
    )
    other_house = House(
        school_id=school.id, name="Hall Other", code="OTHH", gender=HouseGender.MIXED, is_active=True,
    )
    db_session.add_all([own_house, other_house])
    await db_session.flush()
    db_session.add(HouseMaster(
        school_id=school.id, house_id=own_house.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    db_session.add(StudentHouseAssignment(
        school_id=school.id, student_id=student.id, house_id=other_house.id,
        academic_year_id=academic_year.id, assigned_at=date.today(),
    ))
    await db_session.flush()

    upload = await client.post(
        f"/documents/student/{student.id}?document_type=exeat_letter",
        files={"file": ("exeat.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=hm_auth,
    )
    assert upload.status_code == 404


@pytest.mark.asyncio
async def test_class_teacher_can_manage_own_staff_documents(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school, redis_permissions: None,
):
    """Self-service: CLASS_TEACHER holds documents.manage but not
    staff.edit — assert_self_or_permission's self branch still lets them
    manage their OWN staff document (e.g. uploading their own certificate),
    same tier as PATCH /staff/{id} already allows for self-edit."""
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")

    upload = await client.post(
        f"/documents/staff/{staff_id}?document_type=certificate",
        files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=teacher_auth,
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    dl_resp = await client.get(f"/documents/{doc_id}/download", headers=teacher_auth)
    assert dl_resp.status_code == 200

    del_resp = await client.delete(f"/documents/{doc_id}", headers=teacher_auth)
    assert del_resp.status_code == 204
