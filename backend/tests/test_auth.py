from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import AuditEvent, AuthSession, User
from app.security import ROLE_PERMISSIONS


def login(client, role):
    result = client.post("/api/v1/auth/login", json={"username": role, "password": "Testing-password-123"})
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


@pytest.mark.parametrize("role", ROLE_PERMISSIONS)
def test_permission_matrix(client, role):
    api, _ = client
    headers = login(api, role)
    assert api.get("/api/v1/auth/me", headers=headers).json()["role"] == role
    for dashboard in ROLE_PERMISSIONS:
        response = api.get(f"/api/v1/dashboards/{dashboard}", headers=headers)
        assert response.status_code == (200 if dashboard == role else 403)
    assert api.get("/api/v1/admin/users", headers=headers).status_code == (200 if role == "administrator" else 403)
    assert api.get("/api/v1/admin/audit", headers=headers).status_code == (200 if role == "administrator" else 403)
    if role != 'administrator':
        assert api.get('/api/v1/simulation/status',headers=headers).status_code==403
    assert not any("flight" in permission for permission in ROLE_PERMISSIONS[role])


def test_login_logout_and_hashes(client):
    api, factory = client
    headers = login(api, "administrator")
    with factory() as db:
        session = db.scalar(select(AuthSession))
        assert session.token_hash not in headers["Authorization"]
        assert db.get(User, "administrator").password_hash.startswith("$argon2")
    assert api.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 401
    with factory() as db:
        assert [event.action for event in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at))] == ["login_succeeded", "logout"]


def test_reject_invalid_expired_disabled_sessions(client):
    api, factory = client
    assert api.get("/api/v1/auth/me").status_code == 401
    assert api.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    for username in ["administrator", "unknown"]:
        assert api.post("/api/v1/auth/login", json={"username": username, "password": "wrong"}).status_code == 401
    headers = login(api, "administrator")
    with factory() as db:
        session = db.scalar(select(AuthSession))
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 401
    headers = login(api, "supervisor")
    with factory() as db:
        db.get(User, "supervisor").active = False
        db.commit()
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_permissions_read_from_database_not_token(client):
    api, factory = client
    headers = login(api, "administrator")
    with factory() as db:
        db.get(User, "administrator").role = "supervisor"
        db.commit()
    assert api.get("/api/v1/admin/users", headers=headers).status_code == 403


def test_empty_dashboard_and_no_flight_surface(client):
    api, _ = client
    headers = login(api, "mission_operator")
    data = api.get("/api/v1/dashboards/mission_operator", headers=headers).json()
    assert data["potential_detections"] == []
    assert data["survey_attempts"] == []
    assert data["mode"] == "simulation-only"
    assert api.post("/api/v1/missions/1/start", headers=headers).status_code == 404
    assert api.get("/api/v1/health/ready").status_code == 503  # SQLite has no PostGIS

def test_admin_restricts_permissions_and_revokes_sessions(client):
    api, factory = client
    admin = login(api, 'administrator')
    analyst = login(api, 'detection_analyst')
    body = {'role': 'detection_analyst', 'active': True, 'denied_permissions': ['detections:review']}
    assert api.put('/api/v1/admin/users/detection_analyst/access', headers=analyst, json=body).status_code == 403
    result = api.put('/api/v1/admin/users/detection_analyst/access', headers=admin, json=body)
    assert result.status_code == 200
    assert 'detections:review' not in result.json()['permissions']
    assert api.get('/api/v1/auth/me', headers=analyst).status_code == 401
    analyst = login(api, 'detection_analyst')
    assert api.post('/api/v1/detections/missing/reviews', headers=analyst, json={'assessment':'inconclusive','notes':'Test restriction'}).status_code == 403
    body['active'] = False
    assert api.put('/api/v1/admin/users/detection_analyst/access', headers=admin, json=body).status_code == 200
    assert api.post('/api/v1/auth/login', json={'username':'detection_analyst','password':'Testing-password-123'}).status_code == 401
    with factory() as db:
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == 'access_updated:detection_analyst'))


def test_admin_role_changes_and_guardrails(client):
    api, _ = client
    admin = login(api, 'administrator')
    body = {'role':'supervisor','active':True,'denied_permissions':[]}
    assert api.put('/api/v1/admin/users/administrator/access',headers=admin,json=body).status_code == 409
    assert api.put('/api/v1/admin/users/detection_analyst/access',headers=admin,json={**body,'denied_permissions':['missions:execute']}).status_code == 422
    result = api.put('/api/v1/admin/users/detection_analyst/access',headers=admin,json=body)
    assert result.status_code == 200
    assert result.json()['role'] == 'supervisor'
    assert 'missions:execute' not in result.json()['permissions']
    assert api.put('/api/v1/admin/users/missing/access',headers=admin,json=body).status_code == 404
    assert 'mission_operator' in api.get('/api/v1/admin/roles',headers=admin).json()
