"""Mission workflows. All flight effects are confined to the isolated SITL service."""
import asyncio
import csv
from datetime import UTC, datetime
import io
import json
import math
import threading
import time
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect
from sqlalchemy import select, text
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB

from .coverage import calculate, store_position
from .db import SessionLocal
from .models import AuthSession, User
from .operations_models import AnalystReview, Detection, Mission, MissionEvent, Observation, SurveyAttempt, VehicleLease
from .operations_schemas import Assignment, MissionPlan, ReviewInput, StopRequest
from .runtime import runtime
from .survey_areas import ACTIVE, check_mission_area, get_area
from .security import effective_permissions, Db, ROLE_PERMISSIONS, audit, current_user, digest, require
from terraguavd_detection.processing import VERSION, fixture, score, valid_footprint, mock_classification

router = APIRouter(prefix='/api/v1')
Identity = Annotated[User, Depends(current_user)]
TERMINAL = {'COMPLETED','CANCELLED','INTERRUPTED','FAILED'}
NOTICE = 'Simulation only. Potential targets are unverified. Surveyed does not mean cleared or safe.'


def now():
    return datetime.now(UTC)


def identifier():
    return str(uuid4())


def event(db, mission, kind, detail):
    db.add(MissionEvent(id=identifier(), mission_id=mission.id, kind=kind, detail=detail, created_at=now()))


