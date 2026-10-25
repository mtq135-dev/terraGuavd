# Connected prototype verification — 17 October 2026

## Executed checks

| Check | Result |
|---|---|
| Authentication/RBAC and detector/profile unit tests | 11 passed |
| PostGIS migrations/API/workflow integration | 5 passed; actual flight skipped in the ordinary regression run |
| Actual isolated PX4/Gazebo E2E | Passed; locked native ARM64 runtime, takeoff, uploaded route, return, landing and disarming |
| React interaction tests | 11 passed, including validation-before-start, field stop request without flight controls and analyst assessment persistence |
| TypeScript/Vite production build and formatting | Passed |
| Browser UI | Real API/PostGIS/WS, operator planning/start, actual pause/resume/cancel, completed/cancelled history, CSV download, persisted analyst review and assigned Field Personnel mobile view |
| Mobile browser sizing | 390×844; 375px content width with scrollbar, no horizontal overflow |
| Docker platform | aarch64 engine; PostGIS and PX4/Gazebo built and ran natively; upstream manifests publish ARM64 and AMD64 |

The final locked-adapter E2E recorded **90 actual SITL telemetry samples, 4 explicitly synthetic potential targets and 17.37% experimental coverage**, passing the five checks then in that suite in 151.20 seconds. Later lifecycle hardening added an interruption/late-worker test; the final non-flight regression suite passed all five spatial/workflow checks. Authentication unit tests and UI tests are separate from those integration checks. No remote CI run or native AMD64 runtime success is claimed.

Spatial tests cover containment validation, role and assignment denial, draft validation requirements, idempotent repeated starts, concurrent start lease contention, simulator failure release, synthetic provenance, quality/altitude/speed coverage rules, immutable survey snapshots, indexed coverage geometry, analyst permissions, report scoping, authorized/unauthorized WebSocket access and restart recovery that cannot revive an interrupted attempt.

## Actual browser-driven missions

- Full survey: 80 SITL samples, 3 synthetic targets, 5.43% experimental coverage, COMPLETED only after landing/disarming.
- Command exercise: PX4 Hold paused motion, Mission resumed it, explicit cancellation requested RTL, and CANCELLED was recorded after landing/disarming. It retained 88 samples, 2 synthetic targets and 6.24% partial coverage, while the earlier completed attempt remained visible under the same survey-area ID.
- The browser downloaded an authorized CSV report. An analyst saved a needs-investigation assessment, with explicit text that it does not verify a mine. Field Personnel saw only assigned mission data and no flight controls.
- WebSocket transport support was added after the actual browser caught its absence. PX4 upload frame/unused-parameter encoding and supported pause/resume modes were verified against the actual runtime rather than inferred from mocks.

Evidence: [connected survey](screenshots/prototype-survey.jpg), [analyst review](screenshots/prototype-analyst-review.jpg), [assigned mobile view](screenshots/prototype-field.jpg). All screenshots and report data are QA simulation records, not operational landmine results.

Screenshots were captured during integration. The final permission pass subsequently removed report-export controls from Field Personnel and restricted raw system runtime status to Administrators; field monitoring continues through assignment-scoped mission snapshots.

## Reproduce

Run `scripts/check.ps1` for unit/UI/build/config checks, `scripts/check-postgis.ps1` for automatic disposable PostGIS checks, and `scripts/check-postgis.ps1 -IncludeSitl` for an actual isolated simulated mission. Do not operate another simulated mission while the flight check runs. Test helpers create uniquely named databases and remove only those databases. QA role accounts never seed the development database.

The dependency stack emits a Starlette/httpx TestClient deprecation warning; tests pass. Flutter SDK/native analysis/device builds are unavailable. Real sensor/model calibration, physical aircraft integration, multiple vehicles, push notifications, configurable approval policy and production authentication/deployment hardening are not implemented or validated. This is a local simulation prototype. Experimental sensor coverage is not clearance evidence.
# Pre-arm startup correction — 18 October 2026

