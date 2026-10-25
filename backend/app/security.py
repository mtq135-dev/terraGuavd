import hashlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuditEvent, AuthSession, User

ROLE_PERMISSIONS = {
    "administrator": {"dashboard:administrator", "users:read", "system:read", "audit:read", "missions:read", "reports:read"},
    "mission_operator": {"dashboard:mission_operator", "missions:plan", "missions:read", "missions:execute", "reports:read", "survey_areas:read"},
    "detection_analyst": {"dashboard:detection_analyst", "detections:review", "missions:read", "reports:read"},
    "supervisor": {"dashboard:supervisor", "missions:read", "missions:assign", "reports:read", "survey_areas:read", "survey_areas:manage"},
    "field_personnel": {"dashboard:field_personnel", "missions:assigned:read", "stop:request"},
}
def effective_permissions(user):
    return ROLE_PERMISSIONS.get(user.role, set()) - set(user.denied_permissions or [])


passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("unused-timing-equalization-password")
bearer = HTTPBearer(auto_error=False)
Db = Annotated[Session, Depends(get_db)]


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def audit(db: Session, actor: str | None, action: str):
    db.add(AuditEvent(id=str(uuid4()), actor=actor, action=action, created_at=datetime.now(UTC)))


def current_user(db: Db, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    session = db.get(AuthSession, digest(credentials.credentials)) if credentials else None
    # SQLite drops timezone metadata; production Postgres retains UTC timestamps.
    if not session or session.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Account unavailable")
    return user


def require(permission: str):
    def check(user: Annotated[User, Depends(current_user)]):
        if permission not in effective_permissions(user):
            raise HTTPException(403, "Permission denied")
        return user
    return check
