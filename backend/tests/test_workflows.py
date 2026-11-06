"""Integration and optional real PX4 E2E; use a disposable PostGIS database only."""
import os
import subprocess
import sys
import time
from uuid import uuid4
from datetime import UTC, datetime
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DBAPIError

from app import operations
from app.db import get_db
from app.main import app
from app.models import User
from app.operations_models import Mission, Observation, VehicleLease, SurveyAreaAssignment, SurveyAreaEvent, SurveyAttempt
from app.security import ROLE_PERMISSIONS, passwords
from app.coverage import store_position
from terraguavd_detection.processing import fixture, COVERAGE_VERSION

pytestmark=pytest.mark.skipif(not os.getenv('TEST_POSTGIS_URL'),reason='Disposable PostGIS database required')
PLAN={'name':'Integration survey','area_id':'integration-area','assignment_id':'workflow-area','boundary':[[8.5453,47.3976],[8.5459,47.3976],[8.5459,47.39794],[8.5453,47.39794],[8.5453,47.3976]],
      'waypoints':[[8.5454,47.3977],[8.5458,47.3977],[8.5458,47.39784],[8.5454,47.39784]],
      'altitude_m':5,'speed_m_s':2,'synthetic_sensors':True,'field_ids':['field_personnel']}


@pytest.fixture(scope='module')
def database():
    url=os.environ['TEST_POSTGIS_URL']
    env={**os.environ,'DATABASE_URL':url}
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True)
    engine=create_engine(url)
    factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as db:
        for role in [*ROLE_PERMISSIONS,'other_operator','other_field']:
            db.add(User(id=role,username=role,role={'other_operator':'mission_operator','other_field':'field_personnel'}.get(role,role),password_hash=passwords.hash('Only-for-test-password-123')))
        db.commit()
        db.add(SurveyAreaAssignment(id='workflow-area',name='Workflow parent area',description='Test only',operator_id='mission_operator',
            created_by='supervisor',boundary={'type':'Polygon','coordinates':[[[8.54,47.39],[8.55,47.39],[8.55,47.4],[8.54,47.4],[8.54,47.39]]]},
            created_at=datetime.now(UTC),updated_at=datetime.now(UTC)))
        db.commit()
    yield factory
    engine.dispose()
    subprocess.run([sys.executable,'-m','alembic','downgrade','base'],env=env,check=True)


@pytest.fixture
def operational_api(database,monkeypatch):
    def db_session():
        with database() as db:
            yield db
    app.dependency_overrides[get_db]=db_session
    monkeypatch.setattr(operations,'SessionLocal',database)
    with TestClient(app) as api:
        def headers(role):
            response=api.post('/api/v1/auth/login',json={'username':role,'password':'Only-for-test-password-123'})
            assert response.status_code==200
            return {'Authorization':'Bearer '+response.json()['access_token']}
        yield api,headers,database
    app.dependency_overrides.clear()


def create(api,headers,**changes):
    response=api.post('/api/v1/missions',headers=headers,json={**PLAN,**changes})
    assert response.status_code==201,response.text
    return response.json()['id']


def area_body(**changes):
    return {'name':'Assigned survey sector','description':'Divide into small missions','operator_id':'mission_operator',
            'boundary':PLAN['boundary'],'deadline':'2026-12-01T15:00:00+03:00',**changes}


def new_area(api,sup,**changes):
    response=api.post('/api/v1/survey-areas',headers=sup,json=area_body(**changes))
    assert response.status_code==201,response.text
    return response.json()


