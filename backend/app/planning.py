"""Read-only survey-lane preview adapted from gradProjectPrototype's scanline method.
Authoritative containment remains PostGIS; preview never persists, reserves or flies.
"""
import json
import math
from types import SimpleNamespace
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import text
from .models import User
from .security import Db,current_user,effective_permissions
from .survey_areas import check_mission_area
from .fleet import vehicle_runtime
from .simulation_plan import simulation_home

router=APIRouter(prefix='/api/v1/plans')
class PreviewInput(BaseModel):
    assignment_id:str=Field(min_length=1,max_length=36)
    uav_id:str=Field(min_length=1,max_length=40)
    boundary:list[tuple[float,float]]=Field(min_length=4,max_length=101)
    altitude_m:float=Field(default=5,ge=2,le=8,allow_inf_nan=False)
    speed_m_s:float=Field(default=2,ge=.5,le=3,allow_inf_nan=False)
    spacing_m:float=Field(default=5,ge=1,le=50,allow_inf_nan=False)
    @field_validator('boundary')
    @classmethod
    def valid(cls,points):
        if points[0]!=points[-1] or any(not math.isfinite(x) or not math.isfinite(y) or not -180<=x<=180 or not -85<=y<=85 for x,y in points):
            raise ValueError('Use a closed ring of finite [longitude,latitude] coordinates')
        if max(x for x,y in points)-min(x for x,y in points)>180:raise ValueError('Antimeridian outlines are not supported')
        return points


def survey_lanes(ring,spacing):
    # Reference flight.py: horizontal scanlines clipped to polygon crossings.
    # A centimetre inset avoids floating-point ambiguity on the polygon boundary.
    lon0,lat0=ring[0]
    sx=111195*math.cos(math.radians(lat0));sy=111195
    xy=[((x-lon0)*sx,(y-lat0)*sy) for x,y in ring[:-1]]
    lo=min(y for x,y in xy);hi=max(y for x,y in xy)
    count=max(1,math.ceil((hi-lo)/spacing))
    if count>50:raise ValueError('Too many survey lanes. Increase lane spacing or split the sector (maximum 100 waypoints).')
    route=[];lanes=0
    for k in range(count):
        y=lo+(k+.5)*(hi-lo)/count
        crossings=[]
        for (x1,y1),(x2,y2) in zip(xy,xy[1:]+xy[:1]):
            if (y1>y)!=(y2>y):crossings.append(x1+(y-y1)*(x2-x1)/(y2-y1))
        crossings.sort()
        pieces=[(a+.02,b-.02) for a,b in zip(crossings[::2],crossings[1::2]) if b-a>=1]
        if k%2:pieces=[(b,a) for a,b in reversed(pieces)]
        for a,b in pieces:
            route.extend([(lon0+a/sx,lat0+y/sy),(lon0+b/sx,lat0+y/sy)]);lanes+=1
    if not 2<=len(route)<=100:raise ValueError('Use a wider sector or larger lane spacing; the route must have 2–100 waypoints.')
    length=sum(math.hypot((b[0]-a[0])*sx,(b[1]-a[1])*sy) for a,b in zip(route,route[1:]))
    return route,lanes,length

@router.post('/preview')
def preview(body:PreviewInput,db:Db,user:Annotated[User,Depends(current_user)]):
    if user.role!='mission_operator' or 'missions:plan' not in effective_permissions(user):raise HTTPException(403,'Assigned Mission Operator planning permission required')
    geometry={'type':'Polygon','coordinates':[body.boundary]}
    mission=SimpleNamespace(assignment_id=body.assignment_id,operator_id=user.id,boundary=geometry)
    valid,area=db.execute(text('SELECT ST_IsValid(g),CASE WHEN ST_IsValid(g) THEN ST_Area(g::geography) ELSE 0 END FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) g) p'),{'g':json.dumps(geometry)}).one()
    if not valid or area<=0:return {'ok':False,'problems':['Draw a valid nonzero-area outline.'],'path':[]}
    check_mission_area(db,mission)
    vehicle_runtime(db,body.uav_id)
    try:path,lanes,length=survey_lanes(body.boundary,body.spacing_m)
    except ValueError as error:return {'ok':False,'problems':[str(error)],'path':[]}
    try:home=simulation_home(path)
    except HTTPException as error:return {'ok':False,'problems':[error.detail],'path':[]}
    inside=db.execute(text('SELECT ST_Covers(ST_SetSRID(ST_GeomFromGeoJSON(:g),4326),ST_SetSRID(ST_GeomFromGeoJSON(:r),4326))'),{'g':json.dumps(geometry),'r':json.dumps({'type':'LineString','coordinates':path})}).scalar_one()
    if not inside:return {'ok':False,'problems':['This concave outline needs turns outside its boundary. Split it into simpler sectors; no outside route will be saved.'],'path':[]}
    return {'ok':True,'problems':[],'path':path,'lanes':lanes,'area_m2':area,'path_length_m':length,'estimated_duration_s':length/body.speed_m_s,'simulation_home':home,'notice':'The isolated simulator origin is set near the first survey waypoint on explicit mission start. Planning estimates are not completed coverage.'}
