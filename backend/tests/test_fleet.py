"""Fleet authorization and lease isolation; runtime effects are explicit test doubles."""
from datetime import UTC,datetime
from app.models import User
from app.operations_models import UAV,Mission,VehicleLease,SurveyAreaAssignment
from app import operations,fleet
from test_auth import login
import pytest
from fastapi import HTTPException

def register(api,headers):
    assert api.post('/api/v1/fleet/types',headers=headers,json={'id':'quad','name':'Test quadrotor','category':'quadrotor','simulation_profile':'px4-x500'}).status_code==201
    for n in [1,2]:
        assert api.post('/api/v1/fleet/vehicles',headers=headers,json={'id':f'uav{n}','name':f'Test UAV {n}','type_id':'quad','runtime_slot':f'sitl-0{n}'}).status_code==201

def test_catalog_authorization_uniqueness_and_unsupported_type(client):
    api,factory=client;admin=login(api,'administrator');op=login(api,'mission_operator')
    assert api.get('/api/v1/fleet/vehicles').status_code==401
    assert api.get('/api/v1/fleet/vehicles',headers=login(api,'field_personnel')).status_code==403
    assert api.post('/api/v1/fleet/types',headers=op,json={'id':'x','name':'X','category':'quad'}).status_code==403
    register(api,admin)
    assert api.post('/api/v1/fleet/types',headers=admin,json={'id':'bad-profile','name':'Not a quadrotor','category':'fixed-wing','simulation_profile':'px4-x500'}).status_code==422
    assert api.post('/api/v1/fleet/vehicles',headers=admin,json={'id':'duplicate','name':'Duplicate','type_id':'quad','runtime_slot':'sitl-01'}).status_code==409
    assert api.post('/api/v1/fleet/vehicles',headers=admin,json={'id':'external','name':'External','type_id':'quad','runtime_slot':'http://aircraft'}).status_code==422
    assert api.post('/api/v1/fleet/types',headers=admin,json={'id':'fixed','name':'Future fixed wing','category':'fixed-wing'}).status_code==201
    assert api.post('/api/v1/fleet/vehicles',headers=admin,json={'id':'catalog','name':'Catalog UAV','type_id':'fixed'}).status_code==201
    rows=api.get('/api/v1/fleet/vehicles',headers=op).json()
    assert len(rows)==3 and not next(v for v in rows if v['id']=='catalog')['executable']
    with factory() as db:
        import pytest
        from fastapi import HTTPException
        with pytest.raises(HTTPException):fleet.vehicle_runtime(db,'catalog')

def test_distinct_uavs_same_area_exclusive_leases_and_failure_isolation(client,monkeypatch):
    api,factory=client;admin=login(api,'administrator');op=login(api,'mission_operator');register(api,admin)
    at=datetime.now(UTC)
    with factory() as db:
        db.add(SurveyAreaAssignment(id='parent',name='Parent',description='Test only',operator_id='mission_operator',created_by='supervisor',boundary={},created_at=at,updated_at=at));db.flush()
        for mid,uid in [('first','uav1'),('second','uav2'),('conflict','uav1')]:
            db.add(Mission(id=mid,name=mid,assignment_id='parent',area_id='test-area',operator_id='mission_operator',field_ids=[],boundary={},waypoints=[[8.5454,47.3977],[8.5455,47.3978]],altitude_m=5,speed_m_s=2,state='READY',uav_id=uid,created_at=at))
        db.commit()
    queued=[];monkeypatch.setattr(operations,'schedule',queued.append);monkeypatch.setattr(operations,'validate_geometry',lambda *args,**kwargs:None)
    assert api.post('/api/v1/missions/first/start',headers=admin).status_code==403
    assert api.post('/api/v1/missions/first/start',headers=op).status_code==202
    assert api.post('/api/v1/missions/conflict/start',headers=op).status_code==409
    assert api.post('/api/v1/missions/second/start',headers=op).status_code==202
    assert queued==['first','second']
    assert api.patch('/api/v1/fleet/vehicles/uav1',headers=admin,json={'active':False}).status_code==409
    rows=api.get('/api/v1/fleet/vehicles',headers=op).json();assert all(v['in_use'] for v in rows)
    class Broken:
        def __init__(self):self.calls=[]
        def call(self,path,body=None):
            self.calls.append(path)
            if path=='/runtime/start':raise RuntimeError('Test runtime failure')
    a,b=Broken(),Broken();monkeypatch.setattr(operations,'runtime',a);monkeypatch.setattr(fleet,'secondary_runtime',b);monkeypatch.setattr(operations,'SessionLocal',factory)
    monkeypatch.setattr(operations,'calculate',lambda *args:{'coverage_percent':0,'geometry':{'type':'GeometryCollection','geometries':[]},'algorithm_version':'test-only'})
    operations.run_mission('first')
    assert a.calls==['/runtime/start','/runtime/stop'] and b.calls==[]
    with factory() as db:
        assert db.get(Mission,'first').state=='FAILED'
        assert db.get(VehicleLease,'uav1').mission_id is None
        assert db.get(VehicleLease,'uav2').mission_id=='second'


