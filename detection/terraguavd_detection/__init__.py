"""Sensor-only detection contract; no inference implementation."""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol


@dataclass(frozen=True)
class SensorObservation:
    observed_at: datetime
    longitude: float
    latitude: float
    sensor: Literal["gpr", "metal_detector"]
    values: tuple[float, ...]
    simulated: bool


@dataclass(frozen=True)
class PotentialTarget:
    confidence: float
    processing_version: str
    source_observation_ids: tuple[str, ...]
    simulated: bool
    classification: Literal["potential_target"] = "potential_target"


class DetectionEngine(Protocol):
    def process(self, observations: list[SensorObservation]) -> list[PotentialTarget]: ...
