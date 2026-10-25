import json
from sqlalchemy import text
from terraguavd_detection.processing import COVERAGE_VERSION, valid_footprint


def store_position(db, observation):
    valid = valid_footprint(observation.sensor, observation.altitude_m, observation.speed_m_s)
    db.execute(text('''UPDATE observations SET
      position=ST_SetSRID(ST_MakePoint(:lon,:lat),4326),
      footprint=CASE WHEN :valid THEN ST_Buffer(ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography,2)::geometry ELSE NULL END
      WHERE id=:id'''), {'lon':observation.longitude,'lat':observation.latitude,'id':observation.id,'valid':valid})


def calculate(db, mission_id):
    result = db.execute(text('''WITH covered AS (
      SELECT ST_Intersection(m.planned_geometry,ST_Union(o.footprint)) geom, m.planned_geometry planned
      FROM missions m LEFT JOIN observations o ON o.mission_id=m.id
      WHERE m.id=:id GROUP BY m.planned_geometry)
      SELECT ST_AsGeoJSON(geom), CASE WHEN geom IS NULL THEN 0 ELSE
        LEAST(100,100*ST_Area(geom::geography)/NULLIF(ST_Area(planned::geography),0)) END FROM covered'''), {'id':mission_id}).one()
    return {'geometry':json.loads(result[0]) if result[0] else {'type':'GeometryCollection','geometries':[]},
            'coverage_percent':round(float(result[1] or 0),2), 'algorithm_version':COVERAGE_VERSION,
            'simulated':True, 'notice':'Experimental synthetic sensor-footprint coverage. Surveyed does not mean cleared or safe.'}
