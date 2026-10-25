"""Manual browser QA fixture. Isolated disposable DB; never seed runtime accounts.

Run from backend: python tests/preview.py (requires running local Compose DB).
Test-only credentials match test_auth.py. Database is removed on clean shutdown.
"""
import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    base = make_url(os.environ["DATABASE_URL"])
    name = "terraguavd_browser_test"
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        # Refuse to overwrite any existing database, including a prior fixture.
        connection.execute(text(f"CREATE DATABASE {name}"))
    os.environ["DATABASE_URL"] = base.set(database=name).render_as_string(hide_password=False)
    try:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
        from app.db import SessionLocal, engine
        from app.models import User
        from app.security import ROLE_PERMISSIONS, passwords
        with SessionLocal() as db:
            for role in ROLE_PERMISSIONS:
                db.add(User(id=role, username=role, role=role, password_hash=passwords.hash("Testing-password-123")))
            db.commit()
        print("Browser QA only: isolated disposable database, test-role accounts.", flush=True)
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
        engine.dispose()
    finally:
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE {name} WITH (FORCE)"))
        admin.dispose()


if __name__ == "__main__":
    main()
