"""
Permission sets for the 6 StaffPosition templates removed from
scripts/reference_data.py (redundant with the per-staff personal permission
override — see that file's own comment for the full rationale).

Several tests still need to exercise these exact permission combinations
(e.g. "approve_scores without students.delete", the specific boundary
EXAM_OFFICER used to represent) — not because the position names themselves
matter, but because the combination does. Test helpers across this
directory (`_login_as_position`/`_make_staff_with_position`) fall back to
building an ad hoc, school-scoped StaffPosition from this table when a code
isn't found among the real seeded templates, so every pre-existing test
call site keeps working unchanged and keeps testing the same boundary it
always did.

Not used by application code — test-only.
"""

LEGACY_POSITION_PERMISSIONS: dict[str, list[tuple[str, str]]] = {
    "DEPUTY_HEAD": [
        ("school", "view"), ("school", "edit"),
        ("staff", "view"), ("staff", "create"), ("staff", "edit"),
        ("students", "view"), ("students", "create"), ("students", "edit"), ("students", "delete"),
        ("academic", "view"), ("academic", "create"), ("academic", "edit"),
        ("attendance", "view"), ("attendance", "record"), ("attendance", "approve"),
        ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
        ("assessments", "record_behaviour"),
        ("fees", "view"), ("fees", "collect"),
        ("housing", "view"), ("housing", "assign"),
        ("reports", "view"), ("reports", "generate"),
        ("documents", "view"), ("documents", "manage"),
    ],
    "ASSISTANT_HEAD_ACADEMICS": [
        ("school", "view"),
        ("staff", "view"),
        ("students", "view"), ("students", "edit"), ("students", "delete"),
        ("academic", "view"), ("academic", "edit"),
        ("attendance", "view"), ("attendance", "record"), ("attendance", "approve"),
        ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
        ("assessments", "record_behaviour"),
        ("reports", "view"), ("reports", "generate"),
        ("documents", "view"), ("documents", "manage"),
    ],
    "ASSISTANT_HEAD_ADMINISTRATION": [
        ("school", "view"), ("school", "edit"),
        ("staff", "view"), ("staff", "create"), ("staff", "edit"),
        ("students", "view"),
        ("reports", "view"), ("reports", "generate"),
        ("documents", "view"), ("documents", "manage"),
    ],
    "ASSISTANT_HEAD_BOARDING": [
        ("school", "view"),
        ("students", "view"),
        ("housing", "view"), ("housing", "assign"), ("housing", "manage"),
        ("attendance", "view"), ("attendance", "record"),
        ("reports", "view"), ("reports", "generate"),
        ("documents", "view"), ("documents", "manage"),
    ],
    "HOD": [
        ("school", "view"),
        ("staff", "view"),
        ("students", "view"), ("students", "edit"), ("students", "delete"),
        ("academic", "view"), ("academic", "edit"),
        ("attendance", "view"), ("attendance", "record"),
        ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
        ("assessments", "record_behaviour"),
        ("reports", "view"), ("reports", "generate"),
        ("documents", "view"), ("documents", "manage"),
    ],
    "EXAM_OFFICER": [
        ("school", "view"),
        ("students", "view"),
        ("academic", "view"), ("academic", "edit"),
        ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
        ("assessments", "record_behaviour"),
        ("reports", "view"), ("reports", "generate"),
        ("documents", "view"), ("documents", "manage"),
    ],
}
