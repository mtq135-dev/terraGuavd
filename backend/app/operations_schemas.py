import math
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class MissionPlan(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    assignment_id: str = Field(min_length=1, max_length=36)
    area_id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    boundary: list[tuple[float, float]] = Field(min_length=4, max_length=101)
    waypoints: list[tuple[float, float]] = Field(min_length=2, max_length=100)
    altitude_m: float = Field(default=5, ge=2, le=8, allow_inf_nan=False)
    speed_m_s: float = Field(default=2, ge=.5, le=3, allow_inf_nan=False)
    synthetic_sensors: bool = False
    field_ids: list[str] = Field(default_factory=list, max_length=30)

    @field_validator('boundary', 'waypoints')
    @classmethod
    def coordinates(cls, points):
        if any(not math.isfinite(x) or not math.isfinite(y) or not -180 <= x <= 180 or not -85 <= y <= 85 for x,y in points):
            raise ValueError('Coordinates must be finite [longitude,latitude] pairs')
        return points


class Assignment(BaseModel):
    operator_id: str
    field_ids: list[str] = Field(default_factory=list, max_length=30)


class ReviewInput(BaseModel):
    assessment: Literal['needs_investigation', 'likely_false_positive', 'inconclusive']
    notes: str = Field(min_length=1, max_length=4000)


class StopRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
