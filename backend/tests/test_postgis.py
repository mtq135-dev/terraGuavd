"""Explicit opt-in integration test against a disposable PostgreSQL/PostGIS DB."""
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import User
from app.security import passwords


@pytest.mark.skipif(not os.getenv("TEST_POSTGIS_URL"), reason="Set TEST_POSTGIS_URL to an empty disposable PostGIS database")
def test_migration_postgis_and_append_only_audit():
    url = os.environ["TEST_POSTGIS_URL"]
    env = {**os.environ, "DATABASE_URL": url}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True)
    engine = create_engine(url)
    with engine.begin() as db:
        assert db.execute(text("SELECT PostGIS_Version()")).scalar_one()
        assert db.execute(text("SELECT ST_SRID(ST_GeomFromText('POINT(0 0)',4326))")).scalar_one() == 4326
        db.execute(text("INSERT INTO audit_events VALUES ('integration',NULL,'integration',now())"))
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as db:
            db.execute(text("DELETE FROM audit_events WHERE id='integration'"))
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add(User(id="integration-admin", username="integration-admin", role="administrator", password_hash=passwords.hash("Only-for-disposable-test-123")))
        db.commit()

    def integration_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = integration_db
    try:
        with TestClient(app) as api:
            assert api.get("/api/v1/health/ready").status_code == 200
            login = api.post("/api/v1/auth/login", json={"username": "integration-admin", "password": "Only-for-disposable-test-123"})
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            assert api.get("/api/v1/admin/users", headers=headers).status_code == 200
            assert api.get("/api/v1/dashboards/supervisor", headers=headers).status_code == 403
            assert api.post("/api/v1/auth/logout", headers=headers).status_code == 204
            assert api.get("/api/v1/auth/me", headers=headers).status_code == 401
    finally:
        app.dependency_overrides.clear()
    # Downgrade drops test tables, so use a disposable database only.
    subprocess.run([sys.executable, "-m", "alembic", "downgrade", "base"], env=env, check=True)
    engine.dispose()