def test_survey_area_authorization_containment_revision_and_reassignment(operational_api,monkeypatch):
    api,headers,factory=operational_api
    sup,op,other=headers('supervisor'),headers('mission_operator'),headers('other_operator')
    assert api.post('/api/v1/survey-areas',json=area_body()).status_code==401
    for role in ['administrator','mission_operator','detection_analyst','field_personnel']:
        assert api.post('/api/v1/survey-areas',headers=headers(role),json=area_body()).status_code==403
    area=new_area(api,sup)
    aid=area['id']
    assert area['deadline'].startswith('2026-12-01T12:00:00')
    assert area['progress']['coverage_percent']==0 and area['status']=='ASSIGNED'
    assert api.get(f'/api/v1/survey-areas/{aid}',headers=other).status_code==404
    assert aid not in [a['id'] for a in api.get('/api/v1/survey-areas',headers=other).json()]
    assert api.get('/api/v1/survey-areas',headers=headers('field_personnel')).status_code==403
    assert api.put(f'/api/v1/survey-areas/{aid}',headers=op,json={**area_body(), 'revision':1}).status_code==403
    assert api.post('/api/v1/missions',headers=other,json={**PLAN,'assignment_id':aid}).status_code==404
    missing={**PLAN};missing.pop('assignment_id')
    assert api.post('/api/v1/missions',headers=op,json=missing).status_code==422
    outside=[[x+.001,y] for x,y in PLAN['boundary']]
    drafted = api.post('/api/v1/missions',headers=op,json={**PLAN,'assignment_id':aid,'boundary':outside,
        'waypoints':[[x+.001,y] for x,y in PLAN['waypoints']]})
    assert drafted.status_code==201, drafted.text
    assert drafted.json()['state']=='DRAFT' and drafted.json()['approval']['required']
    mid=create(api,op,assignment_id=aid)
    assert api.post(f'/api/v1/missions/{mid}/validate',headers=op).status_code==200
    assert api.post(f'/api/v1/missions/{mid}/assign',headers=sup,json={'operator_id':'other_operator'}).status_code==409
    # Both validation and start recheck parent containment, not just the form.
    with factory.begin() as db:
        mission=db.get(Mission,mid); mission.boundary={'type':'Polygon','coordinates':[outside]}
        mission.waypoints=[[x+.001,y] for x,y in PLAN['waypoints']]
    assert api.post(f'/api/v1/missions/{mid}/validate',headers=op).status_code==422
    queued=[];monkeypatch.setattr(operations,'schedule',queued.append)
    assert api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code==422
    assert queued==[]
    with factory.begin() as db:
        mission=db.get(Mission,mid);mission.boundary={'type':'Polygon','coordinates':[PLAN['boundary']]};mission.waypoints=PLAN['waypoints']
    update={**area_body(operator_id='other_operator',description='Reassigned sector'),'revision':1}
    response=api.put(f'/api/v1/survey-areas/{aid}',headers=sup,json=update)
    assert response.status_code==200,response.text
    assert api.put(f'/api/v1/survey-areas/{aid}',headers=sup,json=update).status_code==409
    assert api.get(f'/api/v1/survey-areas/{aid}',headers=op).status_code==404
    moved=api.get(f'/api/v1/missions/{mid}',headers=other).json()['mission']
    assert moved['operator_id']=='other_operator' and moved['state']=='DRAFT'
    assert api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code==404
    assert api.post(f'/api/v1/missions/{mid}/start',headers=other).status_code==409
    detail=api.get(f'/api/v1/survey-areas/{aid}',headers=sup).json()
    assert len(detail['history'])==2 and detail['history'][-1]['snapshot']['operator_id']=='mission_operator'
    shrink=[[8.5454,47.3977],[8.5457,47.3977],[8.5457,47.3978],[8.5454,47.3978],[8.5454,47.3977]]
    assert api.put(f'/api/v1/survey-areas/{aid}',headers=sup,json={**update,'revision':2,'boundary':shrink}).status_code==422
    assert api.post(f'/api/v1/missions/{mid}/validate',headers=other).status_code==200
    assert api.post(f'/api/v1/missions/{mid}/start',headers=other).status_code==202
    assert api.put(f'/api/v1/survey-areas/{aid}',headers=sup,json={**update,'revision':2}).status_code==409
    with factory() as db:
        operations.finish(db,db.get(Mission,mid),'FAILED','Intentional test cleanup')
    with pytest.raises(DBAPIError,match='append-only'):
        with factory.begin() as db:
            db.execute(text('DELETE FROM survey_area_events WHERE assignment_id=:id'),{'id':aid})


def test_outside_mission_preview_decisions_revision_and_explicit_start(operational_api, monkeypatch):
    api, headers, factory = operational_api
    sup, op = headers('supervisor'), headers('mission_operator')
    area = new_area(api, sup)
    outside = [[x+.001, y] for x,y in PLAN['boundary']]
    waypoints = [[x+.001, y] for x,y in PLAN['waypoints']]
    plan = {**PLAN, 'assignment_id': area['id'], 'boundary': outside, 'waypoints': waypoints}
    preview = api.post('/api/v1/mission-approval-preview', headers=op,
                       json={'assignment_id': area['id'], 'boundary': outside})
    assert preview.status_code == 200 and preview.json()['outside_m2'] > 0
    mid = create(api, op, **plan)
    url = f'/api/v1/missions/{mid}'
    assert api.post(url+'/validate', headers=op).status_code == 422
    assert api.post(url+'/start', headers=op).status_code == 409

    def request():
        response = api.post(url+'/approval-requests', headers=op, json={'reason': 'Survey adjacent site'})
        assert response.status_code == 200, response.text
        return response.json()['request']['id']

    def decide(request_id, decision, reason=''):
        return api.post(f'/api/v1/mission-approvals/{request_id}/decision', headers=sup,
                        json={'decision': decision, 'reason': reason})

    first = request()
    assert request() == first
    assert decide(first, 'Rejected', 'Outside scope this week').status_code == 200
    assert api.post(url+'/validate', headers=op).status_code == 422
    assert decide(request(), 'Approved').status_code == 200
    assert api.post(url+'/validate', headers=op).status_code == 200
    updated = api.put(url, headers=op, json={**plan, 'plan_revision': 1, 'altitude_m': 6})
    assert updated.status_code == 200, updated.text
    assert updated.json()['approval']['status'] == 'Invalidated'
    assert api.put(url, headers=op, json={**plan, 'plan_revision': 1}).status_code == 409
    assert api.post(url+'/validate', headers=op).status_code == 422
    assert decide(request(), 'Approved').status_code == 200
    assert api.put(f'/api/v1/survey-areas/{area["id"]}', headers=sup,
                   json={**area_body(description='Updated metadata'), 'revision': 1}).status_code == 200
    assert api.get(url+'/approval', headers=op).json()['status'] == 'Invalidated'
    assert decide(request(), 'Approved').status_code == 200
    queued = []
    monkeypatch.setattr(operations, 'schedule', queued.append)
    assert api.post(url+'/validate', headers=op).status_code == 200
    assert queued == []
    assert api.post(url+'/start', headers=op).status_code == 202
    assert queued == [mid]
    with factory() as db:
        operations.finish(db, db.get(Mission, mid), 'FAILED', 'Intentional test cleanup')


