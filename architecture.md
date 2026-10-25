# TerraGuavd — Software Architecture

> Status: planned architecture. Features are not considered implemented until integrated and tested.

## 1. Purpose and safety boundary
TerraGuavd is a software platform for planning and monitoring UAV-based landmine surveys, interpreting sensor measurements, mapping potential targets, and retaining survey history. It does not manufacture the aircraft and has **no camera features**. Potential targets are not confirmed landmines; surveyed ground is not necessarily safe or cleared. The prototype is **simulation-only** until physical integration is separately validated.

## 2. Applications and roles
A single React + TypeScript web application serves four role-aware workspaces: Administrator, Mission Operator, Detection Analyst, and Supervisor. A Flutter mobile application serves Field Personnel. All use the same backend APIs. Backend permission checks, not UI visibility, determine access.

| Role | Responsibilities | Default flight commands |
|---|---|---|
| Administrator | Users, permissions, UAV registry, health, audit | None |
| Mission Operator | Plan, validate, start, pause, resume, cancel, monitor missions | Allowed for assigned missions |
| Detection Analyst | Review GPR/metal-sensor signals, potential detections, annotate/export | None |
| Supervisor | Assignment, approvals, reports, mission oversight | None |
| Field Personnel | Assigned mission map, telemetry, alerts, detections, stop requests | No direct flight control |

A field stop **request** is not equivalent to an autopilot emergency-stop command; the backend must enforce explicit policy.

## 3. System diagram
```text
React Web (Admin / Operator / Analyst / Supervisor)    Flutter Mobile (Field)
                         \                             /
                          HTTPS REST + WebSocket
                                   |
                      FastAPI API + RBAC + Audit
                         /        |           \
               PostgreSQL/PostGIS |       Detection Service
               (missions, geo,    |       (GPR + metal data;
                alerts, history)  |        confidence + provenance)
                                  |
                          Mission Orchestrator
                                  |
                         Simulation Manager
                                  |
                             MAVSDK/MAVLink
                                  |
                              PX4 SITL
                                  |
                               Gazebo

                 QGroundControl: optional developer diagnostics only
```

## 4. Responsibilities and contracts
- **Web:** role-aware dashboards, Leaflet + OpenStreetMap maps, mission editor, live telemetry, detection review, coverage/history and reports. Never contain privileged control logic.
- **Mobile:** assigned missions, UAV status, detections and alerts, read-only coverage and survey dates, authorized stop requests. No camera views.
- **API:** authentication, session management, authorization, mission state machine, validation, assignment, persistence, audit events, report generation, WebSocket distribution.
- **Simulation Manager:** architecture-aware runtime adapter; start/reuse PX4 + Gazebo on explicit authorized mission start; wait for actual MAVLink readiness; reject duplicates; cleanly recover from failures. Simulation startup must not cause takeoff.
- **Detection:** ingest time-stamped sensor readings with positions, store processing version and confidence, classify as *potential* targets for analyst review. Never claim confirmed mines from model output alone.
- **PostGIS:** mission polygons, waypoints, flight tracks, sensor footprints, detections, validated coverage geometry and append-only survey history.

## 5. Mission state machine
`DRAFT → VALIDATING → READY → STARTING_SIMULATION → WAITING_FOR_VEHICLE → UPLOADING → EXECUTING → COMPLETED`

Alternative terminal states: `CANCELLED`, `INTERRUPTED`, `FAILED`; `PAUSED` and `RESUMING` only when supported by the flight adapter. State changes are server-side, persisted, audited and exposed through REST/WebSockets. Mission creation must never arm or take off. Each command must check identity, permission, mission assignment, current state and simulator mode.

## 6. Suggested API surface (to implement)
| Endpoint | Purpose |
|---|---|
| `POST /api/v1/auth/login` | Authenticate |
| `GET /api/v1/auth/me` | Identity and permissions |
| `GET/POST /api/v1/missions` | List/create missions |
| `GET /api/v1/missions/{id}` | Mission details |
| `POST /api/v1/missions/{id}/validate` | Validate geometry and prerequisites |
| `POST /api/v1/missions/{id}/start` | Explicit start (operator only) |
| `POST /api/v1/missions/{id}/pause` | Pause when supported |
| `POST /api/v1/missions/{id}/resume` | Resume when supported |
| `POST /api/v1/missions/{id}/cancel` | Cancel mission |
| `GET /api/v1/missions/{id}/detections` | Potential targets |
| `GET /api/v1/missions/{id}/coverage` | Validated survey geometry |
| `GET /api/v1/areas/{id}/surveys` | Historical surveys and dates |
| `GET /api/v1/alerts` | Authorized alerts |
| `WS /ws/missions/{id}` | Authorized telemetry/events |

Use OpenAPI/Pydantic contracts and versioned migrations. Add pagination, input validation, idempotency and structured errors before production.

