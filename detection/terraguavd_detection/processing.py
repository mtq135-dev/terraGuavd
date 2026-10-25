"""Experimental normalized-feature baseline. Never a mine-verification model."""
from math import isfinite

VERSION = "normalized-feature-baseline/0.1-experimental"
COVERAGE_VERSION = "synthetic-footprint-2m/0.1-experimental"


def score(features: dict) -> float | None:
    values = [features.get(key) for key in ("gpr_response", "metal_response", "quality")]
    if any(not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1 for value in values):
        raise ValueError("Normalized features and quality must be finite values in [0,1]")
    if features.get("provenance") != "synthetic-fixture":
        raise ValueError("This prototype processes synthetic-fixture observations only")
    gpr, metal, quality = values
    if quality < .8:
        return None
    confidence = round((.6 * gpr + .4 * metal) * quality, 4)
    return confidence if confidence >= .65 else None


def valid_footprint(features: dict | None, altitude: float, speed: float) -> bool:
    return bool(features and features.get("quality", 0) >= .8 and
                features.get("provenance") == "synthetic-fixture" and
                1 <= altitude <= 8 and 0 <= speed <= 3)


def fixture(sequence: int) -> dict:
    # Deterministic synthetic normalized features, not emulated physical GPR.
    peak = sequence % 12 in (6, 7)
    examples = [('potential_mine', .96, .85), ('metallic_object', .67, 1),
                ('potential_mine', 1, .9), ('unknown', .701, .66),
                ('potential_mine', .88, .84), ('rock', .70, .68)]
    label, gpr, metal = examples[(sequence // 12) % len(examples)]
    return {"gpr_response": gpr if peak else .12, "metal_response": metal if peak else .18,
            "quality": .95, "provenance": "synthetic-fixture", "fixture_version": "demo/2",
            "mock_classification": label if peak else 'unknown'}


def mock_classification(features: dict) -> str:
    """Predefined demonstration labels only; never a sensor-derived classifier."""
    if features.get('provenance') != 'synthetic-fixture':
        raise ValueError('Mock labels require synthetic-fixture provenance')
    label = features.get('mock_classification')
    return label if label in {'potential_mine','metallic_object','unknown','rock'} else 'potential_target'
