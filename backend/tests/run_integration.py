"""Create and remove only a uniquely named local disposable test database."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sitl',action='store_true',help='Execute a real isolated PX4/Gazebo simulated mission')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    load_dotenv(root/'.env')
    url=make_url(os.environ['DATABASE_URL'])
    if url.get_backend_name()!='postgresql' or url.host not in {'127.0.0.1','localhost'}:
        parser.error('Integration helper supports the local development PostgreSQL instance only')
    if args.sitl:
        import httpx
        response=httpx.get('http://127.0.0.1:8090/status',headers={'Authorization':'Bearer '+os.environ['SIMULATION_SECRET']},timeout=5,trust_env=False)
        response.raise_for_status()
        if response.json().get('armed'):
            parser.error('An existing simulated flight is active; finish it before running tests')
    name='terraguavd_test_'+uuid4().hex
    admin=create_engine(url,isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE {name}'))
    try:
        env={**os.environ,'TEST_POSTGIS_URL':url.set(database=name).render_as_string(hide_password=False)}
        if args.sitl:
            env['RUN_PX4_E2E']='1'
        else:
            env.pop('RUN_PX4_E2E',None)
        result=subprocess.run([sys.executable,'-m','pytest','tests/test_postgis.py','tests/test_workflows.py','-s'],cwd=root/'backend',env=env)
        return result.returncode
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE {name} WITH (FORCE)'))
        admin.dispose()


if __name__=='__main__':
    sys.exit(main())
