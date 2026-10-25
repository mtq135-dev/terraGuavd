"""Version-one foundation response contracts; operational records are pending."""
from typing import Literal
from pydantic import BaseModel

Role = Literal["administrator", "mission_operator", "detection_analyst", "supervisor", "field_personnel"]


class Identity(BaseModel):
    id: str
    username: str
    role: Role
    permissions: list[str]
    active: bool = True
    denied_permissions: list[str] = []


class SessionToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int


class Dashboard(BaseModel):
    role: Role
    mode: Literal["simulation-only"]
    missions: list[dict]
    potential_detections: list[dict]
    survey_attempts: list[dict]
    alerts: list[dict]
    telemetry: dict | None
    simulation: str
    detection_engine: str
    notice: str