def test_survey_area_invalid_polygons_and_operators(operational_api):
    api,headers,_=operational_api
    sup=headers('supervisor')
    for changes in [
        {'operator_id':'supervisor'}, {'operator_id':'not-an-account'}, {'name':'   '},
        {'boundary':[[0,0],[1,1],[0,1],[1,0],[0,0]]},
        {'boundary':[[0,0],[1,0],[1,1],[0,0]]}, # exceeds the large-area cap
        {'boundary':PLAN['boundary'][:-1]}, {'deadline':'2026-12-01T10:00:00'},
        {'boundary':[[179,0],[-179,0],[-179,1],[179,0]]},
    ]:
        assert api.post('/api/v1/survey-areas',headers=sup,json=area_body(**changes)).status_code==422


def test_survey_area_progress_uses_union_of_completed_valid_coverage(operational_api):
    api,headers,factory=operational_api
    sup,op=headers('supervisor'),headers('mission_operator')
    ring=[[8.5453,47.3976],[8.54545,47.3976],[8.54545,47.3977],[8.5453,47.3977],[8.5453,47.3976]]
    area=new_area(api,sup,boundary=ring)
    aid=area['id']
    def mission(boundary=ring):
        xs=[p[0] for p in boundary]; low,high=min(xs),max(xs)
        return create(api,op,assignment_id=aid,boundary=boundary,waypoints=[[low+(high-low)*.25,47.39762],[low+(high-low)*.75,47.39768]])
    def observe(mid,locations,valid=True):
        with factory.begin() as db:
            m=db.get(Mission,mid);m.started_at=datetime.now(UTC);m.state='EXECUTING'
            for index,(x,y) in enumerate(locations):
                observation=Observation(id=str(uuid4()),mission_id=mid,sequence=index,longitude=x,latitude=y,
                    altitude_m=5,speed_m_s=2,sensor=fixture(0) if valid else None,
                    source='explicit-test-fixture',created_at=datetime.now(UTC))
                db.add(observation);db.flush();store_position(db,observation)
    def finish(mid,state='COMPLETED'):
        with factory() as db:
            operations.finish(db,db.get(Mission,mid),state)
    def read():
        return api.get(f'/api/v1/survey-areas/{aid}',headers=sup).json()
    empty=mission();observe(empty,[(8.54533,47.39763)],False);finish(empty)
    assert read()['progress']['coverage_percent']==0 # completed flight, no valid sensors
    first=mission();observe(first,[(8.54533,47.39763)]);finish(first)
    partial=read()['progress']
    assert 0<partial['coverage_percent']<100
    duplicate=mission();observe(duplicate,[(8.54533,47.39763)]);finish(duplicate)
    assert read()['progress']['completed_m2']==pytest.approx(partial['completed_m2'])
    live=mission();observe(live,[(8.54542,47.39768)])
    progress=read()['progress']
    assert progress['in_progress_m2']>0 and progress['coverage_percent']==partial['coverage_percent']
    assert progress['completed_m2']+progress['in_progress_m2']+progress['remaining_m2']==pytest.approx(progress['total_m2'],abs=.02)
    finish(live,'CANCELLED')
    assert read()['progress']['in_progress_m2']==0
    assert read()['progress']['coverage_percent']==partial['coverage_percent']
    assert read()['status']=='IN_PROGRESS' and not read()['progress']['fully_surveyed']
    # A dense, explicitly synthetic valid observation grid covers all edges;
    # completion must arise from the real coverage pipeline, not a status flag.
    left=[[8.5453,47.3976],[8.545375,47.3976],[8.545375,47.3977],[8.5453,47.3977],[8.5453,47.3976]]
    right=[[8.545375,47.3976],[8.54545,47.3976],[8.54545,47.3977],[8.545375,47.3977],[8.545375,47.3976]]
    full=mission(left)
    observe(full,[(8.5453+i*.000015,47.3976+j*.00001) for i in range(6) for j in range(11)])
    assert not read()['progress']['fully_surveyed'] # live evidence never completes an assignment
    finish(full)
    assert not read()['progress']['fully_surveyed']
    second_half=mission(right)
    observe(second_half,[(8.545375+i*.000015,47.3976+j*.00001) for i in range(6) for j in range(11)])
    assert not read()['progress']['fully_surveyed']
    finish(second_half)
    complete=read()
    assert complete['status']=='COMPLETED'
    assert complete['progress']['fully_surveyed'] and complete['progress']['coverage_percent']==100
    assert complete['progress']['remaining_m2']==0
    assert len(complete['surveys'])==6
    almost=[*ring];almost[1]=[8.545450001,47.3976];almost[2]=[8.545450001,47.3977]
    response=api.put(f'/api/v1/survey-areas/{aid}',headers=sup,json={**area_body(boundary=almost),'revision':1})
    assert response.status_code==200,response.text
    assert response.json()['progress']['coverage_percent']==99.99
    assert not response.json()['progress']['fully_surveyed']
    # Expanding the assignment preserves history and truthfully reopens progress.
    larger=[*ring];larger[1]=[8.5456,47.3976];larger[2]=[8.5456,47.3977]
    response=api.put(f'/api/v1/survey-areas/{aid}',headers=sup,json={**area_body(boundary=larger),'revision':2})
    assert response.status_code==200,response.text
    assert response.json()['status']=='IN_PROGRESS' and response.json()['progress']['coverage_percent']<100
    assert len(read()['surveys'])==6