def serialize(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def allowed(user, mission):
    permissions=effective_permissions(user)
    if not {'missions:read','missions:assigned:read'} & permissions:
        return False
    return (user.role in {'administrator','supervisor','detection_analyst'} or
            user.role == 'mission_operator' and mission.operator_id == user.id or
            user.role == 'field_personnel' and user.id in mission.field_ids)


def get_mission(db, mission_id, user=None, lock=False):
    query = select(Mission).where(Mission.id == mission_id)
    mission = db.scalar(query)
    if mission is None or user and not allowed(user, mission):
        raise HTTPException(404, 'Mission not found')
    if lock:
        # Consistent parent-before-child order also serializes Supervisor edits.
        if mission.assignment_id:
            get_area(db,mission.assignment_id,lock=True)
        mission=db.scalar(query.with_for_update().execution_options(populate_existing=True))
        if user and not allowed(user,mission):
            raise HTTPException(404,'Mission not found')
    return mission


def operator(user, mission, permission='missions:execute'):
    if permission not in effective_permissions(user) or mission.operator_id != user.id:
        raise HTTPException(403, 'Only the assigned Mission Operator may command this simulation')


def scoped(query, db, user):
    if user.role == 'mission_operator':
        query = query.where(Mission.operator_id == user.id)
    elif user.role == 'field_personnel' and db.bind.dialect.name == 'postgresql':
        query = query.where(cast(Mission.field_ids, JSONB).contains([user.id]))
    return query


def visible_missions(db, user):
    query = scoped(select(Mission).order_by(Mission.created_at.desc()),db,user)
    rows = db.scalars(query.limit(500)).all()
    return [row for row in rows if allowed(user, row)]


def validate_geometry(db, mission):
    polygon = json.dumps(mission.boundary)
    route = json.dumps({'type':'LineString','coordinates':mission.waypoints})
    check = db.execute(text('''WITH g AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:polygon),4326) p,
        ST_SetSRID(ST_GeomFromGeoJSON(:route),4326) r)
        SELECT ST_IsValid(p), ST_Area(p::geography), ST_Covers(p,r) FROM g'''),
        {'polygon':polygon,'route':route}).one()
    if not check[0] or check[1] <= 0 or not check[2]:
        raise HTTPException(422, 'Use a valid nonzero-area polygon containing the entire route')
    check_mission_area(db,mission)
    db.execute(text('UPDATE missions SET planned_geometry=ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326) WHERE id=:id'),
               {'geometry':polygon,'id':mission.id})


def validate_fields(db, field_ids):
    for field_id in field_ids:
        person = db.get(User, field_id)
        if person is None or not person.active or person.role != 'field_personnel':
            raise HTTPException(422, 'Assign active Field Personnel accounts only')


def transition(db, mission, state, detail):
    mission.state = state
    event(db, mission, state.lower(), detail)


def finish(db, mission, state, error=None):
    if mission.state in TERMINAL:
        return
    mission.finished_at = now()
    mission.error = error
    transition(db, mission, state, error or f'Simulated mission {state.lower()}')
    if mission.started_at and not db.scalar(select(SurveyAttempt).where(SurveyAttempt.mission_id == mission.id)):
        coverage = calculate(db, mission.id)
        db.add(SurveyAttempt(id=identifier(), mission_id=mission.id, area_id=mission.area_id, uav_id=mission.uav_id,
            status=state, coverage_percent=coverage['coverage_percent'], geometry=coverage['geometry'],
            algorithm_version=coverage['algorithm_version'], simulated=True,
            started_at=mission.started_at, finished_at=mission.finished_at))
    lease = db.get(VehicleLease, 'sitl-01')
    if lease and lease.mission_id == mission.id:
        lease.mission_id = None
    db.commit()


def run_mission(mission_id):
    """Single-worker prototype runner; the database vehicle lease prevents duplicate starts."""
    try:
        with SessionLocal() as db:
            mission = get_mission(db, mission_id,lock=True)
            if mission.state!='STARTING_SIMULATION':
                return
            runtime.call('/runtime/start', {})
            transition(db, mission, 'WAITING_FOR_VEHICLE', 'Waiting for actual SITL MAVLink position and heartbeat')
            db.commit()
        deadline = time.monotonic()+120
        while True:
            with SessionLocal() as db:
                if get_mission(db,mission_id).state!='WAITING_FOR_VEHICLE':
                    return
            snapshot = runtime.call('/status')
            if snapshot['ready']:
                break
            if time.monotonic()>deadline:
                raise RuntimeError('PX4/Gazebo did not become ready within 120 seconds')
            time.sleep(1)
        with SessionLocal() as db:
            mission = get_mission(db, mission_id,lock=True)
            if mission.state!='WAITING_FOR_VEHICLE':
                return
            transition(db, mission, 'UPLOADING', 'Uploading validated simulator-only mission')
            plan = {'waypoints':mission.waypoints,'altitude_m':mission.altitude_m,'speed_m_s':mission.speed_m_s}
            db.commit()
        with SessionLocal() as db:
            mission = get_mission(db, mission_id,lock=True)
            if mission.state!='UPLOADING':
                return
            runtime.call('/mission/upload', plan)
            # Lock prevents recovery or another command from reviving an interrupted attempt.
            runtime.call('/mission/start', {})
            transition(db, mission, 'EXECUTING', 'PX4 accepted explicit mission start')
            db.commit()
        deadline = time.monotonic()+1200
        saw_armed = False
        sequence = 0
        while time.monotonic()<deadline:
            snapshot = runtime.call('/status')
            if not snapshot['ready']:
                raise RuntimeError('SITL telemetry connection lost')
            saw_armed = saw_armed or snapshot['armed']
            with SessionLocal() as db:
                mission = get_mission(db, mission_id, lock=True)
                if mission.state not in ACTIVE:
                    return
                sensor = fixture(sequence) if mission.synthetic_sensors and mission.state == 'EXECUTING' else None
                observation = Observation(id=identifier(), mission_id=mission.id, sequence=sequence,
                    longitude=snapshot['longitude'], latitude=snapshot['latitude'], altitude_m=snapshot['altitude_m'],
                    speed_m_s=snapshot['speed_m_s'], battery_percent=snapshot['battery_percent'], source='px4-gazebo-sitl',
                    sensor=sensor, created_at=now())
                db.add(observation)
                db.flush()
                store_position(db, observation)
                confidence = score(sensor) if valid_footprint(sensor,observation.altitude_m,observation.speed_m_s) else None
                if confidence is not None:
                    # Suppress repeated points within the experimental sensor footprint.
                    nearest = db.execute(text('''SELECT count(*) FROM detections WHERE mission_id=:id AND
                        ST_DWithin(ST_SetSRID(ST_MakePoint(longitude,latitude),4326)::geography,
                        ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography,4)'''),
                        {'id':mission.id,'lon':observation.longitude,'lat':observation.latitude}).scalar_one()
                    if not nearest:
                        db.add(Detection(id=identifier(),mission_id=mission.id,observation_id=observation.id,
                            longitude=observation.longitude,latitude=observation.latitude,confidence=confidence,
                            classification=mock_classification(sensor),processing_version=VERSION,simulated=True,created_at=now()))
                        event(db,mission,'potential_target','Synthetic feature baseline flagged an unverified potential target')
                db.commit()
                if saw_armed and not snapshot['armed']:
                    db.refresh(mission,with_for_update=True)
                    state = 'CANCELLED' if mission.state == 'CANCELLING' else 'COMPLETED' if snapshot['reached'] >= snapshot['total']-2 else 'INTERRUPTED'
                    finish(db, mission, state)
                    return
            sequence += 1
            time.sleep(1)
        raise RuntimeError('Simulator mission exceeded the 20 minute prototype limit')
    except Exception as exc:
        # Stop the isolated simulator on failures so no orphaned simulated flight remains.
        try:
            runtime.call('/runtime/stop', {})
        except Exception:
            pass
        with SessionLocal() as db:
            mission = get_mission(db, mission_id, lock=True)
            if mission.state not in TERMINAL:
                finish(db, mission, 'FAILED', str(exc)[:1000])


def schedule(mission_id):
    threading.Thread(target=run_mission, args=(mission_id,), daemon=True).start()


def recover():
    """Called on API startup; never resume or arm automatically after a restart."""
    with SessionLocal() as db:
        active = db.scalars(select(Mission.id).where(Mission.state.in_(ACTIVE))).all()
        if not active:
            return
        runtime.call('/runtime/stop', {})
        for mission_id in active:
            mission=get_mission(db,mission_id,lock=True)
            if mission.state in ACTIVE:
                finish(db, mission, 'INTERRUPTED', 'Backend lifecycle interrupted this attempt; simulator stopped; explicit new mission required')


@router.get('/missions')
def list_missions(db: Db, user: Identity, offset: int = 0, limit: int = 50):
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(422, 'Invalid pagination')
    rows=db.scalars(scoped(select(Mission).order_by(Mission.created_at.desc()),db,user).offset(offset).limit(limit))
    return [serialize(row) for row in rows if allowed(user,row)]


@router.get('/mission-users')
def mission_users(db: Db, user: Identity):
    if user.role not in {'mission_operator','supervisor','administrator'}:
        raise HTTPException(403, 'Permission denied')
    rows = db.scalars(select(User).where(User.active.is_(True),User.role.in_(['mission_operator','field_personnel'])))
    return [{'id':row.id,'username':row.username,'role':row.role} for row in rows if user.role != 'mission_operator' or row.role == 'field_personnel' or row.id == user.id]


@router.post('/missions', status_code=201)
def create_mission(body: MissionPlan, db: Db, user: Identity):
    if 'missions:plan' not in effective_permissions(user):
        raise HTTPException(403,'Mission planning permission required')
    get_area(db,body.assignment_id,user,lock=True)
    if body.boundary[0] != body.boundary[-1]:
        raise HTTPException(422, 'Close the polygon by repeating its first coordinate')
    validate_fields(db,body.field_ids)
    mission = Mission(id=identifier(),name=body.name.strip(),area_id=body.area_id,assignment_id=body.assignment_id,operator_id=user.id,
        field_ids=body.field_ids,boundary={'type':'Polygon','coordinates':[body.boundary]},
        waypoints=body.waypoints,altitude_m=body.altitude_m,speed_m_s=body.speed_m_s,
        synthetic_sensors=body.synthetic_sensors,created_at=now())
    if not mission.name:
        raise HTTPException(422, 'Mission name is required')
    db.add(mission)
    db.flush()
    validate_geometry(db,mission)
    event(db,mission,'created','Draft simulation plan created; no flight command issued')
    audit(db,user.id,'mission_created')
    db.commit()
    return serialize(mission)


@router.get('/missions/{mission_id}/scene')
def gazebo_scene(mission_id: str, db: Db, user: Identity):
    mission=get_mission(db,mission_id,user)
    lease=db.scalar(select(VehicleLease).where(VehicleLease.id=='sitl-01').with_for_update())
    # An old/assigned mission must never expose another mission's live vehicle.
    if mission.state not in ACTIVE or not lease or lease.mission_id!=mission.id:
        return {'runtime':'px4-gazebo','simulated':True,'live':False,'pose':None,
                'notice':'Live Gazebo view is available only for this active mission.'}
    try:
        return runtime.call('/scene')
    except RuntimeError as exc:
        raise HTTPException(503,'Gazebo scene is unavailable') from exc


@router.get('/missions/{mission_id}')
def detail(mission_id: str, db: Db, user: Identity):
    mission=get_mission(db,mission_id,user)
    observations=db.scalars(select(Observation).where(Observation.mission_id==mission_id).order_by(Observation.sequence).limit(1500)).all()
    targets=db.scalars(select(Detection).where(Detection.mission_id==mission_id).order_by(Detection.created_at)).all()
    reviews=db.scalars(select(AnalystReview).where(AnalystReview.detection_id.in_([row.id for row in targets]))).all() if targets else []
    events=db.scalars(select(MissionEvent).where(MissionEvent.mission_id==mission_id).order_by(MissionEvent.created_at.desc()).limit(100)).all()
    return {'mission':serialize(mission),'observations':[serialize(row) for row in observations],
            'detections':[serialize(row) for row in targets],'reviews':[serialize(row) for row in reviews],
            'events':[serialize(row) for row in events],'coverage':calculate(db,mission_id),'notice':NOTICE}


@router.post('/missions/{mission_id}/assign')
def assign(mission_id: str, body: Assignment, db: Db, user: Identity):
    if 'missions:assign' not in effective_permissions(user):
        raise HTTPException(403,'Supervisor permission required')
    mission=get_mission(db,mission_id,user,lock=True)
    if mission.state not in {'DRAFT','READY'}:
        raise HTTPException(409,'Assignments cannot change after a mission starts')
    if mission.assignment_id and body.operator_id!=get_area(db,mission.assignment_id).operator_id:
        raise HTTPException(409,'Reassign the parent survey area instead of an individual linked mission')
    person=db.get(User,body.operator_id)
    if not person or not person.active or person.role!='mission_operator':
        raise HTTPException(422,'Select an active Mission Operator')
    validate_fields(db,body.field_ids)
    mission.operator_id=person.id
    mission.field_ids=body.field_ids
    event(db,mission,'assigned','Supervisor updated mission assignments')
    audit(db,user.id,'mission_assigned')
    db.commit()
    return serialize(mission)


@router.post('/missions/{mission_id}/validate')
def validate(mission_id: str, db: Db, user: Identity):
    mission=get_mission(db,mission_id,user,lock=True)
    operator(user,mission,'missions:plan')
    if mission.state not in {'DRAFT','READY'}:
        raise HTTPException(409,'Only draft or ready plans can be validated')
    validate_geometry(db,mission)
    transition(db,mission,'READY','Geometry and simulation plan validated; no flight command issued')
    db.commit()
    return serialize(mission)


@router.post('/missions/{mission_id}/start', status_code=202)
def start(mission_id: str, db: Db, user: Identity):
    mission=get_mission(db,mission_id,user,lock=True)
    operator(user,mission)
    lease=db.scalar(select(VehicleLease).where(VehicleLease.id=='sitl-01').with_for_update())
    if not lease:
        raise HTTPException(503,'Run database migrations first')
    if mission.state in ACTIVE:
        return serialize(mission)  # Repeated explicit start is idempotent.
    if mission.state!='READY':
        raise HTTPException(409,'Validate this draft plan before starting')
    if lease.mission_id:
        raise HTTPException(409,'The simulator is reserved by another active mission')
    validate_geometry(db,mission)
    lease.mission_id=mission.id
    mission.started_at=now()
    transition(db,mission,'STARTING_SIMULATION','Explicit assigned-operator start accepted')
    audit(db,user.id,'simulation_mission_start_requested')
    db.commit()
    schedule(mission.id)
    return serialize(mission)


@router.post('/missions/{mission_id}/{command}')
def command(mission_id: str, command: Literal['pause','resume','cancel'], db: Db, user: Identity):
    if command not in {'pause','resume','cancel'}:
        raise HTTPException(404,'Unknown command')
    mission=get_mission(db,mission_id,user,lock=True)
    operator(user,mission)
    permitted={'pause':{'EXECUTING'},'resume':{'PAUSED'},'cancel':{'EXECUTING','PAUSED'}}
    if mission.state not in permitted[command]:
        raise HTTPException(409,f'Cannot {command} a mission in {mission.state}')
    try:
        runtime.call(f'/mission/{command}',{})
    except RuntimeError as exc:
        raise HTTPException(502,str(exc)) from exc
    transition(db,mission,{'pause':'PAUSED','resume':'EXECUTING','cancel':'CANCELLING'}[command],f'Assigned operator requested {command}')
    audit(db,user.id,f'simulation_mission_{command}')
    db.commit()
    return serialize(mission)


@router.post('/missions/{mission_id}/stop-request')
def request_stop(mission_id: str, body: StopRequest, db: Db, user: Identity):
    mission=get_mission(db,mission_id,user,lock=True)
    if 'stop:request' not in effective_permissions(user) or mission.state not in ACTIVE:
        raise HTTPException(403,'Assigned Field Personnel on active missions only')
    event(db,mission,'stop_requested',body.reason)
    audit(db,user.id,'field_stop_requested')
    db.commit()
    return {'status':'requested','notice':'Operator notified. No autopilot command was sent.'}


@router.get('/missions/{mission_id}/detections')
def mission_detections(mission_id: str, db: Db, user: Identity):
    get_mission(db,mission_id,user)
    return [serialize(row) for row in db.scalars(select(Detection).where(Detection.mission_id==mission_id))]


@router.post('/detections/{detection_id}/reviews', status_code=201)
def review(detection_id: str, body: ReviewInput, db: Db, user: Identity):
    if 'detections:review' not in effective_permissions(user):
        raise HTTPException(403,'Detection Analyst permission required')
    target=db.get(Detection,detection_id)
    if target is None:
        raise HTTPException(404,'Potential target not found')
    get_mission(db,target.mission_id,user)
    record=AnalystReview(id=identifier(),detection_id=target.id,analyst_id=user.id,
        assessment=body.assessment,notes=body.notes,created_at=now())
    db.add(record)
    audit(db,user.id,'analyst_assessment_added')
    db.commit()
    return serialize(record)


@router.get('/missions/{mission_id}/coverage')
def coverage(mission_id: str, db: Db, user: Identity):
    get_mission(db,mission_id,user)
    return calculate(db,mission_id)


@router.get('/areas/{area_id}/surveys')
def area_history(area_id: str, db: Db, user: Identity, offset: int=0, limit: int=100):
    if offset<0 or not 1<=limit<=100:
        raise HTTPException(422,'Invalid history pagination')
    query=scoped(select(SurveyAttempt).join(Mission,Mission.id==SurveyAttempt.mission_id).where(SurveyAttempt.area_id==area_id),db,user)
    rows=db.scalars(query.order_by(SurveyAttempt.finished_at.desc()).offset(offset).limit(limit))
    return [serialize(row) for row in rows if allowed(user,db.get(Mission,row.mission_id))]


@router.get('/alerts')
def alert_list(db: Db, user: Identity):
    ids=[row.id for row in visible_missions(db,user)]
    return [serialize(row) for row in db.scalars(select(MissionEvent).where(MissionEvent.mission_id.in_(ids),
        MissionEvent.kind.in_(['potential_target','stop_requested','failed','interrupted'])).order_by(MissionEvent.created_at.desc()).limit(100))]


@router.get('/missions/{mission_id}/report')
def report(mission_id: str, db: Db, user: Identity, format: str='json'):
    get_mission(db,mission_id,user)
    if 'reports:read' not in effective_permissions(user):
        raise HTTPException(403,'Report export permission required')
    result=detail(mission_id,db,user)
    if format=='json':
        return {'generated_at':now(),**result}
    if format!='csv':
        raise HTTPException(422,'Use json or csv')
    output=io.StringIO()
    writer=csv.writer(output)
    writer.writerow(['TerraGuavd SIMULATION REPORT',NOTICE])
    writer.writerow(['mission_id','state','area_id','uav_id','synthetic_sensor_fixture','coverage_percent','coverage_algorithm'])
    mission=result['mission']
    writer.writerow([mission['id'],mission['state'],mission['area_id'],mission['uav_id'],mission['synthetic_sensors'],
                     result['coverage']['coverage_percent'],result['coverage']['algorithm_version']])
    writer.writerow(['potential_target_id','latitude','longitude','confidence','classification','processing_version','simulated'])
    for target in result['detections']:
        writer.writerow([target[key] for key in ['id','latitude','longitude','confidence','classification','processing_version','simulated']])
    return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="terraguavd-{mission_id}.csv"','Cache-Control':'no-store'})


@router.get('/simulation/status')
def runtime_status(user: Annotated[User,Depends(require('system:read'))]):
    try:
        return runtime.call('/status')
    except RuntimeError:
        return {'runtime':'px4-gazebo','simulated':True,'ready':False,'running':False,'notice':'Simulator service unavailable'}


def socket_snapshot(token,mission_id):
    with SessionLocal() as db:
        session=db.get(AuthSession,digest(token))
        user=db.get(User,session.user_id) if session and session.expires_at.replace(tzinfo=UTC)>now() else None
        if not user or not user.active:
            raise HTTPException(401,'Session expired')
        return detail(mission_id,db,user)


@router.websocket('/ws/missions/{mission_id}')
async def mission_socket(websocket: WebSocket, mission_id: str):
    await websocket.accept()
    try:
        credentials=await asyncio.wait_for(websocket.receive_json(),timeout=5)
        token=credentials.get('token','') if isinstance(credentials,dict) else ''
        if not isinstance(token,str) or not 1<=len(token)<=256:
            await websocket.close(code=4401)
            return
        while True:
            try:
                result=await asyncio.to_thread(socket_snapshot,token,mission_id)
            except HTTPException as exc:
                await websocket.close(code=4401 if exc.status_code==401 else 4403)
                return
            from fastapi.encoders import jsonable_encoder
            await websocket.send_json(jsonable_encoder(result))
            await asyncio.sleep(2)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        return
