"""Only the locally configured, authenticated, isolated SITL service is reachable."""
import os
import httpx


class SimulationRuntime:
    def call(self, path: str, body: dict | None = None):
        secret = os.environ.get('SIMULATION_SECRET')
        if not secret:
            raise RuntimeError('Simulation service is not configured. Run setup.ps1.')
        try:
            with httpx.Client(base_url='http://127.0.0.1:8090', timeout=45, trust_env=False,
                              headers={'Authorization': f'Bearer {secret}'}) as client:
                response = client.get(path) if body is None else client.post(path, json=body)
                response.raise_for_status()
                result = response.json()
                if result.get('runtime') != 'px4-gazebo' or result.get('simulated') is not True:
                    raise RuntimeError('Only the isolated PX4/Gazebo simulator is supported')
                return result
        except httpx.HTTPError as exc:
            detail = exc.response.text[:250] if isinstance(exc, httpx.HTTPStatusError) else 'Simulator service unavailable'
            raise RuntimeError(detail) from exc


runtime = SimulationRuntime()
