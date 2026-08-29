from __future__ import annotations
import uuid
from pydantic import BaseModel, field_validator

# The canonical permission matrix — every module and its valid actions.
PERMISSION_MATRIX: dict[str, list[str]] = {
    "school":      ["view", "edit", "manage_users"],
    "staff":       ["view", "create", "edit", "delete"],
    "students":    ["view", "create", "edit", "delete"],
    "academic":    ["view", "create", "edit", "delete"],
    "attendance":  ["view", "record", "approve"],
    "assessments": ["view", "enter_scores", "approve_scores", "record_behaviour"],
    "fees":        ["view", "collect", "manage"],
    "housing":     ["view", "assign", "manage"],
    "reports":     ["view", "generate"],
    "documents":   ["view", "manage"],
    "lesson_plans": ["view", "manage"],
}

VALID_PAIRS: set[tuple[str, str]] = {
    (mod, act) for mod, acts in PERMISSION_MATRIX.items() for act in acts
}


class PermissionEntry(BaseModel):
    module: str
    action: str
    is_allowed: bool

    @field_validator("module")
    @classmethod
    def valid_module(cls, v: str) -> str:
        if v not in PERMISSION_MATRIX:
            raise ValueError(f"Unknown module '{v}'")
        return v

    @field_validator("action")
    @classmethod
    def valid_action(cls, v: str) -> str:
        return v


class PositionWithPerms(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    is_template: bool
    school_id: uuid.UUID | None
    permissions: list[PermissionEntry]
    model_config = {"from_attributes": True}


class PositionPermissionsUpdate(BaseModel):
    permissions: list[PermissionEntry]
