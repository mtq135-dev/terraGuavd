import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text, delete

from .models import AuditEvent, AuthSession, User
from . import operations
from . import survey_areas
from .db import engine
from .schemas import Dashboard, Identity, Role, SessionToken
from .security import effective_permissions, DUMMY_HASH, ROLE_PERMISSIONS, Db, audit, bearer, current_user, digest, passwords, require

@asynccontextmanager
async def lifespan(app):
    if engine.dialect.name == 'postgresql':
        operations.recover()
    try:
        yield
    finally:
        if engine.dialect.name == 'postgresql':
            operations.recover()


app = FastAPI(title="TerraGuavd API", version="0.2.0", description="Isolated SITL survey prototype. No physical UAV integration.",lifespan=lifespan)
# Static command endpoints must precede the parameterized command fallback.
operations.router.routes.sort(key=lambda route: '{command}' in route.path)
app.include_router(operations.router)
app.include_router(survey_areas.router)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


def identity(user: User):
    return {"id": user.id, "username": user.username, "role": user.role,
            "permissions": sorted(effective_permissions(user)), "active": user.active,
            "denied_permissions": user.denied_permissions or []}


@app.get("/api/v1/health/live")
def live():
    return {"status": "ok", "mode": "simulation-only"}


@app.get("/api/v1/health/ready")
def ready(db: Db):
    try:
        db.execute(select(User.id).limit(1))
        version = db.execute(text("SELECT PostGIS_Version()" )).scalar_one()
    except Exception:
        raise HTTPException(503, "Database, migrations or PostGIS unavailable") from None
    return {"status": "ready", "postgis": version}


@app.post("/api/v1/auth/login", response_model=SessionToken)
def login(body: Login, db: Db, response: Response):
    user = db.scalar(select(User).where(User.username == body.username))
    valid = passwords.verify(body.password, user.password_hash if user else DUMMY_HASH)
    if not valid or not user or not user.active:
        audit(db, None, "login_failed")
        db.commit()
        raise HTTPException(401, "Invalid credentials")
    token = secrets.token_urlsafe(48)
    db.add(AuthSession(token_hash=digest(token), user_id=user.id, expires_at=datetime.now(UTC) + timedelta(minutes=30)))
    audit(db, user.id, "login_succeeded")
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": token, "token_type": "bearer", "expires_in": 1800}


@app.get("/api/v1/auth/me", response_model=Identity)
def me(user: Annotated[User, Depends(current_user)]):
    return identity(user)


@app.post("/api/v1/auth/logout", status_code=204)
def logout(db: Db, user: Annotated[User, Depends(current_user)], credentials=Depends(bearer)):
    db.delete(db.get(AuthSession, digest(credentials.credentials)))
    audit(db, user.id, "logout")
    db.commit()


@app.get("/api/v1/dashboards/{role}", response_model=Dashboard)
def dashboard(role: Role, db: Db, user: Annotated[User, Depends(current_user)]):
    if f"dashboard:{role}" not in effective_permissions(user):
        raise HTTPException(403, "Permission denied")
    missions=operations.visible_missions(db,user)
    ids=[row.id for row in missions]
    from .operations_models import Detection, SurveyAttempt, Observation
    detections=db.scalars(select(Detection).where(Detection.mission_id.in_(ids))).all()
    surveys=db.scalars(select(SurveyAttempt).where(SurveyAttempt.mission_id.in_(ids))).all()
    latest=db.scalar(select(Observation).where(Observation.mission_id.in_(ids)).order_by(Observation.created_at.desc()).limit(1))
    return {"role": role, "mode": "simulation-only", "missions": [operations.serialize(row) for row in missions], "potential_detections": [operations.serialize(row) for row in detections],
            "survey_attempts": [operations.serialize(row) for row in surveys], "alerts": operations.alert_list(db,user), "telemetry": operations.serialize(latest) if latest else None, "simulation": "px4-gazebo", "detection_engine": "experimental synthetic-feature baseline",
            "notice": "Surveyed does not mean cleared or safe. Potential detections are unverified."}


@app.get("/api/v1/admin/users", response_model=list[Identity])
def users(db: Db, user: Annotated[User, Depends(require("users:read"))], offset: int = 0):
    if offset < 0:
        raise HTTPException(422, "Offset must be nonnegative")
    return [identity(item) for item in db.scalars(select(User).order_by(User.username).offset(offset).limit(50))]


@app.get('/api/v1/admin/audit')
def audit_records(db: Db,user: Annotated[User,Depends(require('audit:read'))],offset: int=0):
    if offset<0:
        raise HTTPException(422,'Offset must be nonnegative')
    return [operations.serialize(row) for row in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).offset(offset).limit(100))]


class AccessUpdate(BaseModel):
    role: Role
    active: bool
    denied_permissions: list[str] = Field(default_factory=list, max_length=30)


@app.get('/api/v1/admin/roles')
def role_catalog(user: Annotated[User, Depends(require('users:read'))]):
    return {role: sorted(permissions) for role, permissions in ROLE_PERMISSIONS.items()}


@app.put('/api/v1/admin/users/{user_id}/access', response_model=Identity)
def update_access(user_id: str, body: AccessUpdate, db: Db,
                  actor: Annotated[User, Depends(require('users:read'))]):
    # Serialize account administration, including concurrent last-admin changes.
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(748219)'))
    actor = db.scalar(select(User).where(User.id == actor.id).execution_options(populate_existing=True))
    if not actor.active or actor.role != 'administrator' or 'users:read' not in effective_permissions(actor):
        raise HTTPException(403, 'Administrator access required')
    target = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not target:
        raise HTTPException(404, 'Account not found')
    if user_id == actor.id:
        raise HTTPException(409, 'Use another administrator to change your own access')
    denied = set(body.denied_permissions)
    if not denied <= ROLE_PERMISSIONS[body.role]:
        raise HTTPException(422, 'Restrictions must belong to the selected role')
    if body.role == 'administrator' and 'users:read' in denied:
        raise HTTPException(422, 'Administrators must retain account administration permission')
    if target.role == 'administrator' and target.active and (not body.active or body.role != 'administrator'):
        others = db.scalars(select(User).where(User.role == 'administrator', User.active == True, User.id != user_id)).all()
        if not any('users:read' in effective_permissions(item) for item in others):
            raise HTTPException(409, 'Keep at least one active administrator')
    from .operations_models import Mission
    from .survey_areas import ACTIVE
    if db.scalar(select(Mission.id).where(Mission.operator_id == user_id, Mission.state.in_(ACTIVE)).limit(1)):
        raise HTTPException(409, 'Wait for the assigned active mission to finish before changing access')
    target.role, target.active, target.denied_permissions = body.role, body.active, sorted(denied)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    audit(db, actor.id, f'access_updated:{user_id}')
    db.commit()
    return identity(target)
