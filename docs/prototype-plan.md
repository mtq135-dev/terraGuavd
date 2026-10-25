# Connected prototype increment

Authorized by the user's request to complete mission execution, simulation, telemetry, detection, coverage and reports.

Status: implemented and locally tested for the connected simulation prototype. Native ARM64 PostGIS/PX4/Gazebo execution, WebSocket UI, synthetic processing, reviews, partial coverage/history and exports are verified; native Flutter/device and AMD64 runtime matrices remain unverified. See prototype-verification.md. Detector and footprint rules remain explicitly experimental and synthetic-only, not validated field detection.

1. Persist missions, assignments, waypoints, events, readings, potential targets, analyst assessments and immutable survey attempts using migration 0002.
2. Implement a server-side assigned-operator mission state machine with an exclusive vehicle lease, explicit start, bounded failures, pause/resume/cancel and restart interruption recovery.
3. Run an isolated PX4/Gazebo container behind an authenticated runtime adapter. Do not publish MAVLink ports or redirect MAVLink to the host. Runtime start never arms or executes a mission.
4. Stream actual SITL position/altitude/battery/status to authenticated clients. Synthetic sensor observations are opt-in simulation fixtures, labelled throughout; baseline signal scoring is experimental and does not verify mines.
5. Calculate coverage only from valid sensor observations and an explicit experimental footprint/altitude/speed profile, using PostGIS geographic buffers, intersection and union. Preserve attempts separately from planned area and flown tracks. No clearance claims.
6. Connect the reference-based web/mobile-first workspaces to mission planning, maps, telemetry, reviews, coverage/history, alerts/stop requests and JSON/CSV/printable reports.
7. Test permission/assignment denial, ordering, idempotency, concurrent commands, sensor provenance, partial coverage, history, exports and actual PX4/Gazebo integration where available. Document the actual test matrix.

Runtime image manifest checked: official px4io/px4-sitl-gazebo publishes linux/arm64 and linux/amd64. Pinned digest: 29a5a1b5af77e5d39b67bc6664d36acead63f9dfb829475216522b1feec8036e. See https://docs.px4.io/main/en/simulation/px4_sitl_prebuilt_packages for upstream runtime layout. Flight transport uses MAVLink; no camera features are consumed or exposed.
