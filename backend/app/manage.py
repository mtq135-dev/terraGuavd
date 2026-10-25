"""Explicit local provisioning; never create default accounts at startup."""
import argparse
from getpass import getpass
from uuid import uuid4

from sqlalchemy import select

from .db import SessionLocal
from .models import User
from .security import ROLE_PERMISSIONS, audit, passwords


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("role", choices=ROLE_PERMISSIONS)
    args = parser.parse_args()
    if not 1 <= len(args.username) <= 80:
        parser.error("Username must be 1-80 characters")
    password = getpass("New password (12-256 characters): ")
    if not 12 <= len(password) <= 256 or password != getpass("Confirm password: "):
        parser.error("Passwords must match and be 12-256 characters")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == args.username)):
            parser.error("User already exists")
        user = User(id=str(uuid4()), username=args.username, role=args.role, password_hash=passwords.hash(password))
        db.add(user)
        audit(db, user.id, "account_provisioned_locally")
        db.commit()
    print("Account created")


if __name__ == "__main__":
    main()
