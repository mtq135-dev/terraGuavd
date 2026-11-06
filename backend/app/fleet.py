"""Catalog and fixed isolated runtime bindings. No arbitrary transport addresses."""
from datetime import UTC,datetime
from typing import Annotated,Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from .operations_models import UAV,UAVType,VehicleLease,Mission,SurveyAttempt
from .security import Db,current_user,effective_permissions,audit
from .models import User
from .runtime import runtime,secondary_runtime,third_runtime

router=APIRouter(prefix='/api/v1/fleet')
Identity=Annotated[User,Depends(current_user)]
def check(user,manage=False):
    if ('fleet:manage' if manage else 'fleet:read') not in effective_permissions(user):raise HTTPException(403,'Fleet permission required')
def vehicle_runtime(db,uav_id,primary=None):
    vehicle=db.scalar(select(UAV).where(UAV.id==uav_id).with_for_update().execution_options(populate_existing=True))
    kind=db.get(UAVType,vehicle.type_id) if vehicle else None
    if not vehicle or not vehicle.active or not kind or kind.simulation_profile not in {'px4-x500','px4-x500-lidar-down'} or vehicle.runtime_slot not in {'sitl-01','sitl-02','sitl-03'}:
        raise HTTPException(409,'Select an enabled UAV bound to a supported isolated x500 runtime')
    return (primary if primary is not None else runtime) if vehicle.runtime_slot=='sitl-01' else secondary_runtime if vehicle.runtime_slot=='sitl-02' else third_runtime
def record(row):return {c.name:getattr(row,c.name) for c in row.__table__.columns}
def commit(db):
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Identifier, type name or runtime slot already exists')
class TypeInput(BaseModel):
    id:str=Field(min_length=1,max_length=36,pattern=r'^[a-zA-Z0-9_-]+$')
    name:str=Field(min_length=1,max_length=80)
    category:str=Field(min_length=1,max_length=40)
    simulation_profile:Literal['px4-x500','px4-x500-lidar-down','catalog-only']='catalog-only'
    specifications:dict=Field(default_factory=dict)
    @model_validator(mode='after')
    def supported_profile(self):
        if self.simulation_profile!='catalog-only' and self.category!='quadrotor':
            raise ValueError('The x500 simulation profile supports the quadrotor category only')
        return self
class VehicleInput(BaseModel):
    id:str=Field(min_length=1,max_length=40,pattern=r'^[a-zA-Z0-9_-]+$')
    name:str=Field(min_length=1,max_length=100)
    type_id:str=Field(min_length=1,max_length=36)
    runtime_slot:Literal['sitl-01','sitl-02','sitl-03']|None=None
class Availability(BaseModel):
    active:bool
@router.get('/types')
def types(db:Db,user:Identity):
    check(user);return [record(t) for t in db.scalars(select(UAVType).order_by(UAVType.id))]
@router.post('/types',status_code=201)
def add_type(body:TypeInput,db:Db,user:Identity):
    check(user,True);row=UAVType(**body.model_dump());db.add(row);audit(db,user.id,'fleet_type_created:'+row.id);commit(db);return record(row)
@router.get('/vehicles')
def vehicles(db:Db,user:Identity):
    check(user);rows=[]
    for row in db.scalars(select(UAV).order_by(UAV.id)):
        lease=db.get(VehicleLease,row.id);kind=db.get(UAVType,row.type_id)
        rows.append({**record(row),'type_name':kind.name,'simulation_profile':kind.simulation_profile,
            'in_use':bool(lease and lease.mission_id),'executable':bool(row.active and row.runtime_slot in {'sitl-01','sitl-02','sitl-03'} and kind.simulation_profile in {'px4-x500','px4-x500-lidar-down'})})
    return rows
@router.post('/vehicles',status_code=201)
def add_vehicle(body:VehicleInput,db:Db,user:Identity):
    check(user,True)
    kind=db.get(UAVType,body.type_id)
    if not kind:raise HTTPException(422,'Unknown UAV type')
    if body.runtime_slot and kind.simulation_profile=='catalog-only':raise HTTPException(422,'This type has no supported flight profile')
    row=UAV(**body.model_dump(),active=True,created_at=datetime.now(UTC));db.add(row)
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Identifier or runtime slot already exists')
    db.add(VehicleLease(id=row.id));audit(db,user.id,'fleet_vehicle_created:'+row.id);commit(db);return record(row)
@router.patch('/vehicles/{uav_id}')
def availability(uav_id:str,body:Availability,db:Db,user:Identity):
    check(user,True);row=db.scalar(select(UAV).where(UAV.id==uav_id).with_for_update())
    if not row:raise HTTPException(404,'UAV not found')
    lease=db.get(VehicleLease,row.id)
    if lease and lease.mission_id:raise HTTPException(409,'Wait for the active mission to finish')
    row.active=body.active;audit(db,user.id,'fleet_availability_changed:'+row.id);commit(db);return record(row)


@router.get('/vehicles/{uav_id}')
def vehicle_details(uav_id:str,db:Db,user:Identity):
    check(user)
    row=db.get(UAV,uav_id)
    if not row:raise HTTPException(404,'UAV not found')
    kind=db.get(UAVType,row.type_id)
    total,started,completed,last_started=db.execute(select(
        func.count(Mission.id),
        func.count(Mission.started_at),
        func.count(Mission.id).filter(Mission.state=='COMPLETED'),
        func.max(Mission.started_at),
    ).where(Mission.uav_id==uav_id)).one()
    attempts=db.scalar(select(func.count(SurveyAttempt.id)).where(SurveyAttempt.uav_id==uav_id))
    return {**record(row),'type':record(kind),'usage':{
        'missions_planned':total,'missions_started':started,'missions_completed':completed,
        'survey_attempts':attempts,'last_started_at':last_started,
    }}
