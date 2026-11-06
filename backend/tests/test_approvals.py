"""Boundary authorization API tests with spatial operations stubbed for SQLite."""

from datetime import UTC, datetime

from app import mission_approvals, operations
from app.models import User
from app.operations_models import Mission, SurveyAreaAssignment, VehicleLease
from app.security import passwords


def test_outside_approval_is_scoped_and_stale_start_never_queues(client, monkeypatch):
    api, sessions = client
    now = datetime.now(UTC)
    parent_boundary = {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [0, 1], [0, 0]]]}
    boundary = {'type': 'Polygon', 'coordinates': [[[0, 0], [2, 0], [0, 2], [0, 0]]]}
    with sessions.begin() as db:
        db.add(User(id='unrelated', username='unrelated', role='supervisor',
                    password_hash=passwords.hash('Testing-password-123')))
        db.add(SurveyAreaAssignment(id='parent', name='Assigned area', description='',
            operator_id='mission_operator', created_by='supervisor', boundary=parent_boundary,
            created_at=now, updated_at=now))
        db.flush()
        db.add(Mission(id='outside', name='Outside draft', area_id='demo', assignment_id='parent',
                       operator_id='mission_operator', boundary=boundary, waypoints=[[0, 0], [1, 0]],
                       altitude_m=5, speed_m_s=2, created_at=now))
        db.add(VehicleLease(id='sitl-01'))

    def spatial(*_):
        return {'required': True, 'outside_geometry': boundary, 'outside_m2': 20.0}

    def geometry(db, mission, *, require_approval=True):
        parent = db.get(SurveyAreaAssignment, mission.assignment_id)
        if require_approval:
            mission_approvals.enforce(db, mission, parent)
        return parent

    monkeypatch.setattr(mission_approvals, 'spatial_context', spatial)
    monkeypatch.setattr(operations, 'validate_geometry', geometry)
    queued = []
    monkeypatch.setattr(operations, 'schedule', queued.append)

    def sign_in(username):
        response = api.post('/api/v1/auth/login', json={'username': username, 'password': 'Testing-password-123'})
        assert response.status_code == 200
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    op, sup, other, admin = [sign_in(u) for u in ('mission_operator', 'supervisor', 'unrelated', 'administrator')]
    mission = '/api/v1/missions/outside'
    assert api.post(mission + '/validate', headers=op).status_code == 422
    assert api.post(mission + '/start', headers=op).status_code == 409
    assert api.post(mission + '/approval-requests', headers=op, json={'reason': '   '}).status_code == 422
    request = api.post(mission + '/approval-requests', headers=op, json={'reason': 'Complete adjacent survey'})
    assert request.status_code == 200, request.text
    assert request.json()['status'] == 'Pending'
    request_id = request.json()['request']['id']
    decision = f'/api/v1/mission-approvals/{request_id}/decision'
    assert api.get('/api/v1/mission-approvals', headers=other).json() == []
    assert api.post(decision, headers=other, json={'decision': 'Approved'}).status_code == 404
    for actor in (op, admin):
        assert api.post(decision, headers=actor, json={'decision': 'Approved'}).status_code == 403
    assert api.post(decision, headers=sup, json={'decision': 'Rejected'}).status_code == 422
    assert api.post(decision, headers=sup, json={'decision': 'Approved'}).json()['status'] == 'Approved'
    assert api.post(mission + '/validate', headers=op).status_code == 200
    assert not queued

    with sessions.begin() as db:
        db.get(Mission, 'outside').speed_m_s = 2.5
    assert api.get(mission + '/approval', headers=op).json()['status'] == 'Invalidated'
    assert api.post(mission + '/start', headers=op).status_code == 422
    assert not queued
    with sessions() as db:
        assert db.get(VehicleLease, 'sitl-01').mission_id is None
