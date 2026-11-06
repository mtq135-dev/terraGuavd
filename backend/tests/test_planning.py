import pytest
from app.planning import survey_lanes,PreviewInput
from pydantic import ValidationError

def test_rectangle_scanline_count_spacing_and_alternation():
    ring=[(8.5453,47.3976),(8.5459,47.3976),(8.5459,47.39794),(8.5453,47.39794),(8.5453,47.3976)]
    path,lanes,length=survey_lanes(ring,5)
    assert len(path)==2*lanes and 2<=len(path)<=100 and length>0
    assert path[0][0]<path[1][0] and path[2][0]>path[3][0]
    assert all(8.5453<x<8.5459 and 47.3976<y<47.39794 for x,y in path)

def test_too_many_lanes_and_tiny_sector_are_rejected():
    with pytest.raises(ValueError,match='Too many'):survey_lanes([(0,0),(.01,0),(.01,.01),(0,.01),(0,0)],1)
    with pytest.raises(ValueError):survey_lanes([(0,0),(.00000001,0),(.00000001,.00000001),(0,0)],5)

def test_preview_rejects_nonfinite_and_out_of_bounds_settings():
    with pytest.raises(ValidationError):PreviewInput(assignment_id='a',uav_id='u',boundary=[(0,0),(1,0),(float('nan'),1),(0,0)])
    with pytest.raises(ValidationError):PreviewInput(assignment_id='a',uav_id='u',boundary=[(0,0),(1,0),(1,1),(0,0)],spacing_m=0)


def test_simulation_origin_follows_route_and_keeps_local_limits():
    from app.simulation_plan import simulation_home
    from fastapi import HTTPException
    assert simulation_home([(47.16,22.77),(47.1601,22.7701)])=={'latitude':22.77,'longitude':47.16}
    with pytest.raises(HTTPException):simulation_home([(47.16,22.77),(47.20,22.77)])