@pytest.mark.parametrize('count',[0,1,2,3,5,10])
def test_inventory_sizes_and_different_catalog_categories(client,count):
    api,factory=client;admin=login(api,'administrator')
    for category in ['quadrotor','hexacopter','fixed-wing']:
        assert api.post('/api/v1/fleet/types',headers=admin,json={'id':category,'name':category,'category':category}).status_code==201
    for i in range(count):
        category=['quadrotor','hexacopter','fixed-wing'][i%3]
        assert api.post('/api/v1/fleet/vehicles',headers=admin,json={'id':f'catalog-{i}','name':f'Catalog {i}','type_id':category}).status_code==201
    rows=api.get('/api/v1/fleet/vehicles',headers=admin).json();assert len(rows)==count
    assert all(not r['executable'] and not r['in_use'] for r in rows)
    with factory() as db:
        for row in rows:
            with pytest.raises(HTTPException):fleet.vehicle_runtime(db,row['id'])


def test_operator_selects_vehicle_supervisor_assigns_area_and_unauthorized_operator_is_rejected(client,monkeypatch):
    api,factory=client;admin=login(api,'administrator');op=login(api,'mission_operator');sup=login(api,'supervisor');register(api,admin)
    at=datetime.now(UTC)
    with factory() as db:
        existing=db.get(User,'mission_operator')
        db.add(User(id='other',username='other',role='mission_operator',password_hash=existing.password_hash))
        db.add(SurveyAreaAssignment(id='parent',name='Parent',description='Test only',operator_id='mission_operator',created_by='supervisor',boundary={},created_at=at,updated_at=at));db.commit()
    monkeypatch.setattr(operations,'validate_geometry',lambda *args,**kwargs:None)
    plan={'name':'Selected UAV test','assignment_id':'parent','area_id':'test','uav_id':'uav2','boundary':[[0,0],[1,0],[1,1],[0,0]],'waypoints':[[0,0],[.1,.1]]}
    assert api.post('/api/v1/missions',headers=sup,json=plan).status_code==403
    assert api.post('/api/v1/missions',headers=admin,json=plan).status_code==403
    assert api.post('/api/v1/missions',headers=login(api,'other'),json=plan).status_code==404
    monkeypatch.setattr(operations.mission_approvals,'context',lambda *args:None)
    result=api.post('/api/v1/missions',headers=op,json=plan);assert result.status_code==201,result.text
    assert result.json()['uav_id']=='uav2' and result.json()['operator_id']=='mission_operator'
    assert api.post('/api/v1/missions',headers=op,json={**plan,'uav_id':'unknown'}).status_code==409
    assert api.patch('/api/v1/fleet/vehicles/uav1',headers=admin,json={'active':False}).status_code==200
    assert api.post('/api/v1/missions',headers=op,json={**plan,'uav_id':'uav1'}).status_code==409


def test_supported_variant_and_execution_capacity(client):
    api,factory=client;admin=login(api,'administrator');register(api,admin)
    assert api.post('/api/v1/fleet/types',headers=admin,json={'id':'lidar','name':'Downward LiDAR','category':'quadrotor','simulation_profile':'px4-x500-lidar-down'}).status_code==201
    assert api.post('/api/v1/fleet/vehicles',headers=admin,json={'id':'third','name':'Third UAV','type_id':'lidar','runtime_slot':'sitl-03'}).status_code==201
    assert api.post('/api/v1/fleet/vehicles',headers=admin,json={'id':'fourth','name':'Fourth UAV','type_id':'lidar','runtime_slot':'sitl-04'}).status_code==422
    assert api.post('/api/v1/fleet/vehicles',headers=admin,json={'id':'duplicate-third','name':'Duplicate third','type_id':'lidar','runtime_slot':'sitl-03'}).status_code==409
    assert api.post('/api/v1/fleet/types',headers=admin,json={'id':'unknown-profile','name':'Unknown profile','category':'quadrotor','simulation_profile':'arbitrary-model'}).status_code==422
    assert api.post('/api/v1/fleet/types',headers=admin,json={'id':'catalog-type','name':'Catalog type','category':'hexacopter'}).status_code==201
    assert api.post('/api/v1/fleet/vehicles',headers=admin,json={'id':'catalog-runtime','name':'Unsupported binding','type_id':'catalog-type','runtime_slot':'sitl-03'}).status_code==422
    rows=api.get('/api/v1/fleet/vehicles',headers=admin).json()
    assert len(rows)==3 and all(row['executable'] for row in rows)
    with factory() as db:assert fleet.vehicle_runtime(db,'third') is fleet.third_runtime


def test_vehicle_details_authorization_and_recorded_usage(client):
    api,factory=client;admin=login(api,'administrator');register(api,admin)
    assert api.get('/api/v1/fleet/vehicles/uav1').status_code==401
    assert api.get('/api/v1/fleet/vehicles/uav1',headers=login(api,'field_personnel')).status_code==403
    assert api.get('/api/v1/fleet/vehicles/missing',headers=admin).status_code==404
    at=datetime.now(UTC)
    with factory() as db:
        for mid,state,started in [('draft','DRAFT',None),('done','COMPLETED',at),('failed','FAILED',at)]:
            db.add(Mission(id=mid,name=mid,area_id='test',operator_id='mission_operator',field_ids=[],boundary={},waypoints=[],altitude_m=5,speed_m_s=2,state=state,uav_id='uav1',created_at=at,started_at=started))
        db.commit()
    result=api.get('/api/v1/fleet/vehicles/uav1',headers=login(api,'supervisor'))
    assert result.status_code==200
    data=result.json()
    assert data['type']['name']=='Test quadrotor'
    assert data['usage']['missions_planned']==3 and data['usage']['missions_started']==2
    assert data['usage']['missions_completed']==1 and data['usage']['survey_attempts']==0
    assert data['usage']['last_started_at'] is not None
    other=api.get('/api/v1/fleet/vehicles/uav2',headers=admin).json()
    assert other['usage']['missions_planned']==0 and other['usage']['last_started_at'] is None