def test_gazebo_scene_is_scoped_to_active_vehicle_lease(operational_api,monkeypatch):
    api,headers,factory=operational_api
    op=headers('mission_operator')
    mid=create(api,op)
    calls=[]
    monkeypatch.setattr(operations.runtime,'call',lambda path: calls.append(path) or {
        'runtime':'px4-gazebo','simulated':True,'live':True,'source':'gazebo-world-pose',
        'pose':{'position':[1,2,3],'quaternion':[0,0,0,1]}})
    assert api.get(f'/api/v1/missions/{mid}/scene').status_code==401
    assert api.get(f'/api/v1/missions/{mid}/scene',headers=headers('other_field')).status_code==404
    assert api.get(f'/api/v1/missions/{mid}/scene',headers=op).json()['live'] is False
    assert not calls
    with factory.begin() as db:
        db.get(Mission,mid).state='EXECUTING'
        db.get(VehicleLease,'sitl-01').mission_id=mid
    assert api.get(f'/api/v1/missions/{mid}/scene',headers=headers('field_personnel')).json()['pose']['position']==[1,2,3]
    assert calls==['/scene']
    with factory.begin() as db:
        db.get(VehicleLease,'sitl-01').mission_id=None
        db.get(Mission,mid).state='FAILED'
    assert api.get(f'/api/v1/missions/{mid}/scene',headers=op).json()['live'] is False
    assert calls==['/scene']


def test_geometry_assignment_permissions_idempotency_and_vehicle_lease(operational_api,monkeypatch):
    api,headers,factory=operational_api
    op=headers('mission_operator')
    mid=create(api,op)
    with factory() as db:
        assert db.get(Mission,mid).state=='DRAFT'
        assert db.get(VehicleLease,'sitl-01').mission_id is None
    for role in ['administrator','supervisor','detection_analyst','field_personnel']:
        assert api.post(f'/api/v1/missions/{mid}/start',headers=headers(role)).status_code==403
    for role in ['other_operator','other_field']:
        assert api.get(f'/api/v1/missions/{mid}',headers=headers(role)).status_code==404
    assert api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code==409
    assert api.post('/api/v1/missions',headers=op,json={**PLAN,'waypoints':[[9,48],[9.1,48.1]]}).status_code==422
    assert api.post(f'/api/v1/missions/{mid}/validate',headers=op).status_code==200
    queued=[]
    monkeypatch.setattr(operations,'schedule',queued.append)
    assert api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code==202
    assert api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code==202
    assert queued==[mid]
    second=create(api,op)
    api.post(f'/api/v1/missions/{second}/validate',headers=op)
    assert api.post(f'/api/v1/missions/{second}/start',headers=op).status_code==409
    with factory() as db:
        mission=db.get(Mission,mid)
        operations.finish(db,mission,'FAILED','Intentional integration cleanup')


