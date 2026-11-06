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
    parser.add_argument('--multi-sitl',action='store_true',help='Execute two concurrent isolated simulated missions')
    parser.add_argument('--fleet-matrix',action='store_true',help='Run 1/2/3-UAV and mixed-model flight scenarios')
    parser.add_argument('--relocated-sitl',action='store_true',help='Fly an isolated mission near a Saudi origin instead of the default world origin')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    load_dotenv(root/'.env')
    url=make_url(os.environ['DATABASE_URL'])
    if url.get_backend_name()!='postgresql' or url.host not in {'127.0.0.1','localhost'}:
        parser.error('Integration helper supports the local development PostgreSQL instance only')
    if args.sitl or args.multi_sitl or args.fleet_matrix or args.relocated_sitl:
        import httpx
        response=httpx.get('http://127.0.0.1:8090/status',headers={'Authorization':'Bearer '+os.environ['SIMULATION_SECRET']},timeout=5,trust_env=False)
        response.raise_for_status()
        if response.json().get('armed'):
            parser.error('An existing simulated flight is active; finish it before running tests')
        if args.multi_sitl or args.fleet_matrix:
            response=httpx.get('http://127.0.0.1:8091/status',headers={'Authorization':'Bearer '+os.environ['SIMULATION_SECRET']},timeout=5,trust_env=False)
            response.raise_for_status()
            if response.json().get('armed'):parser.error('The second simulated vehicle is armed')
        if args.fleet_matrix:
            response=httpx.get('http://127.0.0.1:8092/status',headers={'Authorization':'Bearer '+os.environ['SIMULATION_SECRET']},timeout=5,trust_env=False)
            response.raise_for_status()
            if response.json().get('armed'):parser.error('The third simulated vehicle is armed')
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
        if args.multi_sitl:env['RUN_PX4_MULTI_E2E']='1'
        else:env.pop('RUN_PX4_MULTI_E2E',None)
        if args.fleet_matrix:env['RUN_FLEET_MATRIX']='1'
        else:env.pop('RUN_FLEET_MATRIX',None)
        if args.relocated_sitl:env['RUN_PX4_HOME_E2E']='1'
        else:env.pop('RUN_PX4_HOME_E2E',None)
        result=subprocess.run([sys.executable,'-m','pytest','tests/test_postgis.py','tests/test_workflows.py','tests/test_fleet_matrix.py','-s'],cwd=root/'backend',env=env)
        return result.returncode
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE {name} WITH (FORCE)'))
        admin.dispose()


if __name__=='__main__':
    sys.exit(main())
