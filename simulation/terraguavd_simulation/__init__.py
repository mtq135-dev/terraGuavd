"""Simulation integration contracts. No flight implementation or process startup."""
from typing import Protocol


class SimulationRuntime(Protocol):
    async def ensure_started(self) -> None:
        """Start/reuse simulator only; never arm, upload, or take off."""
        ...

    async def wait_for_vehicle(self, timeout_seconds: float) -> None:
        """Require actual MAVLink readiness with a bounded timeout."""
        ...

    async def stop(self) -> None: ...
