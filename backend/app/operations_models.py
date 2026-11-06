"""Persistent prototype records. Geometry columns are managed by PostGIS migration."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class Mission(Base):
    __tablename__ = "missions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    area_id: Mapped[str] = mapped_column(String(80), index=True)
    assignment_id: Mapped[str | None] = mapped_column(ForeignKey('survey_area_assignments.id'), nullable=True, index=True)
    operator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    field_ids: Mapped[list] = mapped_column(JSON, default=list)
    boundary: Mapped[dict] = mapped_column(JSON)
    waypoints: Mapped[list] = mapped_column(JSON)
    altitude_m: Mapped[float] = mapped_column(Float)
    speed_m_s: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(32), default="DRAFT")
    runtime: Mapped[str] = mapped_column(String(32), default="px4-gazebo")
    uav_id: Mapped[str] = mapped_column(ForeignKey('uavs.id'), default="sitl-01")
    synthetic_sensors: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_revision: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MissionEvent(Base):
    __tablename__ = "mission_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    actor_username: Mapped[str | None] = mapped_column(String(80))
    priority: Mapped[str | None] = mapped_column(String(16))


class MissionApprovalRequest(Base):
    __tablename__ = 'mission_approval_requests'
    __table_args__ = (
        CheckConstraint("status IN ('Pending','Approved','Rejected','Invalidated')", name='valid_mission_approval_status'),
        Index('mission_approval_mission_id_idx', 'mission_id'),
        Index('mission_approval_operator_id_idx', 'operator_id'),
        Index('mission_approval_supervisor_id_idx', 'supervisor_id'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey('missions.id'))
    assignment_id: Mapped[str] = mapped_column(ForeignKey('survey_area_assignments.id'))
    operator_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    supervisor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    assignment_revision: Mapped[int] = mapped_column(Integer)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    altitude_m: Mapped[float] = mapped_column(Float)
    speed_m_s: Mapped[float] = mapped_column(Float)
    battery_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(40))
    sensor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Detection(Base):
    __tablename__ = "detections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    observation_id: Mapped[str] = mapped_column(ForeignKey("observations.id"))
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    classification: Mapped[str] = mapped_column(String(40), default="potential_target")
    processing_version: Mapped[str] = mapped_column(String(80))
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AnalystReview(Base):
    __tablename__ = "analyst_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    detection_id: Mapped[str] = mapped_column(ForeignKey("detections.id"), index=True)
    analyst_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    assessment: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SurveyAttempt(Base):
    __tablename__ = "survey_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), unique=True)
    area_id: Mapped[str] = mapped_column(String(80), index=True)
    uav_id: Mapped[str] = mapped_column(ForeignKey('uavs.id'), default="sitl-01")
    status: Mapped[str] = mapped_column(String(32))
    coverage_percent: Mapped[float] = mapped_column(Float)
    geometry: Mapped[dict] = mapped_column(JSON)
    algorithm_version: Mapped[str] = mapped_column(String(80))
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VehicleLease(Base):
    __tablename__ = "vehicle_leases"
    id: Mapped[str] = mapped_column(ForeignKey('uavs.id'), primary_key=True)
    mission_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class UAVType(Base):
    __tablename__ = 'uav_types'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    category: Mapped[str] = mapped_column(String(40))
    simulation_profile: Mapped[str] = mapped_column(String(40))
    specifications: Mapped[dict] = mapped_column(JSON, default=dict)


class UAV(Base):
    __tablename__ = 'uavs'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type_id: Mapped[str] = mapped_column(ForeignKey('uav_types.id'))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    runtime_slot: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SurveyAreaAssignment(Base):
    __tablename__ = 'survey_area_assignments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    operator_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    boundary: Mapped[dict] = mapped_column(JSON)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SurveyAreaEvent(Base):
    __tablename__ = 'survey_area_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(ForeignKey('survey_area_assignments.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(40))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
