# Fleet scenarios and responsibility

## Workflow

1. Administrator registers the UAV type and individual vehicles, and manages availability. Registration does not grant flight permissions. Type/profile and runtime binding are immutable through the fleet API.
2. Supervisor draws a survey-area polygon and assigns its responsible Mission Operator. The Supervisor does not choose the mission UAV or issue flight commands.
3. The assigned Operator creates one or more contained missions, chooses one registered executable UAV per mission, and supplies each route. Splitting work and selecting vehicles are manual; there is no automatic fleet allocation or route partitioning.
4. The Operator explicitly validates and starts each mission. Different UAVs may execute different missions in the same assigned area concurrently. A busy UAV cannot be reserved by another mission.
5. Each UAV retains its own runtime, observations, attempt snapshot, commands and lease. Area progress unions completed valid coverage; vehicle count is not a progress measure. Field Personnel submit stop requests to the Operator rather than directly controlling aircraft.

Example: the Supervisor assigns Area A to Operator O. O prepares A1 for sitl-01, A2 for sitl-02 and A3 for sitl-03, then explicitly starts the three missions. Their footprints may overlap; union-based coverage avoids double counting. The automated flight matrix intentionally uses matching small routes to exercise isolation and overlapping footprints, rather than claiming an optimized area-partitioning algorithm. Each service is a separate isolated simulated world, so this test does not validate shared-airspace collision avoidance or formation flight.

## Counts and types

The catalog supports multiple vehicles and categories. Inventory-size tests exercise 0, 1, 2, 3, 5 and 10 vehicles across quadrotor, hexacopter and fixed-wing labels. These catalog labels do not establish flight compatibility.

Execution is limited to three fixed isolated local channels (8090/8091/8092). The allowlisted camera-free models are PX4/Gazebo x500 and x500_lidar_down. These are variants within the quadrotor family. Hexacopter and fixed-wing entries remain catalog-only. The downward LiDAR model does not make the experimental GPR/metal fixtures physical measurements: detection inputs remain explicitly synthetic.

## Automated cases

| Case | Method | Expected result |
|---|---|---|
| Inventory sizes 0/1/2/3/5/10 | API unit cases | Correct counts and no execution for catalog-only entries |
| Three category labels | API unit cases | Registration accepted; no inferred flight support |
| Supported downward LiDAR variant | API unit case | Third executable channel selected correctly |
| Fourth execution channel | API unit case | 422; configured capacity remains three |
| Duplicate runtime binding | API unit case | 409; exclusive channel identity |
| Unknown profile or external URL | API unit case | 422; fixed isolated allowlist only |
| Catalog-only type with runtime | API unit case | 422; no unsupported flight |
| Wrong category with x500 profile | API unit case | 422 |
| Supervisor/Administrator mission creation | API unit cases | 403; no flight authority added |
| Unassigned Operator | API unit case | 404; no access to another assignment |
| Assigned Operator chooses UAV 2 | API unit case | 201; selected identity persisted |
| Unknown/disabled UAV | API unit cases | 409 |
| Two starts on the same UAV | API unit case | Conflict rejected with 409 |
| Separate UAVs in one area | API unit case | Independent leases accepted |
| Disable a reserved UAV | API unit case | 409 |
| Runtime 1 failure | API unit case | Its lease released; runtime 2 and lease untouched |
| Selected scene model | Simulator unit case | Pose uses exact model name; other model ignored |
| Migration 0008 rollback/reapply | Disposable PostGIS case | Registry retained; reapplication succeeds |
| One x500 | Actual isolated SITL | See machine-readable evidence |
| One downward LiDAR x500 | Actual isolated SITL | See machine-readable evidence |
| Two x500s | Actual isolated SITL | Overlap in EXECUTING, independent completion/data/leases |
| Three mixed variants | Actual isolated SITL | Overlap in EXECUTING, independent completion/data/leases |

Unit cases use explicit doubles where required and are not flight evidence. Actual matrix results are written after each case to [fleet-matrix-evidence.json](fleet-matrix-evidence.json). Runs use disposable PostgreSQL/PostGIS data and explicitly enabled synthetic sensor fixtures; no verified mine or safe-ground claim is made.

## Recheck

Run `scripts/check-postgis.ps1 -IncludeFleetMatrix` while the development simulator is idle. The helper checks all three services for armed vehicles and uses a uniquely named disposable database. Each flight scenario stops its own runtimes after completion or failure. Execution requires a single backend process.

Frontend component/build tests and simulator unit tests are separate from the real matrix. Native mobile, manual browser walkthrough, architecture compatibility, other aircraft families and shared-world collision avoidance are not validated by these cases.

## Supporting checks (2026-11-06)

- Backend unit suite: 24 passed; 16 opt-in integration/flight cases skipped in this invocation.
- Separate disposable PostGIS regression: 10 passed; 6 optional flight cases skipped. Migration 0008 rollback/reapply passed.
- Simulator unit suite: 7 passed in the simulator image with network disabled, including refusal to switch models while armed.
- Frontend: 23 tests passed; TypeScript and production build passed. Vite reports a bundle-size advisory for the existing 3D chunk.
- Compose validation and PowerShell parser checks passed; changed fleet UI formatting passed.
- Live three-channel scene check: all channels reported fresh poses; channel 3 reported `x500_lidar_down_0` and channels 1/2 reported their own isolated `x500_0`. See [fleet-scene-evidence.json](fleet-scene-evidence.json).
- Local development PostgreSQL was upgraded and verified at 0008 with three active registered vehicles. Automated flights use their own disposable database.

## Actual flight matrix outcome (2026-11-06)

All four scenarios passed: one x500, one downward-LiDAR x500, two concurrent x500s, and three concurrent mixed variants. Seven missions completed in total. The two- and three-vehicle scenarios observed all their missions in EXECUTING at the same time. Each mission preserved its selected UAV, more than five observations, a matching survey-attempt UAV, and a released lease. The three-vehicle case recorded 100, 101 and 102 observations respectively. All runtime flight processes were subsequently verified stopped and disarmed.

| Scenario | Mission observations | Outcome |
|---|---|---|
| One x500 | 102 | Passed |
| One downward-LiDAR x500 | 103 | Passed |
| Two x500s | 100 / 100 | Passed |
| Three mixed variants | 100 / 101 / 102 | Passed |

Raw evidence remains in `fleet-matrix-evidence.json`. Experimental per-mission coverage remained around 17–18%; completion was not treated as full area coverage. The GPR/metal feature inputs were explicitly synthetic throughout.
