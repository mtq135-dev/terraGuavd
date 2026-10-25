"""Supervisor area assignments. Progress is geographic evidence, never flight counts."""
from datetime import UTC, datetime
import json
import math
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text

from .models import User
from .operations_models import Mission, MissionEvent, SurveyAreaAssignment, SurveyAreaEvent, SurveyAttempt
from .security import effective_permissions, Db, ROLE_PERMISSIONS, audit, current_user
from terraguavd_detection.processing import COVERAGE_VERSION

ACTIVE = {'STARTING_SIMULATION','WAITING_FOR_VEHICLE','UPLOADING','EXECUTING','PAUSED','RESUMING','CANCELLING'}
router = APIRouter(prefix='/api/v1/survey-areas', tags=['Survey area assignments'])
Identity = Annotated[User, Depends(current_user)]
NOTICE = 'Experimental mock sensor coverage only. Surveyed does not mean cleared or safe.'


class AreaInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=4000)
    operator_id: str = Field(min_length=1, max_length=36)
    boundary: list[tuple[float,float]] = Field(min_length=4, max_length=501)
    deadline: datetime | None = None

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError('Assignment name is required')
        return value.strip()

    @field_validator('boundary')
    @classmethod
    def valid_coordinates(cls, points):
        if points[0]!=points[-1]:
            raise ValueError('Close the polygon by repeating its first coordinate')
        if any(not math.isfinite(x) or not math.isfinite(y) or not -180<=x<=180 or not -85<=y<=85 for x,y in points):
            raise ValueError('Use finite [longitude, latitude] coordinates')
        if max(x for x,y in points)-min(x for x,y in points)>180:
            raise ValueError('Polygons crossing the antimeridian are not supported')
        return points

    @field_validator('deadline')
    @classmethod
    def utc_deadline(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError('Deadline must include a time zone')
        return value.astimezone(UTC) if value else None


class AreaUpdate(AreaInput):
    revision: int = Field(ge=1)


def permission(user, manage=False):
    if ('survey_areas:manage' if manage else 'survey_areas:read') not in effective_permissions(user):
        raise HTTPException(403,'Supervisor permission required' if manage else 'Survey area access denied')


def get_area(db, area_id, user=None, lock=False):
    if user:
        permission(user)
    query=select(SurveyAreaAssignment).where(SurveyAreaAssignment.id==area_id)
    if lock:
        query=query.with_for_update().execution_options(populate_existing=True)
    row=db.scalar(query)
    if row is None or user and user.role!='supervisor' and row.operator_id!=user.id:
        raise HTTPException(404,'Survey area assignment not found')
    return row


def polygon(body):
    return {'type':'Polygon','coordinates':[body.boundary]}


def validate_area(db, geometry):
    valid,area=db.execute(text('''WITH g AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) p)
        SELECT ST_IsValid(p), ST_Area(p::geography) FROM g'''),{'g':json.dumps(geometry)}).one()
    if not valid or not 10<=area<=100_000_000:
        raise HTTPException(422,'Use a valid polygon of 10 m² to 100 km²')


def check_mission_area(db, mission):
    # Pre-upgrade unassigned missions retain their original workflow/history.
    if not mission.assignment_id:
        return
    parent=get_area(db,mission.assignment_id,lock=True)
    if parent.operator_id!=mission.operator_id:
        raise HTTPException(409,'Mission operator must match the survey area assignment')
    if not db.execute(text('''SELECT ST_Covers(boundary_geometry,
        ST_SetSRID(ST_GeomFromGeoJSON(:g),4326)) FROM survey_area_assignments WHERE id=:id'''),
        {'id':parent.id,'g':json.dumps(mission.boundary)}).scalar_one():
        raise HTTPException(422,'The entire mission boundary must be inside its assigned survey area')


def progress(db, area_id):
    result=db.execute(text('''WITH p AS (
        SELECT boundary_geometry g FROM survey_area_assignments WHERE id=:id),
      evidence AS (SELECT p.g planned,
        ST_Intersection(p.g,COALESCE((SELECT ST_UnaryUnion(ST_Collect(s.coverage_geometry))
          FROM survey_attempts s JOIN missions m ON m.id=s.mission_id
          WHERE m.assignment_id=:id AND s.status='COMPLETED' AND s.algorithm_version=:version AND s.simulated),
          ST_GeomFromText('POLYGON EMPTY',4326))) completed,
        ST_Intersection(p.g,COALESCE((SELECT ST_UnaryUnion(ST_Collect(o.footprint))
          FROM observations o JOIN missions m ON m.id=o.mission_id
          WHERE m.assignment_id=:id AND m.state=ANY(:active)),ST_GeomFromText('POLYGON EMPTY',4326))) live
        FROM p), layers AS (
        SELECT planned,completed,ST_Difference(live,completed) live,
          ST_Difference(planned,ST_Union(completed,live)) remaining FROM evidence)
      SELECT ST_AsGeoJSON(completed),ST_AsGeoJSON(live),ST_AsGeoJSON(remaining),
        ST_Area(planned::geography),ST_Area(completed::geography),ST_Area(live::geography),
        ST_Area(remaining::geography),ST_CoveredBy(planned,completed) FROM layers'''),
        {'id':area_id,'version':COVERAGE_VERSION,'active':list(ACTIVE)}).one()
    total,completed,live,remaining=map(float,result[3:7])
    full=bool(result[7])
    percent=100.0 if full else min(99.99,round(100*completed/total,2))
    return {'completed_geometry':json.loads(result[0]),'in_progress_geometry':json.loads(result[1]),
        'remaining_geometry':json.loads(result[2]),'total_m2':total,'completed_m2':completed,
        'in_progress_m2':live,'remaining_m2':remaining,'coverage_percent':percent,'fully_surveyed':full,
        'algorithm_version':COVERAGE_VERSION,'simulated':True,'notice':NOTICE}


def record(db, row):
    return {column.name:getattr(row,column.name) for column in row.__table__.columns}


def summary(db, row):
    coverage=progress(db,row.id)
    started=db.scalar(select(Mission.id).where(Mission.assignment_id==row.id,Mission.started_at.is_not(None)).limit(1))
    status='COMPLETED' if coverage['fully_surveyed'] else 'IN_PROGRESS' if started else 'ASSIGNED'
    operator=db.get(User,row.operator_id)
    return {**record(db,row),'operator_username':operator.username,'status':status,'progress':coverage,
        'overdue':bool(row.deadline and row.deadline.replace(tzinfo=UTC)<datetime.now(UTC) and status!='COMPLETED')}


def history_event(db, row, actor, kind):
    db.add(SurveyAreaEvent(id=str(uuid4()),assignment_id=row.id,actor_id=actor.id,kind=kind,
                          snapshot=jsonable_encoder(record(db,row)),created_at=datetime.now(UTC)))
    audit(db,actor.id,'survey_area_'+kind)


def valid_operator(db, operator_id):
    person=db.get(User,operator_id)
    if not person or not person.active or person.role!='mission_operator':
        raise HTTPException(422,'Select an active Mission Operator')


@router.get('')
def list_areas(db: Db,user: Identity,offset: int=0,limit: int=50):
    permission(user)
    if offset<0 or not 1<=limit<=100:
        raise HTTPException(422,'Invalid pagination')
    query=select(SurveyAreaAssignment).order_by(SurveyAreaAssignment.created_at.desc(),SurveyAreaAssignment.id)
    if user.role!='supervisor':
        query=query.where(SurveyAreaAssignment.operator_id==user.id)
    return [summary(db,row) for row in db.scalars(query.offset(offset).limit(limit))]


@router.post('',status_code=201)
def create_area(body: AreaInput,db: Db,user: Identity):
    permission(user,True)
    valid_operator(db,body.operator_id)
    geometry=polygon(body)
    validate_area(db,geometry)
    at=datetime.now(UTC)
    row=SurveyAreaAssignment(id=str(uuid4()),name=body.name,description=body.description,
        operator_id=body.operator_id,created_by=user.id,boundary=geometry,deadline=body.deadline,
        revision=1,created_at=at,updated_at=at)
    db.add(row)
    db.flush()
    history_event(db,row,user,'created')
    db.commit()
    return summary(db,row)


@router.put('/{area_id}')
def update_area(area_id: str,body: AreaUpdate,db: Db,user: Identity):
    permission(user,True)
    row=get_area(db,area_id,user,lock=True)
    if row.revision!=body.revision:
        raise HTTPException(409,'Assignment changed. Reload before editing.')
    valid_operator(db,body.operator_id)
    geometry=polygon(body)
    validate_area(db,geometry)
    missions=db.scalars(select(Mission).where(Mission.assignment_id==row.id).with_for_update()).all()
    if any(m.state in ACTIVE for m in missions):
        raise HTTPException(409,'Wait for active missions to finish before modifying this assignment')
    if db.execute(text('''SELECT EXISTS(SELECT 1 FROM missions WHERE assignment_id=:id AND
        NOT ST_Covers(ST_SetSRID(ST_GeomFromGeoJSON(:g),4326),planned_geometry))'''),
        {'id':row.id,'g':json.dumps(geometry)}).scalar_one():
        raise HTTPException(422,'Updated area must still contain every linked mission boundary; survey history is preserved')
    reassign=row.operator_id!=body.operator_id
    row.name, row.description, row.operator_id, row.boundary, row.deadline = body.name,body.description,body.operator_id,geometry,body.deadline
    row.revision+=1
    row.updated_at=datetime.now(UTC)
    if reassign:
        for mission in missions:
            if mission.state in {'DRAFT','READY'}:
                mission.operator_id=row.operator_id
                mission.state='DRAFT'
                db.add(MissionEvent(id=str(uuid4()),mission_id=mission.id,kind='assigned',
                    detail='Survey area reassigned by Supervisor; draft requires revalidation',created_at=row.updated_at))
    history_event(db,row,user,'reassigned' if reassign else 'updated')
    db.commit()
    return summary(db,row)


@router.get('/{area_id}')
def area_detail(area_id: str,db: Db,user: Identity,offset: int=0,limit: int=100):
    row=get_area(db,area_id,user)
    if offset<0 or not 1<=limit<=100:
        raise HTTPException(422,'Invalid pagination')
    missions=db.scalars(select(Mission).where(Mission.assignment_id==row.id).order_by(Mission.created_at.desc()).offset(offset).limit(limit)).all()
    attempts=db.scalars(select(SurveyAttempt).join(Mission,Mission.id==SurveyAttempt.mission_id).where(Mission.assignment_id==row.id)
                       .order_by(SurveyAttempt.finished_at.desc()).offset(offset).limit(limit)).all()
    events=db.scalars(select(SurveyAreaEvent).where(SurveyAreaEvent.assignment_id==row.id)
                     .order_by(SurveyAreaEvent.created_at.desc()).offset(offset).limit(limit)).all()
    return {**summary(db,row),'missions':[record(db,m) for m in missions],
        'surveys':[record(db,s) for s in attempts],'history':[record(db,e) for e in events]}
