import uuid
from datetime import date as _date

from pydantic import BaseModel, Field


class HolidayCreate(BaseModel):
    name: str = Field(max_length=100)
    date: _date
    is_recurring: bool = True
    description: str | None = Field(default=None, max_length=300)


class HolidayUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    date: _date | None = None
    is_recurring: bool | None = None
    description: str | None = Field(default=None, max_length=300)


class HolidayRead(BaseModel):
    id: uuid.UUID
    name: str
    date: _date
    is_recurring: bool
    description: str | None
    model_config = {"from_attributes": True}