class ReplayRuntime:
    def __init__(self):
        self.calls=[]
        self.sequence=-1
    def call(self,path,body=None):
        self.calls.append(path)
        if path=='/status':
            self.sequence+=1
        return {'runtime':'px4-gazebo','simulated':True,'ready':True,'running':True,
                'armed':0<=self.sequence<12,'longitude':8.5454+self.sequence*.000008,
                'latitude':47.3977,'altitude_m':5,'speed_m_s':2,'battery_percent':90,
                'total':6,'reached':5 if self.sequence>=12 else 0}


def test_persisted_replay_detection_coverage_history_reviews_reports_and_stop_request(operational_api,monkeypatch):
    api,headers,factory=operational_api
    op=headers('mission_operator')
    replay=ReplayRuntime()
    monkeypatch.setattr(operations,'runtime',replay)
    monkeypatch.setattr(operations,'schedule',lambda _:None)
    monkeypatch.setattr(operations.time,'sleep',lambda _:None)
    mid=create(api,op)
    api.post(f'/api/v1/missions/{mid}/validate',headers=op)
    api.post(f'/api/v1/missions/{mid}/start',headers=op)
    field=headers('field_personnel')
    before=list(replay.calls)
    assert api.post(f'/api/v1/missions/{mid}/stop-request',headers=field,json={'reason':'Exercise a field stop request'}).status_code==200
    assert replay.calls==before  # Request does not command the vehicle.
    operations.run_mission(mid)
    assert replay.calls[:3]==['/runtime/start','/status','/mission/upload']
    assert replay.calls[3]=='/mission/start'
    detail=api.get(f'/api/v1/missions/{mid}',headers=op).json()
    assert detail['mission']['state']=='COMPLETED'
    assert 0<detail['coverage']['coverage_percent']<100
    assert detail['detections'] and all(t['simulated'] for t in detail['detections'])
    assert all(t['classification']=='potential_mine' and t['created_at'] for t in detail['detections'])
    target=detail['detections'][0]
    assert api.post(f"/api/v1/detections/{target['id']}/reviews",headers=op,json={'assessment':'inconclusive','notes':'Test'}).status_code==403
    analyst=headers('detection_analyst')
    assert api.post(f"/api/v1/detections/{target['id']}/reviews",headers=analyst,json={'assessment':'needs_investigation','notes':'Synthetic baseline requires review'}).status_code==201
    history=api.get('/api/v1/areas/integration-area/surveys',headers=op).json()
    assert any(h['mission_id']==mid and h['simulated'] for h in history)
    report=api.get(f'/api/v1/missions/{mid}/report?format=csv',headers=op)
    assert report.status_code==200 and 'SIMULATION REPORT' in report.text and 'potential_target_id' in report.text
    assert api.get(f'/api/v1/missions/{mid}/report',headers=headers('other_field')).status_code==404
    assert api.get(f'/api/v1/missions/{mid}/report',headers=field).status_code==403
    # Flight telemetry without sensor observations never creates coverage.
    empty=create(api,op,synthetic_sensors=False)
    assert api.get(f'/api/v1/missions/{empty}/coverage',headers=op).json()['coverage_percent']==0
    assert any(e['kind']=='stop_requested' for e in detail['events'])
    with factory() as db:
        assert db.execute(text('SELECT ST_SRID(coverage_geometry) FROM survey_attempts WHERE mission_id=:id'),{'id':mid}).scalar_one()==4326
    with pytest.raises(DBAPIError,match='append-only'):
        with factory.begin() as db:
            db.execute(text('DELETE FROM survey_attempts WHERE mission_id=:id'),{'id':mid})
    token=op['Authorization'].split(' ',1)[1]
    with api.websocket_connect(f'/api/v1/ws/missions/{mid}') as socket:
        socket.send_json({'token':token})
        assert socket.receive_json()['mission']['id']==mid
    with pytest.raises(WebSocketDisconnect) as closed:
        with api.websocket_connect(f'/api/v1/ws/missions/{mid}') as socket:
            socket.send_json({'token':headers('other_field')['Authorization'].split(' ',1)[1]})
            socket.receive_json()
    assert closed.value.code==4403


def test_parallel_starts_reserve_one_vehicle_and_failures_release_it(operational_api,monkeypatch):
    api,headers,factory=operational_api
    op=headers('mission_operator')
    ids=[create(api,op) for _ in range(2)]
    for mid in ids:
        api.post(f'/api/v1/missions/{mid}/validate',headers=op)
    queued=[]
    monkeypatch.setattr(operations,'schedule',queued.append)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda mid:api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code,ids))
    assert sorted(results)==[202,409]
    assert len(queued)==1
    class FailedRuntime:
        def call(self,*args):
            raise RuntimeError('Intentional simulator startup failure')
    monkeypatch.setattr(operations,'runtime',FailedRuntime())
    operations.run_mission(queued[0])
    with factory() as db:
        assert db.get(Mission,queued[0]).state=='FAILED'
        assert db.get(VehicleLease,'sitl-01').mission_id is None


