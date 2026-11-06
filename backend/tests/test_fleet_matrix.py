"""Opt-in real 1/2/3-channel and camera-free mixed-model flight matrix."""
import os,time,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select
from test_workflows import database,operational_api,create
from app import operations
from app.fleet import vehicle_runtime
from app.operations_models import UAV,UAVType,Mission,Observation,SurveyAttempt,VehicleLease

pytestmark=pytest.mark.skipif(os.getenv('RUN_FLEET_MATRIX')!='1',reason='Opt in to fleet flight matrix')
RESULTS=[]

@pytest.mark.parametrize('vehicles',[['sitl-01'],['sitl-03'],['sitl-01','sitl-02'],['sitl-01','sitl-02','sitl-03']],ids=['one-x500','one-lidar-variant','two-x500','three-mixed-variants'])
def test_actual_fleet_scenarios(operational_api,vehicles):
    api,headers,factory=operational_api;op=headers('mission_operator')
    ids=[create(api,op,name='Fleet matrix '+uid,uav_id=uid) for uid in vehicles]
    result={'vehicles':vehicles,'simultaneously_executing':False,'missions':[]}
    try:
        for mid in ids:assert api.post(f'/api/v1/missions/{mid}/validate',headers=op).status_code==200
        with ThreadPoolExecutor(max_workers=len(ids)) as pool:
            assert list(pool.map(lambda mid:api.post(f'/api/v1/missions/{mid}/start',headers=op).status_code,ids))==[202]*len(ids)
        deadline=time.monotonic()+420
        while time.monotonic()<deadline:
            rows=[api.get(f'/api/v1/missions/{mid}',headers=op).json() for mid in ids]
            if all(r['mission']['state']=='EXECUTING' for r in rows):result['simultaneously_executing']=True
            assert not any(r['mission']['state']=='FAILED' for r in rows),[r['mission'].get('error') for r in rows]
            if all(r['mission']['state'] in operations.TERMINAL for r in rows):break
            time.sleep(2)
        assert result['simultaneously_executing']
        for uid,mid,row in zip(vehicles,ids,rows):
            assert row['mission']['state']=='COMPLETED',row['mission']
            assert row['mission']['uav_id']==uid and len(row['observations'])>5
            assert all(o['mission_id']==mid for o in row['observations'])
            with factory() as db:
                vehicle=db.get(UAV,uid);profile=db.get(UAVType,vehicle.type_id).simulation_profile
                actual=vehicle_runtime(db,uid).call('/status')
                assert actual['simulation_profile']==profile
                attempt=db.scalar(select(SurveyAttempt).where(SurveyAttempt.mission_id==mid))
                assert attempt.uav_id==uid and db.get(VehicleLease,uid).mission_id is None
            result['missions'].append({'uav_id':uid,'profile':profile,'state':'COMPLETED','observations':len(row['observations']),'synthetic_targets':len(row['detections']),'experimental_coverage_percent':row['coverage']['coverage_percent']})
        result['passed']=True
    finally:
        for mid in ids:
            with factory() as db:
                mission=db.get(Mission,mid);vehicle_runtime(db,mission.uav_id).call('/runtime/stop',{})
                if mission.state not in operations.TERMINAL:operations.finish(db,mission,'INTERRUPTED','Fleet matrix cleanup')
        RESULTS.append(result)
        (Path(__file__).resolve().parents[2]/'docs/fleet-matrix-evidence.json').write_text(json.dumps({'simulation_only':True,'sensor_data':'explicit synthetic fixtures','scenarios':RESULTS},indent=2),encoding='utf-8')
        print('FLEET SCENARIO:',json.dumps(result))