Investigated a user-reported command 400/result 1 failure. PX4 logged system-health arming denial; connectivity-only readiness could race startup health checks. The adapter now waits for fresh PX4 pre-arm health before normal arming and includes recent status text on failure. It never force-arms or disables checks. Two simulator regression tests passed, covering missing/failed/stale health and no arm command after failed preflight. The rebuilt native ARM64 runtime completed the actual isolated flight suite: six PostGIS/workflow tests passed in 142.61 seconds, including takeoff, survey, return, landing and disarming, 86 recorded samples, four synthetic potential targets and 17.13% experimental coverage. Full checks also passed: 11 backend unit tests, 11 frontend tests, formatting, TypeScript/build and Compose validation. Earlier failed attempts remain preserved; retry through a new validated draft.

# Mock sensors, UAV map symbol and Gazebo 3D web view

The disposable browser survey also completed and landed: 79 samples, four mock targets, 16.72% experimental coverage. The panel switched to no-live-scene after completion. Flutter's geographic schematic source now uses the same quadrotor motif; native compilation/device testing remains unverified.

New web drafts visibly select mock sensor fixtures by default, following the user's request. Existing records and API defaults remain unchanged. Leaflet uses a quadrotor SVG marker for the latest recorded UAV position. The web 3D panel is an interactive Three.js visualization driven directly by Gazebo world position/orientation, with a simplified enlarged UAV and flat grid. It is not a camera feed, native Gazebo GUI, or arbitrary terrain renderer.

Executed checks: 11 backend unit tests, 12 frontend tests, formatting, TypeScript/build and Compose validation passed. Seven disposable PostGIS/workflow tests passed in 155.02 seconds, including new scene authentication/mission/lease isolation and an actual PX4 survey with the Gazebo bridge enabled: 94 samples, four synthetic potential targets, 17.46% experimental coverage, landing and disarming. Two scene parser/freshness tests and two pre-arm tests passed inside the native ARM64 simulator container. Browser QA used a disposable database and operator account: default mock checkbox selected, actual flight commands, live `gazebo-world-pose` source, map UAV symbol, visible 3D model, zoom, reset and expand/close verified. Screenshots: `docs/screenshots/gazebo-live-3d.png` and `docs/screenshots/uav-map-symbol.png`. The Three.js viewer is lazy-loaded; its production chunk still produces Vite's advisory size warning. Native AMD64 runtime and native Flutter builds were not tested in this increment.

# Survey Area Assignments — 25 October 2026

Implemented and verified Supervisor polygon assignments, operator child-mission planning/containment, safe reassignment, revisioned append-only change history and coverage-based aggregate progress. See [survey-area-assignments.md](survey-area-assignments.md) for executed tests, semantics and screenshots. An actual assigned PX4/Gazebo mission completed with 71 samples and three synthetic potential targets. Its partial sensor coverage did not complete the larger assignment. Browser QA used a disposable database, drew an assignment and two smaller mission polygons, verified outside-area rejection and cross-operator transfer/access revocation, and checked the mobile layout. No test accounts or assignments were seeded in the normal database.

# Reference-style mock detection list

The reusable Detected Targets panel uses actual mission detection records, persisted classifications/timestamps (observation timestamp fallback for older API payloads), numbered rows, score badges, selected-row highlighting, search, classification/minimum-score filters and six-row pagination. Selecting a row retains the actual detection ID for the existing analyst-review flow. New demo/2 sensor fixtures carry predefined mock labels; score/quality/coverage rules are unchanged and no historical detections were rewritten. CSV exports include classification.

Verification: 12 backend unit tests, 16 frontend tests, nine PostGIS/workflow checks, TypeScript/build, formatting and Compose checks passed. Browser visual verification used an explicitly labeled temporary fixture preview of the same component; search, class filtering/reset and record selection were verified. The preview files were removed and no fixture records were added to the normal database. Screenshot: `docs/screenshots/mock-detection-list.png`. A new PX4 flight was not run for this presentation/fixture update; prior flight verification remains separately recorded.


The subsequent style correction restores the original responsive detection cards while retaining mock classification labels and the existing analyst review connection. The earlier mock-detection-list screenshot documents the superseded list style.