def test_restart_recovery_never_resumes_a_flight(operational_api,monkeypatch):
    api,headers,factory=operational_api
    op=headers('mission_operator')
    mid=create(api,op)
    api.post(f'/api/v1/missions/{mid}/validate',headers=op)
    monkeypatch.setattr(operations,'schedule',lambda _:None)
    replay=ReplayRuntime()
    monkeypatch.setattr(operations,'runtime',replay)
    api.post(f'/api/v1/missions/{mid}/start',headers=op)
    operations.recover()
    assert replay.calls==['/runtime/stop']
    operations.run_mission(mid)  # A late queued worker must not revive the attempt.
    assert replay.calls==['/runtime/stop']
    data=api.get(f'/api/v1/missions/{mid}',headers=op).json()
    assert data['mission']['state']=='INTERRUPTED'
    assert data['coverage']['coverage_percent']==0
    assert api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code==409


@pytest.mark.skipif(os.getenv('RUN_PX4_E2E')!='1',reason='Opt in to actual isolated PX4/Gazebo flight')
def test_actual_px4_gazebo_flight(operational_api):
    api,headers,factory=operational_api
    op=headers('mission_operator')
    mid=create(api,op,name='Actual PX4 SITL end-to-end')
    assert api.post(f'/api/v1/missions/{mid}/validate',headers=op).status_code==200
    assert api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code==202
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        data=api.get(f'/api/v1/missions/{mid}',headers=op).json()
        state=data['mission']['state']
        if state in operations.TERMINAL:
            assert state=='COMPLETED',data['mission'].get('error')
            assert len(data['observations'])>5
            assert any(o['altitude_m']>2 for o in data['observations'])
            assert data['detections']
            assert data['coverage']['coverage_percent']>0
            print(f"PX4 E2E completed: {len(data['observations'])} samples, {len(data['detections'])} synthetic potential targets, {data['coverage']['coverage_percent']}% experimental coverage")
            return
        time.sleep(2)
    operations.runtime.call('/runtime/stop',{})
    with factory() as db:
        operations.finish(db,db.get(Mission,mid),'FAILED','E2E timeout')
    pytest.fail('Actual PX4 flight did not complete within four minutes')


def test_mission_area_and_route_caps_removed_but_containment_retained(operational_api):
    api, headers, _ = operational_api
    op = headers('mission_operator')
    large = {**PLAN, 'name': 'Large contained plan',
             'boundary': [[8.5401,47.3901],[8.5499,47.3901],[8.5499,47.3999],[8.5401,47.3999],[8.5401,47.3901]],
             'waypoints': [[8.541,47.391],[8.549,47.399]]}
    result = api.post('/api/v1/missions', headers=op, json=large)
    assert result.status_code == 201, result.text
    mid = result.json()['id']
    assert api.post(f'/api/v1/missions/{mid}/validate', headers=op).status_code == 200
    tiny = {**PLAN, 'boundary': [[8.5454,47.3977],[8.54542,47.3977],[8.54542,47.39772],[8.5454,47.39772],[8.5454,47.3977]],
            'waypoints': [[8.545405,47.397705],[8.545415,47.397715]]}
    assert api.post('/api/v1/missions', headers=op, json=tiny).status_code == 201
    assert api.post('/api/v1/missions', headers=op, json={**large, 'waypoints': [[9,48],[9.1,48.1]]}).status_code == 422


