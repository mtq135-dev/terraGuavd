# Experimental synthetic-feature detection processor

processing.py implements an explicit synthetic-fixture baseline for the connected simulation prototype. It validates finite normalized GPR response, metal response and quality in [0,1], requires synthetic provenance and rejects quality below 0.8. Its weighted feature score is experimental, not a calibrated mine probability. Targets above the prototype threshold retain observation ID, processing version, position, simulated flag and timestamp; nearby repeated samples are deduplicated by the backend. Analyst reviews remain assessments rather than confirmation.

Sensor fixtures are opt-in per mission and are not physical GPR waveforms or a simulation of electromagnetic propagation. The engine has not been trained/validated on real landmine measurements. No camera input, images, verified-mine classification or clearance claim is supported.

The separate experimental coverage predicate checks quality, relative altitude and speed. PostGIS in backend/app/coverage.py buffers valid sensor observations in meters, unions/clips footprints and records partial coverage. Flight tracks alone contribute zero coverage. A real sensor model, footprint calibration, quality validation, georeferencing/error bounds and field evaluation are required before any physical survey use.
# Mock label examples

Fixture version `demo/2` cycles through predefined Potential Mine, Metallic Object, Unknown and Rock examples with varied normalized features. `mock_classification()` only accepts synthetic-fixture provenance and copies these demonstration labels into new detection records; it does not infer object type from a physical sensor. The feature score, minimum candidate threshold, quality checks and coverage profile are unchanged. Existing records and processing versions are retained. Classification is included in mission CSV exports. The web list marks every result as MOCK DATA / UNVERIFIED.

