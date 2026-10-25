# Requirements and architecture review — 17 October 2026

All three source documents were read completely before implementation. REQUIREMENTS.md describes the full vision; architecture.md tightens defaults and sequencing; the original README described documentation-only status.

| Topic | Finding and foundation decision |
|---|---|
| Five roles vs four web workspaces | Architecture assigns Field Personnel to Flutter. The user's subsequent request also authorizes a responsive mobile-first web Field Personnel workspace. Both clients share the same role-protected dashboard API. |
| Supervisor/field flight permissions | Requirements allow future explicit policy; architecture defaults to no commands. Foundation grants no flight commands to any role. Operator commands require a later validated mission adapter. |
| Two startup commands vs provisioning | Two commands apply after one-time dependency setup and explicit account creation. No seeded credentials. |
| Prototype vs foundation | This delivery provides auth and connected dashboard shells. No simulated mission, detections, telemetry or coverage is fabricated. |
| Start simulator vs start mission | Future operator start orchestrates lifecycle/readiness/upload/execution. Runtime startup alone has no flight effects. No executable adapter in foundation. |
| Flight path vs coverage | Separate future persistence entities; do not infer surveyed ground from a track or imply clearance. |
| Visual concepts | User subsequently supplied web and mobile JPEG references, preserved in docs/designs/. Follow their layout and styling, replacing camera panels and sample results with truthful integration states. Requested PNG paths were absent. |
| Architecture support | One codebase; native compatibility is a goal, not a tested claim. Upstream postgis/postgis documents AMD64 only, so build PostGIS on postgres:17-bookworm using distro packages instead. Both architectures still require runtime verification. |
| Permission storage | Foundation uses reviewed role-to-permission policy in backend code with one role per account. Database-managed multi-role assignments and permission administration are deferred. |

Sources checked: [FastAPI password hashing guidance](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [upstream PostGIS image architecture statement](https://github.com/postgis/docker-postgis#versions-2026-06-19). We use Argon2 password hashing and opaque, hashed, revocable database sessions rather than JWTs.

## Survey area assignments — 25 October 2026

The user now requires Supervisor-owned large polygons and contained operator sub-missions. New mission requests must include `assignment_id`; the older free-text mission `area_id` remains a survey-history grouping label and cannot substitute for authorization. Migration 0005 leaves earlier missions unassigned to preserve history and their existing workflow; no new unassigned missions can be created.

The coverage requirement is conservatively 100% geometric coverage from current-profile successful completed survey attempts. Failed/cancelled attempts retain their evidence in history but do not count toward completed assignment area. Valid live footprints are shown separately, never counted as completed. An incomplete area cannot round up to 100%. The current profile is explicitly synthetic/experimental, not evidence of landmine clearance.

Supervisors may modify metadata, boundary, or operator using revision checks. Active flights block changes. Updated boundaries must contain all linked mission polygons. Reassignment transfers unflown drafts and forces revalidation; previous survey records are not rewritten. Assignments are capped at 100 km², without relaxing existing per-mission/SITL home constraints. Exact polygon/route containment is a planning rule; this change does not install an aircraft geofence.

## Mock sensors and embedded Gazebo world view

The subsequent cropped Detected Targets reference is implemented as a reusable record-backed list, not a hard-coded example list. Fixture version `demo/2` supplies varied predefined example labels; these are explicitly marked MOCK DATA/UNVERIFIED and are not algorithmic landmine classifications. The feature-score calculation, quality gate, candidate threshold and coverage profile remain unchanged. Existing records are not relabeled. The screenshot's example confidence values are visual guidance, not evidence requiring score overrides. Records below the existing candidate threshold are not fabricated to reproduce the reference's low-score row.

The user explicitly requested mock sensor/detection data for now. New web drafts therefore select the visible mock-fixture option by default; submitting the form records that selection. The backend still defaults to no fixtures for API callers, and existing attempts are never rewritten. No simulated result is a verified mine or evidence of clearance.

The requested Gazebo 3D window is implemented as a read-only browser renderer driven directly by Gazebo `/world/default/pose/info`, not a UAV camera. It uses a simplified enlarged quadrotor and flat grid rather than embedding the native Gazebo desktop GUI or claiming to display terrain meshes. No new sensor, flight controls, public ports or lifecycle-start actions are introduced. Scene access requires existing mission permissions and an active matching vehicle lease; historical missions cannot expose another mission's live pose. Native GUI streaming and arbitrary Gazebo-world asset rendering are outside this increment.

The user clarified that the original detection card styling should remain. The cropped reference now guides classification names only; the narrow numbered list has been replaced by the existing responsive mission-card layout. Synthetic/unverified labeling and stored-record selection remain.

Legacy simulated detections now receive stable ID-derived display-only demo labels when their stored classification is potential_target or absent. Details explicitly disclose this fallback. Stored classifications, scores, reviews, exports and coverage are unchanged; this is presentation, not retrospective sensor analysis. Non-simulated records never use this fallback.

Workspace navigation previously repeated the complete mission detail on unrelated tabs. View-specific composition now separates classification register/assessments, target review, sensor readings, map results, operator commands, mission history, reports and alerts. Approval policy remains explicitly unimplemented rather than exposing a misleading approval action. Fleet view reflects the single configured SITL vehicle. Backend authorization is unchanged.

The user removed the mission-specific 10–40,000 m² area range and 600 m route-length cap. Missions still require valid nonzero-area polygons, entire-route containment and assigned-parent containment. Parent assignment limits and isolated SITL runtime/home constraints are unchanged. This permits larger plans without claiming every plan is executable by the simulator.

Account administration now supports role selection, account enable/disable and per-account denied permissions (migration 0006). Role templates remain the upper bound. All runtime permission checks use effective permissions; mission scope/assignment checks remain in place. Shared identity responses add active and denied_permissions fields; React consumes them and existing mobile clients ignore additive fields. Administration is serialized in PostgreSQL, protects self-access/last administrator, blocks active-operator edits, audits target IDs and revokes affected sessions. OpenAPI snapshot updated.