@pytest.mark.skipif(os.getenv('RUN_PX4_MULTI_E2E')!='1',reason='Opt in to two actual isolated PX4/Gazebo flights')
def test_actual_two_uavs_same_area(operational_api):
    from app.fleet import vehicle_runtime
    from pathlib import Path
    import json
    api,headers,factory=operational_api;op=headers('mission_operator')
    ids=[create(api,op,name='Two-UAV isolated test '+uav,uav_id=uav) for uav in ['sitl-01','sitl-02']]
    evidence={'mode':'isolated simulation only','synthetic_sensors':True,'simultaneously_executing':False,'missions':[]}
    try:
        for mid in ids:assert api.post(f'/api/v1/missions/{mid}/validate',headers=op).status_code==200
        with ThreadPoolExecutor(max_workers=2) as pool:
            starts=list(pool.map(lambda mid:api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code,ids))
        assert starts==[202,202],starts
        deadline=time.monotonic()+360
        while time.monotonic()<deadline:
            rows=[api.get(f'/api/v1/missions/{mid}',headers=op).json() for mid in ids]
            if all(row['mission']['state']=='EXECUTING' for row in rows):evidence['simultaneously_executing']=True
            if any(row['mission']['state']=='FAILED' for row in rows):pytest.fail(str([row['mission'].get('error') for row in rows]))
            if all(row['mission']['state'] in operations.TERMINAL for row in rows):break
            time.sleep(2)
        assert evidence['simultaneously_executing'],'Flights did not overlap in EXECUTING'
        for uid,mid,row in zip(['sitl-01','sitl-02'],ids,rows):
            assert row['mission']['state']=='COMPLETED',row['mission']
            assert row['mission']['uav_id']==uid and len(row['observations'])>5
            assert all(o['mission_id']==mid for o in row['observations'])
            assert any(o['altitude_m']>2 for o in row['observations'])
            with factory() as db:
                attempt=db.scalar(select(SurveyAttempt).where(SurveyAttempt.mission_id==mid))
                assert attempt.uav_id==uid
                assert db.get(VehicleLease,uid).mission_id is None
            evidence['missions'].append({'mission_id':mid,'uav_id':uid,'state':row['mission']['state'],'observations':len(row['observations']),'synthetic_targets':len(row['detections']),'experimental_coverage_percent':row['coverage']['coverage_percent']})
        area=api.get('/api/v1/survey-areas/workflow-area',headers=op).json()
        assert area['uav_count']==2 and area['uav_ids']==['sitl-01','sitl-02']
        out=Path(__file__).resolve().parents[2]/'docs/multi-uav-e2e-evidence.json'
        out.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        print('MULTI-UAV E2E:',json.dumps(evidence))
    finally:
        for mid in ids:
            with factory() as db:
                mission=db.get(Mission,mid)
                vehicle_runtime(db,mission.uav_id).call('/runtime/stop',{})
                if mission.state not in operations.TERMINAL:operations.finish(db,mission,'INTERRUPTED','Multi-UAV test cleanup')


def test_multi_uav_disjoint_overlapping_and_separate_assignment_plans(operational_api):
    api,headers,factory=operational_api
    sup,op=headers('supervisor'),headers('mission_operator')
    parent=new_area(api,sup,name='Partitioned area')
    west=[[8.5453,47.3976],[8.54558,47.3976],[8.54558,47.39794],[8.5453,47.39794],[8.5453,47.3976]]
    east=[[8.54562,47.3976],[8.5459,47.3976],[8.5459,47.39794],[8.54562,47.39794],[8.54562,47.3976]]
    first=create(api,op,name='West sector',assignment_id=parent['id'],uav_id='sitl-01',boundary=west,waypoints=[[8.5454,47.3977],[8.5455,47.3978]])
    second=create(api,op,name='East sector',assignment_id=parent['id'],uav_id='sitl-02',boundary=east,waypoints=[[8.5457,47.3977],[8.5458,47.3978]])
    repeated=create(api,op,name='Overlapping survey',assignment_id=parent['id'],uav_id='sitl-03')
    shifted=lambda ring:[[x+.001,y+.001] for x,y in ring]
    other=new_area(api,sup,name='Separate assignment',boundary=shifted(PLAN['boundary']))
    remote=create(api,op,name='Separate sector',assignment_id=other['id'],uav_id='sitl-01',boundary=shifted(PLAN['boundary']),waypoints=shifted(PLAN['waypoints']))
    for mid in [first,second,repeated,remote]:
        assert api.post(f'/api/v1/missions/{mid}/validate',headers=op).status_code==200
    a=api.get(f"/api/v1/survey-areas/{parent['id']}",headers=op).json()
    b=api.get(f"/api/v1/survey-areas/{other['id']}",headers=op).json()
    assert {m['id'] for m in a['missions']}=={first,second,repeated}
    assert {m['id'] for m in b['missions']}=={remote}
    assert a['uav_count']==3 and b['uav_count']==1
    assert a['progress']['coverage_percent']==b['progress']['coverage_percent']==0
    outside=api.post('/api/v1/missions',headers=op,json={**PLAN,'assignment_id':parent['id'],'boundary':shifted(PLAN['boundary']),'waypoints':shifted(PLAN['waypoints'])})
    assert outside.status_code==201
    outside_id=outside.json()['id']
    assert outside.json()['approval']['required'] is True
    assert api.post(f'/api/v1/missions/{outside_id}/validate',headers=op).status_code==422
    assert api.post(f'/api/v1/missions/{outside_id}/start',headers=op).status_code==409
    escaped_route=api.post('/api/v1/missions',headers=op,json={**PLAN,'assignment_id':parent['id'],'boundary':west,'waypoints':[[8.5454,47.3977],[8.5458,47.3978]]})
    assert escaped_route.status_code==422 and 'entire route' in escaped_route.text


