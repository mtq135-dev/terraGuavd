"""Server-side approval for outside-assignment SITL plans."""

from datetime import UTC, datetime
import hashlib
import json
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text

from .models import User
from .operations_models import Mission, MissionApprovalRequest, MissionEvent, SurveyAreaAssignment
from .operations_schemas import ApprovalContext, ApprovalDecision, ApprovalInboxItem, ApprovalPreview, ApprovalPreviewResult, ApprovalReason
from .security import Db, audit, current_user, effective_permissions
from .survey_areas import get_area

router = APIRouter(prefix='/api/v1', tags=['Mission approvals'])
Identity = Annotated[User, Depends(current_user)]
EDITABLE = {'DRAFT', 'READY'}
OPEN_REQUEST = {'Pending', 'Approved'}
WARNING = 'This mission is outside your assigned survey area and requires supervisor approval.'
CONFIGURATION_FIELDS = (
    'id', 'name', 'area_id', 'assignment_id', 'operator_id', 'field_ids',
    'boundary', 'waypoints', 'altitude_m', 'speed_m_s', 'runtime', 'uav_id',
    'synthetic_sensors', 'plan_revision',
)


def record(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def configuration(mission, parent):
    return {**{key: getattr(mission, key) for key in CONFIGURATION_FIELDS},
            'assignment_revision': parent.revision, 'responsible_supervisor_id': parent.created_by}


def fingerprint(mission, parent):
    data = json.dumps(configuration(mission, parent), sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def spatial_context(db, boundary, parent):
    inside, outside, area = db.execute(text('''WITH g AS (
        SELECT ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) mission,
               boundary_geometry assigned FROM survey_area_assignments WHERE id=:id),
        compared AS (SELECT ST_Covers(assigned,mission) inside,
                            ST_Difference(mission,assigned) outside FROM g)
        SELECT inside, ST_AsGeoJSON(outside,15), ST_Area(outside::geography) FROM compared'''),
        {'g': json.dumps(boundary), 'id': parent.id}).one()
    return {'required': not inside, 'outside_geometry': json.loads(outside), 'outside_m2': float(area)}


def responsible_supervisor(db, parent):
    person = db.get(User, parent.created_by, populate_existing=True)
    if person and person.active and person.role == 'supervisor' and 'missions:approve' in effective_permissions(person):
        return person
    return None


def latest_request(db, mission_id, lock=False):
    query = select(MissionApprovalRequest).where(MissionApprovalRequest.mission_id == mission_id).order_by(
        MissionApprovalRequest.requested_at.desc(), MissionApprovalRequest.id.desc()).limit(1)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return db.scalar(query)


def matches(db, request, mission, parent):
    return bool(request and parent and request.assignment_id == parent.id
                and parent.operator_id == mission.operator_id == request.operator_id
                and request.mission_id == mission.id and request.supervisor_id == parent.created_by
                and request.assignment_revision == parent.revision
                and request.configuration_hash == fingerprint(mission, parent)
                and responsible_supervisor(db, parent))


def assignment_snapshot(db, parent):
    supervisor = db.get(User, parent.created_by)
    return {'id': parent.id, 'name': parent.name, 'boundary': parent.boundary, 'revision': parent.revision,
            'supervisor_id': parent.created_by, 'supervisor_username': supervisor.username if supervisor else None}


def visible_to(user, mission, parent):
    permissions = effective_permissions(user)
    return (user.role == 'mission_operator' and 'missions:read' in permissions and mission.operator_id == user.id
            or user.role == 'supervisor' and 'missions:approve' in permissions and parent and parent.created_by == user.id)


def context(db, mission, parent):
    empty = {'required': False, 'status': 'Not Required', 'can_execute': True,
             'outside_geometry': {'type': 'GeometryCollection', 'geometries': []}, 'outside_m2': 0,
             'assignment': None, 'request': None, 'history': [], 'warning': None}
    if parent is None:
        return empty
    spatial = spatial_context(db, mission.boundary, parent)
    history = list(db.scalars(select(MissionApprovalRequest).where(MissionApprovalRequest.mission_id == mission.id,
                                                                  MissionApprovalRequest.operator_id == mission.operator_id)
                              .order_by(MissionApprovalRequest.requested_at.desc(), MissionApprovalRequest.id.desc()).limit(20)))
    latest = history[0] if history else None
    current = matches(db, latest, mission, parent) if latest and latest.status in OPEN_REQUEST else False
    status = latest.status if latest else None
    if mission.state in EDITABLE and latest and latest.status in OPEN_REQUEST and not current:
        status = 'Invalidated'
    return {**spatial, 'status': status if spatial['required'] else 'Not Required',
            'can_execute': parent.operator_id == mission.operator_id and (not spatial['required'] or current and status == 'Approved'),
            'warning': WARNING if spatial['required'] else None, 'assignment': assignment_snapshot(db, parent),
            'request': record(latest) if latest else None, 'history': [record(item) for item in history]}


def enforce(db, mission, parent):
    """Call with parent and mission locked, before a lease or simulator action."""
    if parent is None or not spatial_context(db, mission.boundary, parent)['required']:
        return
    request = latest_request(db, mission.id, lock=True)
    if request is None or request.status != 'Approved' or not matches(db, request, mission, parent):
        raise HTTPException(422, WARNING)


def notify(db, mission, actor, kind, detail):
    db.add(MissionEvent(id=str(uuid4()), mission_id=mission.id, kind=kind, detail=detail,
                        actor_id=actor.id, actor_username=actor.username, priority='info', created_at=datetime.now(UTC)))
    audit(db, actor.id, f'{kind}:{mission.id}')


def invalidate(db, mission, actor, reason):
    requests = list(db.scalars(select(MissionApprovalRequest).where(
        MissionApprovalRequest.mission_id == mission.id, MissionApprovalRequest.status.in_(OPEN_REQUEST))
        .order_by(MissionApprovalRequest.id).with_for_update().execution_options(populate_existing=True)))
    for request in requests:
        request.status = 'Invalidated'
    if requests:
        notify(db, mission, actor, 'approval_invalidated', reason)
    return bool(requests)


@router.post('/mission-approval-preview', response_model=ApprovalPreviewResult)
def preview(body: ApprovalPreview, db: Db, user: Identity):
    if user.role != 'mission_operator' or 'missions:plan' not in effective_permissions(user):
        raise HTTPException(403, 'Mission planning permission required')
    parent = get_area(db, body.assignment_id, user)
    boundary = {'type': 'Polygon', 'coordinates': [body.boundary]}
    valid = db.scalar(text('''WITH g AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) p)
        SELECT CASE WHEN ST_IsValid(p) THEN ST_Area(p::geography)>0 ELSE FALSE END FROM g'''),
        {'g': json.dumps(boundary)})
    if not valid:
        raise HTTPException(422, 'Use a valid nonzero-area polygon')
    return {**spatial_context(db, boundary, parent), 'assigned_boundary': parent.boundary}


@router.get('/missions/{mission_id}/approval', response_model=ApprovalContext)
def mission_approval(mission_id: str, db: Db, user: Identity):
    from .operations import get_mission

    mission = get_mission(db, mission_id, user)
    parent = get_area(db, mission.assignment_id) if mission.assignment_id else None
    if not visible_to(user, mission, parent):
        raise HTTPException(404, 'Mission approval not found')
    return context(db, mission, parent)


@router.post('/missions/{mission_id}/approval-requests', response_model=ApprovalContext)
def request_approval(mission_id: str, body: ApprovalReason, db: Db, user: Identity):
    from .operations import get_mission, operator, validate_geometry

    mission = get_mission(db, mission_id, user, lock=True)
    operator(user, mission, 'missions:plan')
    if mission.state not in EDITABLE or not mission.assignment_id:
        raise HTTPException(409, 'Only unstarted assigned missions may request approval')
    parent = validate_geometry(db, mission, require_approval=False)
    spatial = spatial_context(db, mission.boundary, parent)
    if not spatial['required']:
        raise HTTPException(409, 'This mission is within its assignment; approval is not required')
    supervisor = responsible_supervisor(db, parent)
    if not supervisor:
        raise HTTPException(409, 'The assignment creator must be an active authorized Supervisor')
    current = latest_request(db, mission.id, lock=True)
    if current and current.status in OPEN_REQUEST and matches(db, current, mission, parent):
        return context(db, mission, parent)
    invalidate(db, mission, user, 'A revised approval request superseded the previous request')
    request = MissionApprovalRequest(id=str(uuid4()), mission_id=mission.id, assignment_id=parent.id,
        operator_id=user.id, supervisor_id=supervisor.id, assignment_revision=parent.revision,
        configuration_hash=fingerprint(mission, parent), reason=body.reason, status='Pending', requested_at=datetime.now(UTC),
        snapshot={'configuration': configuration(mission, parent), 'assignment': assignment_snapshot(db, parent),
                  'outside_geometry': spatial['outside_geometry'], 'outside_m2': spatial['outside_m2']})
    db.add(request)
    mission.state = 'DRAFT'
    notify(db, mission, user, 'approval_requested', f'Boundary approval requested from {supervisor.username}')
    db.commit()
    return context(db, mission, parent)


@router.get('/mission-approvals', response_model=list[ApprovalInboxItem])
def list_requests(db: Db, user: Identity, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    permissions = effective_permissions(user)
    if user.role == 'supervisor' and 'missions:approve' in permissions:
        scope = MissionApprovalRequest.supervisor_id == user.id
    elif user.role == 'mission_operator' and 'missions:read' in permissions:
        scope = MissionApprovalRequest.operator_id == user.id
    else:
        raise HTTPException(403, 'Mission approval access denied')
    query = select(MissionApprovalRequest).where(scope).order_by(MissionApprovalRequest.requested_at.desc(),
        MissionApprovalRequest.id.desc()).offset(offset).limit(limit)
    result = []
    for request in db.scalars(query):
        mission = db.get(Mission, request.mission_id)
        parent = db.get(SurveyAreaAssignment, request.assignment_id)
        current = matches(db, request, mission, parent)
        status = ('Invalidated' if mission.state in EDITABLE and request.status in OPEN_REQUEST and not current
                  else request.status)
        person = db.get(User, request.operator_id)
        result.append({'request': record(request), 'status': status, 'current': current,
            'mission': {'id': mission.id, 'name': request.snapshot['configuration']['name']},
            'operator_username': person.username if person else None})
    return result


@router.post('/mission-approvals/{request_id}/decision', response_model=ApprovalContext)
def decide(request_id: str, body: ApprovalDecision, db: Db, user: Identity):
    from .operations import get_mission, validate_geometry

    if user.role != 'supervisor' or 'missions:approve' not in effective_permissions(user):
        raise HTTPException(403, 'Supervisor approval permission required')
    request = db.get(MissionApprovalRequest, request_id)
    if not request or request.supervisor_id != user.id or request.operator_id == user.id:
        raise HTTPException(404, 'Approval request not found')
    mission = get_mission(db, request.mission_id, lock=True)
    request = db.scalar(select(MissionApprovalRequest).where(MissionApprovalRequest.id == request_id)
                        .with_for_update().execution_options(populate_existing=True))
    if request.status != 'Pending' or mission.state not in EDITABLE:
        raise HTTPException(409, 'The request is no longer pending for the current mission configuration')
    parent = validate_geometry(db, mission, require_approval=False)
    if not matches(db, request, mission, parent) or not spatial_context(db, mission.boundary, parent)['required']:
        raise HTTPException(409, 'The request is no longer pending for the current mission configuration')
    reason = body.reason.strip()
    if body.decision == 'Rejected' and len(reason) < 3:
        raise HTTPException(422, 'A rejection reason of at least three characters is required')
    request.status, request.decision_reason = body.decision, reason or None
    request.decided_by, request.decided_at = user.id, datetime.now(UTC)
    notify(db, mission, user, f'approval_{body.decision.lower()}', f'Boundary exception {body.decision.lower()} by {user.username}')
    db.commit()
    return context(db, mission, parent)
