import math
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class ApprovalPreview(BaseModel):
    assignment_id: str = Field(min_length=1, max_length=36)
    boundary: list[tuple[float, float]] = Field(min_length=4, max_length=101)

    @field_validator('boundary')
    @classmethod
    def boundary_coordinates(cls, points):
        valid_coordinates(points)
        if points[0] != points[-1]:
            raise ValueError('Close the polygon by repeating its first coordinate')
        longitudes = [x for x, _ in points]
        if max(longitudes) - min(longitudes) > 180:
            raise ValueError('Polygons crossing the antimeridian are not supported')
        return points


def valid_coordinates(points):
    if any(not math.isfinite(x) or not math.isfinite(y) or not -180 <= x <= 180 or not -85 <= y <= 85 for x, y in points):
        raise ValueError('Coordinates must be finite [longitude,latitude] pairs')
    return points


class MissionPlan(ApprovalPreview):
    name: str = Field(min_length=1, max_length=100)
    area_id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    waypoints: list[tuple[float, float]] = Field(min_length=2, max_length=100)
    altitude_m: float = Field(default=5, ge=2, le=8, allow_inf_nan=False)
    speed_m_s: float = Field(default=2, ge=.5, le=3, allow_inf_nan=False)
    synthetic_sensors: bool = False
    field_ids: list[str] = Field(default_factory=list, max_length=30)

    @field_validator('waypoints')
    @classmethod
    def coordinates(cls, points):
        return valid_coordinates(points)


class MissionUpdate(MissionPlan):
    plan_revision: int = Field(ge=1)


class ApprovalReason(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator('reason', mode='before')
    @classmethod
    def strip_reason(cls, value):
        return value.strip() if isinstance(value, str) else value


class ApprovalDecision(BaseModel):
    decision: Literal['Approved', 'Rejected']
    reason: str = Field(default='', max_length=2000)


ApprovalStatus = Literal['Pending', 'Approved', 'Rejected', 'Invalidated']


class ApprovalSpatialResult(BaseModel):
    required: bool
    outside_geometry: dict
    outside_m2: float


class ApprovalPreviewResult(ApprovalSpatialResult):
    assigned_boundary: dict


class ApprovalAssignmentSnapshot(BaseModel):
    id: str
    name: str
    boundary: dict
    revision: int
    supervisor_id: str
    supervisor_username: str | None


class ApprovalSnapshot(BaseModel):
    configuration: dict
    assignment: ApprovalAssignmentSnapshot
    outside_geometry: dict
    outside_m2: float


class ApprovalRecord(BaseModel):
    id: str
    mission_id: str
    assignment_id: str
    operator_id: str
    supervisor_id: str
    assignment_revision: int
    configuration_hash: str
    snapshot: ApprovalSnapshot
    reason: str
    status: ApprovalStatus
    requested_at: datetime
    decision_reason: str | None
    decided_by: str | None
    decided_at: datetime | None


class ApprovalContext(ApprovalSpatialResult):
    status: ApprovalStatus | Literal['Not Required'] | None
    can_execute: bool
    warning: str | None
    assignment: ApprovalAssignmentSnapshot | None
    request: ApprovalRecord | None
    history: list[ApprovalRecord]


class ApprovalMissionSummary(BaseModel):
    id: str
    name: str


class ApprovalInboxItem(BaseModel):
    request: ApprovalRecord
    status: ApprovalStatus
    current: bool
    mission: ApprovalMissionSummary
    operator_username: str | None


class Assignment(BaseModel):
    operator_id: str
    field_ids: list[str] = Field(default_factory=list, max_length=30)


class ReviewInput(BaseModel):
    assessment: Literal['needs_investigation', 'likely_false_positive', 'inconclusive']
    notes: str = Field(min_length=1, max_length=4000)


class StopRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