def test_reference_lane_preview_permissions_containment_and_no_side_effects(operational_api):
    api,headers,factory=operational_api
    body={'assignment_id':'workflow-area','uav_id':'sitl-01','boundary':PLAN['boundary'],'spacing_m':5}
    assert api.post('/api/v1/plans/preview',json=body).status_code==401
    for role in ['administrator','supervisor','field_personnel','detection_analyst']:
        assert api.post('/api/v1/plans/preview',json=body,headers=headers(role)).status_code==403
    assert api.post('/api/v1/plans/preview',json=body,headers=headers('other_operator')).status_code==409
    op=headers('mission_operator')
    with factory() as db:before=len(db.scalars(select(Mission)).all())
    data=api.post('/api/v1/plans/preview',json=body,headers=op)
    assert data.status_code==200,data.text
    plan=data.json();assert plan['ok'] and 2<=len(plan['path'])<=100
    mid=create(api,op,name='Generated lanes',waypoints=plan['path'])
    assert api.post(f'/api/v1/missions/{mid}/validate',headers=op).status_code==200
    with factory() as db:
        assert len(db.scalars(select(Mission)).all())==before+1
        assert db.get(VehicleLease,'sitl-01').mission_id is None
    concave=[[8.5453,47.3976],[8.5459,47.3976],[8.5459,47.39794],[8.5457,47.39794],[8.5457,47.3977],[8.5455,47.3977],[8.5455,47.39794],[8.5453,47.39794],[8.5453,47.3976]]
    bad=api.post('/api/v1/plans/preview',json={**body,'boundary':concave},headers=op)
    assert bad.status_code==200 and not bad.json()['ok'] and bad.json()['path']==[]


def test_reference_circle_and_invalid_outline_preview(operational_api):
    import math
    api,headers,factory=operational_api
    ring=[[8.5456+.0001*math.cos(i*math.tau/32),47.39777+.0001*math.sin(i*math.tau/32)] for i in range(32)]
    ring.append(ring[0])
    body={'assignment_id':'workflow-area','uav_id':'sitl-03','boundary':ring,'spacing_m':5}
    result=api.post('/api/v1/plans/preview',json=body,headers=headers('mission_operator'))
    assert result.status_code==200 and result.json()['ok'],result.text
    broken=[[8.5453,47.3976],[8.5459,47.39794],[8.5453,47.39794],[8.5459,47.3976],[8.5453,47.3976]]
    result=api.post('/api/v1/plans/preview',json={**body,'boundary':broken},headers=headers('mission_operator'))
    assert result.status_code==200 and not result.json()['ok'] and result.json()['path']==[]


@pytest.mark.skipif(os.getenv('RUN_PX4_HOME_E2E')!='1',reason='Opt in to isolated geographic-origin flight')
def test_actual_relocated_saudi_simulation(operational_api):
    from pathlib import Path
    import json
    from app.fleet import vehicle_runtime
    api,headers,factory=operational_api
    op,sup=headers('mission_operator'),headers('supervisor')
    moved=lambda points:[[47.1605+(x-8.5454),22.77135+(y-47.3977)] for x,y in points]
    ring,route=moved(PLAN['boundary']),moved(PLAN['waypoints'])
    parent=new_area(api,sup,name='Saudi-origin isolated test',boundary=ring)
    mid=create(api,op,name='Saudi-origin SITL',assignment_id=parent['id'],boundary=ring,waypoints=route)
    try:
        assert api.post(f'/api/v1/missions/{mid}/validate',headers=op).status_code==200
        assert api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code==202
        deadline=time.monotonic()+360
        while time.monotonic()<deadline:
            row=api.get(f'/api/v1/missions/{mid}',headers=op).json()
            if row['mission']['state'] in operations.TERMINAL:break
            time.sleep(2)
        assert row['mission']['state']=='COMPLETED',row['mission']
        assert len(row['observations'])>5
        assert all(abs(o['longitude']-47.1605)<.002 and abs(o['latitude']-22.77135)<.002 for o in row['observations'])
        with factory() as db:
            assert db.get(VehicleLease,'sitl-01').mission_id is None
            status=vehicle_runtime(db,'sitl-01').call('/status')
        assert status['simulation_home']=={'latitude':route[0][1],'longitude':route[0][0]}
        evidence={'passed':True,'simulation_only':True,'origin':status['simulation_home'],'mission_state':row['mission']['state'],'observations':len(row['observations']),'first_measured_position':{k:row['observations'][0][k] for k in ['latitude','longitude']},'sensor_data':'explicit synthetic fixtures'}
        (Path(__file__).resolve().parents[2]/'docs/relocated-origin-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        print('RELOCATED ORIGIN:',evidence)
    finally:
        with factory() as db:
            vehicle_runtime(db,'sitl-01').call('/runtime/stop',{})
            mission=db.get(Mission,mid)
            if mission.state not in operations.TERMINAL:operations.finish(db,mission,'INTERRUPTED','Relocated-origin test cleanup')
