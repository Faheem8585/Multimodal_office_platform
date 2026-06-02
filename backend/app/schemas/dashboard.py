"""Dashboard schemas."""

from pydantic import BaseModel

from app.models.enums import Department
from app.schemas.notification import ActivityOut


class StatCard(BaseModel):
    key: str
    label: str
    value: float
    unit: str | None = None
    link: str | None = None


class DashboardResponse(BaseModel):
    department: Department
    role_tier: str
    stats: list[StatCard]
    recent_activity: list[ActivityOut]