## 7. Survey Coverage & History
Track **planned polygon**, **actual flight track**, **sensor observations**, and **validated survey coverage** separately. A mission may complete without covering its entire planned area. Coverage must be computed from sensor footprint, altitude, spacing, valid readings and telemetry quality; do not infer coverage from flight track alone. Interrupted missions only retain substantiated coverage. Persist every survey attempt with mission ID, UAV ID, start/end timestamps, status, geometry, measured coverage and algorithm/version. Never overwrite earlier attempts. Map legend: green = validated surveyed, yellow = in progress, red = interrupted, gray = not surveyed, blue = selected; also include text/patterns. Map selection shows last surveyed date and history. Always display: **Surveyed does not mean cleared or safe.**

## 8. Storage entities
Users; Roles; Permissions; UserRoleAssignments; UAVs; Missions; MissionAssignments; Waypoints; TelemetrySamples; SensorReadings; Detections; AnalystReviews; SurveyAreas; SurveyAttempts; CoverageGeometry; Alerts; MissionEvents; AuditEvents. Store geospatial shapes in PostGIS, timestamps in UTC, and expose user-local dates in clients. Sensitive actions should have immutable audit trails.

## 9. Platform and deployment
One codebase for `linux/amd64` and `linux/arm64`. Prefer multi-arch images and native dependencies. Verify actual PostGIS and PX4/Gazebo image manifests and runtime on both architectures; do not assume a third-party simulator image supports ARM64. Keep simulation adapter configurable for native/WSL/Docker environments. Docker Compose is for database/support services; frontend can run with Vite locally. Two Windows PowerShell entry points are intended: `scripts/start-backend.ps1` and `scripts/start-web.ps1`. These scripts must report readiness and fail clearly. Production secrets belong in ignored environment files, never Git.

## 10. Quality gates
Unit tests for RBAC, state transitions, coverage validity and detection provenance; API integration tests against PostGIS; browser tests for each role; simulated mission end-to-end tests for PX4 readiness, command ordering and telemetry; architecture matrix for AMD64/ARM64. Validate UI against supplied visual references. Prevent conflicting commands from QGroundControl and TerraGuavd.

## 11. Team workflow
Use feature branches and pull requests, protect `main`, document API changes before merging, run tests/linters in CI, assign module ownership and require cross-module review for shared interfaces. Keep simulation-specific code behind an adapter to avoid breaking API consumers.

## 12. Implementation sequence
1. Repository layout, documentation, toolchain and CI.
2. PostGIS schema/migrations and FastAPI foundation.
3. Authentication, RBAC and audit.
4. React role dashboards using supplied design references.
5. Mission planning/state machine and Leaflet maps.
6. PX4/Gazebo on-demand simulation adapter and live telemetry.
7. Sensor ingestion, detection review and confidence provenance.
8. Validated coverage, survey history and reports.
9. Flutter Field Personnel app, alerts and stop requests.
10. AMD64/ARM64 validation and end-to-end tests.

**Implementation status (17 October 2026):** The simulation prototype now connects persisted mission planning/assignment/validation, actual isolated PX4/Gazebo execution over MAVLink, authenticated telemetry snapshots, Leaflet maps, synthetic-feature processing, analyst reviews, PostGIS footprint coverage/history and authorized reports. A responsive Field Personnel web workspace complements Flutter source. `CANCELLING` retains the vehicle lease until landing/disarming. Pause/resume uses PX4 Hold/Mission modes. The detector/coverage profile is experimental and synthetic-only, with no physical validation or clearance claims. Use one API worker and the single configured SITL vehicle. See README.md, docs/prototype-plan.md and docs/prototype-verification.md for test evidence and limitations.

**Gazebo visualization:** The simulator owns a fixed read-only Gazebo Transport pose subscriber, started/stopped with its runtime. `/scene` returns only the fresh `x500_0` world pose. FastAPI `GET /api/v1/missions/{id}/scene` enforces mission access and the matching active vehicle lease before forwarding it; runtime credentials remain server-side. React renders a simplified Z-up quadrotor using Three.js/OrbitControls, with no command transport or sensor images. Missing/stale poses never appear as a live UAV. Scene rendering is isolated from mission telemetry storage and sensor processing. The user authorized default-selected mock fixtures for new web drafts; API and historical mission settings are unchanged.

**Survey area assignments:** `survey_area_assignments` stores Supervisor-owned polygons (GeoJSON plus indexed generated EPSG:4326 PostGIS geometry), operator, metadata/deadline and optimistic revision. `survey_area_events` retains append-only snapshots; missions link by nullable `assignment_id` for historical compatibility. Every new mission requires an assigned area. Create/validate/start enforce full polygon containment; existing route validation then guarantees planned routes remain inside. Supervisor assignment edits and mission mutations lock parent before child to prevent concurrent starts/reassignments from invalidating membership. Active missions block edits. Reassignment moves only unflown drafts and requires revalidation. Historical mission/survey records are preserved.

Area progress unions current-profile `COMPLETED` survey snapshots, clips to the assigned geometry, and computes geographic area in square meters. Live valid footprints form a separate layer after subtracting completed coverage; the remaining layer excludes both. `COMPLETED` requires exact geometric containment of the entire assignment in completed coverage; incomplete percentages cap at 99.99. All current evidence is experimental mock sensor data. Mission counts and the legacy free-text `area_id` do not determine assignment progress. Native aircraft geofencing is not introduced by this feature; containment applies to planned survey polygons/routes within the existing isolated SITL workflow.
