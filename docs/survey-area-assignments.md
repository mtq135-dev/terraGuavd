# Survey Area Assignments — 25 October 2026

Supervisors create large survey polygons, assign a Mission Operator, and monitor progress through multiple smaller missions. Only Supervisors manage the assignments. Operators read their own assignments and create contained child missions. Other roles cannot manage or browse these assignments. Existing mission/field access policies remain authoritative for individual mission records.

## Persistence and API

Migration `0005` adds `survey_area_assignments`, indexed generated `boundary_geometry geometry(Polygon,4326)`, append-only `survey_area_events`, and nullable indexed `missions.assignment_id`. Boundary JSON is GeoJSON Polygon with one closed `[longitude, latitude]` ring, using the project's existing conventions. Input requires finite coordinates, valid polygon topology and geographic area from 10 m² to 100 km²; antimeridian polygons are rejected. Dates use timezone-aware UTC storage. `deadline` is optional and advisory; overdue assignments remain visible.

| Endpoint | Authorization and behavior |
|---|---|
| `GET /api/v1/survey-areas?offset=0&limit=50` | Supervisors see all; operators see their own. Includes computed progress/status. |
| `POST /api/v1/survey-areas` | Supervisor only: name, description, operator_id, boundary ring, optional deadline. |
| `GET /api/v1/survey-areas/{id}?offset=0&limit=100` | Scoped metadata, completed/live/remaining geometry, mission/survey/event history. |
| `PUT /api/v1/survey-areas/{id}` | Supervisor only: full editable fields and current revision; conflicts return 409. |
| `POST /api/v1/missions` | Existing mission plan plus required assignment_id; assigned operator and whole-polygon containment enforced. |

No endpoint deletes survey history. Missing/unowned assignment IDs return 404 to operators. Assignment permissions are `survey_areas:read` for operators/Supervisors and `survey_areas:manage` for Supervisors only. Mission containment is checked again at validate/start; routes already must be covered by their mission polygon. A Supervisor cannot bypass area ownership by assigning an individual child to another operator.

Parent-before-child row locking serializes assignment edits with mission mutations. Reassignments are blocked during active missions; unflown children transfer to the new operator and return to DRAFT. Completed/failed/cancelled histories keep their original identities. Boundary edits must retain every linked mission polygon. Revisions prevent stale edits from silently overwriting newer changes; change snapshots are append-only. Existing unassigned missions remain readable/executable under prior rules, while new requests cannot omit assignments.

## Coverage semantics

- **Completed:** union of stored `COMPLETED` survey-attempt footprints using the current coverage version and synthetic provenance, clipped to the assignment. Overlaps count once. No sensor data means zero progress, even for a completed flight.
- **In progress:** union of current active mission valid observation footprints, clipped to the assignment and with completed coverage subtracted.
- **Remaining:** assigned polygon minus completed and live footprints. This forms a disjoint partition for map display. Live area still needs completion before contributing to completed percentage.
- **Status:** derived from persisted facts: ASSIGNED before any flight, IN_PROGRESS after attempts begin, COMPLETED only when the entire assignment is geometrically covered by completed evidence. Partial percentages cap at 99.99; there is no rounded completion shortcut. Expanding a completed assignment can reopen it.
- **History:** all attempts remain, including cancelled/failed attempts excluded from completed progress. Assignment snapshots retain creation, metadata/operator/boundary changes and revisions. Blue dashed sub-mission outlines on the map are planned geometry only, never coverage.

The existing experimental synthetic-footprint profile remains unchanged. Surveyed does not mean cleared or safe. Planning containment is not aircraft geofencing, and large assignment storage does not remove current simulator-home, per-flight area, route, single-vehicle or time limits.

## Verification

- 11 backend unit tests passed.
- 10 PostGIS/workflow tests passed, including migration upgrade/downgrade, authorization/scoping, required parent linkage, outside polygons, revalidation/start enforcement, revision conflicts, active-flight edit rejection, draft transfer, append-only history, duplicate coverage union, no-sensor completed flights, live/cancelled coverage exclusion, two smaller completed areas reaching whole coverage, an uncovered sliver remaining at 99.99, and expansion reopening progress.
- The same suite executed an actual isolated PX4/Gazebo mission inside an assigned area: 71 recorded telemetry samples, three synthetic potential targets, 16.02% experimental mission coverage, return, landing and disarming. This mission did not fully cover the parent assignment.
- Frontend tests cover Supervisor drawing/submission and Operator read/planning access without edit controls, alongside existing role and mission workflows. TypeScript/build, formatting and Compose validation passed; the existing lazy Three.js chunk-size advisory remains.
- Browser verification used a disposable database and test accounts. Supervisor drew a 15,836 m² area with operator/description/deadline. Operator saw it on the dashboard, received an outside-boundary rejection and saved two contained sub-missions. Supervisor reassignment transferred both drafts and reset READY to DRAFT. The old operator lost access; the new operator saw the area and drafts. Coverage correctly remained zero because those browser drafts had not flown. The assignment map displayed both planned subdivisions without counting them as covered. Responsive check at 390×844 showed no page-wide horizontal overflow.

Screenshots: `docs/screenshots/survey-area-assignment.png` and `docs/screenshots/survey-area-mobile.png`. Native AMD64 and Flutter builds were not rerun for this web/backend feature; the SITL runtime check used the local ARM64 Docker engine.
