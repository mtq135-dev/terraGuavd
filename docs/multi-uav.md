# Multi-UAV simulation increment

## Implemented scope

One mission uses one registered UAV. A Supervisor-owned survey area contains many missions, and these may use different UAVs. Assignment summaries return distinct `uav_ids` and `uav_count`, derived from missions rather than a separately maintained counter. Existing containment, assignment checks and geometric union progress remain authoritative; more vehicles or flights do not imply more coverage or clearance.

Migration 0007 adds `uav_types` (id, name, category, simulation_profile, specifications) and `uavs` (id, name, type_id, active, runtime_slot, created_at). Missions, immutable survey snapshots and vehicle lease identifiers reference registered UAVs. Existing legacy identifiers are preserved as inactive catalog entries; no survey history is rewritten. Migration 0008 provisions a third channel and the downward-LiDAR x500 variant. These are vehicle records, not user accounts. Type names/categories/specifications are catalog data, not validated physical performance.

Supported execution is bounded to three isolated PX4/Gazebo services: localhost 8090, 8091 and 8092. Arbitrary URLs, MAVLink addresses and physical aircraft are not configurable. `sitl-01`, `sitl-02` and `sitl-03` slots are unique. The original single-vehicle runtime is reused unchanged inside each container; all may use internal MAVLink system 1 because their transports/processes are isolated. Explicit distinct `GZ_PARTITION` values isolate same-named Gazebo topics/services, as described in [Gazebo Transport NodeOptions](https://gazebosim.org/api/transport/13/classgz_1_1transport_1_1NodeOptions.html). Startup starts idle authenticated APIs only, never flight.

Executable profiles are the quadrotor `px4-x500` and its camera-free `px4-x500-lidar-down` variant. Other categories remain `catalog-only`, without flight compatibility claims. Historical two-x500 evidence is retained below; see [the expanded matrix](fleet-test-matrix.md) for the additional 1/2/3-vehicle scenarios. Separate isolated worlds do not validate collision avoidance.

## API and module review

- Administrator: `fleet:read` and `fleet:manage`; register types/UAVs and change availability. No flight permission is added.
- Operators, Supervisors and Analysts: `fleet:read`; Field Personnel receive their assigned mission's UAV identity rather than fleet access.
- `GET/POST /api/v1/fleet/types`, `GET/POST /api/v1/fleet/vehicles`, `PATCH /api/v1/fleet/vehicles/{id}`. Types and runtime bindings are immutable through this API; active vehicles cannot be disabled.
- `MissionPlan.uav_id` defaults to `sitl-01` for backward compatibility. New web plans require selecting an executable vehicle. Validation/start reject unknown, disabled, unbound or unsupported vehicles. Database locks serialize changes and vehicle reservations; conflicting starts on the same vehicle are rejected.
- Runtime commands, polling, failure cleanup and recovery resolve the mission's own vehicle. Failure of one isolated runtime does not stop the other. Scene access requires the matching lease; no other mission's pose may be exposed.
- React: Administrator UAV Management and Supervisor UAV Fleet use the registry; planning selects a vehicle, mission cards/detail show its ID, and area detail displays its distinct vehicle count.
- Mobile: additive mission identity/area summary fields; existing Field Personnel reads remain compatible. Native mobile build is not verified by this increment.
- `docs/openapi.json` refreshed from the application. Backend, runtime routing, Compose/startup and frontend contracts were reviewed together. One backend process remains required.

## Validation evidence

- Backend unit suite: 16 passed; integration/flight cases skipped unless explicitly enabled.
- Disposable PostgreSQL/PostGIS regression suite after lock-order review: 10 passed, 2 optional flight tests skipped. Migration upgrade/downgrade and existing assignment, history, coverage, permissions, report and lease workflows passed.
- Actual concurrent PX4/Gazebo test: 11 passed, 1 optional single-flight case skipped. Both missions in the same assigned area overlapped in EXECUTING, completed and released independent leases. First UAV: 101 observations, 5 synthetic targets, 17.52% experimental mission coverage. Second: 100 observations, 5 synthetic targets, 17.65%. Raw result: [multi-uav-e2e-evidence.json](multi-uav-e2e-evidence.json).
- Frontend: 23 tests passed; TypeScript/production build passed. Changed TS files pass Prettier. Repository-wide format check reports 20 pre-existing, unchanged files; those files were not reformatted as part of this feature.
- Browser/manual UI walkthrough and native AMD64/ARM64 matrix: not verified in this increment. The real flight test used the existing local Docker engine.

All sensor fixtures were explicitly enabled and synthetic. No detection is a verified mine; no experimental coverage establishes cleared or safe ground. Test users/data lived in a uniquely named disposable database which the test helper removed.

## Run and recheck

Run `scripts/start-backend.ps1` after stopping the old backend process; this starts all three idle runtime services and applies migrations. Run `scripts/start-web.ps1`, then sign in as Administrator for UAV Management or as the assigned Operator for Mission Planning.

Run `scripts/check-postgis.ps1 -IncludeMultiSitl` for the actual concurrent-flight test. Do not run it during another simulation session; the helper refuses already armed vehicles and uses only a uniquely named disposable database. PX4/Gazebo runtime APIs remain running but the E2E test stops both flight processes on completion/cleanup.

The existing Word/PDF Section 4.4 still describes the previous 12-table schema. Following this successfully tested increment, it needs two new entity dictionaries, updated FK descriptions/ERD, and testing-caption renumbering before it represents migration 0007. Do not present the old report as the new schema.

Development database deployment was subsequently verified at Alembic head 0007 with both registered vehicles. Both runtime services were checked disarmed with no flight process running after the experiment.

## Expanded matrix result

All four additional 1/2/3-vehicle flight scenarios passed (seven completed missions), including the camera-free downward-LiDAR x500 variant. Full cases, role workflow and limitations are recorded in [fleet-test-matrix.md](fleet-test-matrix.md), with raw [flight evidence](fleet-matrix-evidence.json). Development PostgreSQL is now verified at migration 0008 with three active vehicles; all flight processes were stopped and disarmed after testing. The earlier 0007/two-vehicle evidence above is retained as historical evidence.
