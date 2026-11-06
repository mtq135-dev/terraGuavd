"""Only the locally configured, authenticated, isolated SITL service is reachable."""
import os
import httpx


class SimulationRuntime:
    def __init__(self, port=8090):
        if port not in {8090,8091,8092}:
            raise ValueError('Only configured isolated runtime ports are supported')
        self.port=port
    def call(self, path: str, body: dict | None = None):
        secret = os.environ.get('SIMULATION_SECRET')
        if not secret:
            raise RuntimeError('Simulation service is not configured. Run setup.ps1.')
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{self.port}', timeout=45, trust_env=False,
                              headers={'Authorization': f'Bearer {secret}'}) as client:
                response = client.get(path) if body is None else client.post(path, json=body)
                response.raise_for_status()
                result = response.json()
                if result.get('runtime') != 'px4-gazebo' or result.get('simulated') is not True:
                    raise RuntimeError('Only the isolated PX4/Gazebo simulator is supported')
                return result
        except httpx.HTTPError as exc:
            detail = 'Simulator service unavailable'
            if isinstance(exc,httpx.HTTPStatusError):
                try:detail=exc.response.json().get('detail','Simulator request rejected')
                except ValueError:detail=exc.response.text[:250]
                if not isinstance(detail,str):detail='Simulator request rejected'
                detail=detail[:250]
            raise RuntimeError(detail) from exc


runtime = SimulationRuntime()
secondary_runtime = SimulationRuntime(8091)
third_runtime = SimulationRuntime(8092)
