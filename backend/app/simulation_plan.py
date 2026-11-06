"""Fixed isolated-world origin and bounded local route policy."""
from fastapi import HTTPException

def simulation_home(waypoints):
    if len(waypoints)<2:raise HTTPException(422,'At least two survey waypoints are required.')
    lon,lat=waypoints[0]
    if any(abs(y-lat)>.004 or abs(x-lon)>.006 for x,y in waypoints):
        raise HTTPException(422,'This sector is too large for one isolated simulation. Split it into smaller sectors near their first waypoint.')
    return {'latitude':lat,'longitude':lon}
