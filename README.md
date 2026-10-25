# TerraGuavd

Connected UAV landmine-survey **simulation prototype**. **No camera features. Potential detections are unverified. Surveyed does not mean cleared or safe.**

Read [REQUIREMENTS.md](REQUIREMENTS.md), [architecture.md](architecture.md), [AGENTS.md](AGENTS.md), the [consistency review](docs/consistency-review.md), and [connected prototype plan](docs/prototype-plan.md). The simulation workflow is connected; physical sensor/model validation and physical aircraft integration are outside this prototype.

## Implemented

- Modular React/TypeScript web and Python/FastAPI backend.
- Argon2 passwords, expiring opaque bearer sessions stored as hashes, logout revocation, active-account checks and server-side role-to-permission enforcement. No default accounts.
- Administrator, Mission Operator, Detection Analyst and Supervisor dashboards; mobile-first Field Personnel workspace. Shared reusable navigation, panels, metrics, tables, empty states and safety messaging.
- Functional login/logout, admin account listing/search and audit browsing, system health, persisted mission planning/assignment/validation, exclusive vehicle reservation, explicit start, pause/resume/cancel, and field stop requests with backend authorization.
- Actual PX4 SITL + Gazebo execution behind an authenticated isolated runtime adapter using MAVLink. Live position, altitude, speed and battery are stored and distributed over authenticated WebSockets, with polling fallback.
- Leaflet/OpenStreetMap planning and monitoring maps: draw boundaries/waypoints, inspect actual flight tracks, potential targets, experimental sensor coverage, survey dates/history and analyst assessments.
- Experimental processing of explicitly opted-in synthetic normalized GPR/metal feature fixtures. Model version, observation IDs, position and simulated provenance accompany every potential target. This is not a trained or validated mine detector.
- Original responsive detection cards with selectable details and predefined Potential Mine, Metallic Object, Unknown and Rock labels from new `demo/2` fixtures. These are synthetic, unverified examples, not predictions. Existing records retain their stored classifications; experimental scoring and thresholds are unchanged.
- PostGIS sensor-footprint coverage with quality/altitude/speed rules, spatial target storage and append-only survey snapshots. Completed, cancelled and failed attempts preserve their own coverage; flight completion never forces 100% coverage.
- Authorized JSON/CSV reports plus browser print/save PDF.
- Supervisor-owned large survey area assignments, map drawing, operator assignment/reassignment, descriptions/deadlines, append-only change history and linked sub-missions. Progress unions completed valid sensor-footprint coverage in PostGIS; live and remaining ground are separate. New missions require an assigned parent area and backend containment checks.
- Reference-based compact dark navy layouts with cream/red accents. Supplied JPEGs are preserved in [docs/designs/](docs/designs/); requested PNG paths were absent. Example values and camera panels in the images are not implemented as real data or features.
- PostgreSQL/PostGIS Docker Compose build, persistent volume, database readiness and versioned migrations through 0006 for identity, operations, spatial records and survey area assignments.
- Flutter Field Personnel source with authentication, polling, assigned mission cards, telemetry, a geographic schematic, target details, survey history and stop requests. Native SDK/device builds remain unverified; the responsive Field Personnel web interface is browser tested.

## Windows 11 setup

Install Python 3.12+, Node.js 24 LTS, Git, and Docker Desktop with the WSL 2 Linux engine. Run from the repository root in PowerShell. If script execution is restricted, follow your organization's PowerShell policy; no script changes machine-wide execution policy.

Setup installs locked dependencies and generates an ignored `.env` with random local database and simulator-service secrets. Re-run setup when updating from the foundation increment:

```powershell
.\scripts\setup.ps1
```

Terminal 1 starts the database and idle simulator service, waits for health, applies migrations, then runs the API. First setup downloads the official PX4/Gazebo image and can take several minutes:

```powershell
.\scripts\start-backend.ps1
```

Provision accounts in another terminal, choosing your own passwords at the hidden prompt:

```powershell
.\scripts\create-user.ps1 -Username admin -Role administrator
.\scripts\create-user.ps1 -Username operator -Role mission_operator
.\scripts\create-user.ps1 -Username analyst -Role detection_analyst
.\scripts\create-user.ps1 -Username supervisor -Role supervisor
.\scripts\create-user.ps1 -Username field -Role field_personnel
```

Terminal 2:

```powershell
.\scripts\start-web.ps1
```

Open [TerraGuavd](http://127.0.0.1:5173), [API docs](http://127.0.0.1:8000/docs), or [readiness](http://127.0.0.1:8000/api/v1/health/ready). Vite proxies `/api` to port 8000; browser tokens stay in memory. Reload requires sign-in; sessions expire after 30 minutes. Use a Field Personnel account and a narrow viewport for the mobile-first web interface. Native Flutter instructions are in [mobile/README.md](mobile/README.md).

Use one API process/worker and one active test session for the single configured `sitl-01` vehicle. Stop foreground servers with Ctrl+C. Stop supporting services with `docker compose stop db simulation`; data remains in the named volume. Scripts start the idle simulation API, not a flight. PX4/Gazebo start/reuse is triggered by an assigned operator's explicit mission start; runtime startup itself never arms or uploads. After an API restart, unfinished attempts are interrupted and the isolated simulator is stopped rather than automatically resumed. If you edit a database password after volume initialization, changing `.env` alone does not rotate it.

## Run a survey

1. Sign in as a **Supervisor** and open **Survey Areas → New area assignment**. Draw a polygon, select a provisioned Mission Operator, enter its name/description and optional local-time deadline, then save. No flight starts. Large assignments support 10 m²–100 km²; do not cross the antimeridian.
2. Sign in as the assigned **Mission Operator**. The area appears on the dashboard and **Survey Areas** map. Choose **Plan sub-mission**, draw a smaller closed boundary and internal waypoints inside the purple assignment outline, then save. Repeat for additional portions. New missions require the assigned area; mission polygons and entire routes must remain contained. Mission polygon area and route length have no separate numeric caps. Polygons must be valid, have nonzero area, contain the entire route and remain within the assigned parent area. Altitude 2–8 m and speed 0.5–3 m/s still apply. SITL execution remains near the current simulator home. Coordinates are `[longitude, latitude]`.
3. **Mock GPR/metal sensor data and synthetic detections** are selected by default for new web drafts as requested. Keep this checked for detection/coverage demos, or uncheck for telemetry only. The backend retains the explicit selection and synthetic provenance. Assign existing Field Personnel accounts if required.
4. Save the draft, **Validate plan**, then explicitly **Start simulated mission**. Saving, validating and starting the simulator alone never launches a mission. Start waits for fresh MAVLink telemetry before upload/arming/execution.
5. Monitor the map and telemetry. Assigned operators can pause, resume or cancel/return. A field stop request records an alert for the operator; it never directly commands PX4.
6. Sign in as Detection Analyst, select a recorded target and save an assessment. Assessments cannot confirm a landmine.
7. Review coverage/history and download JSON/CSV reports or print/save PDF. Create another mission with the same area ID for a subsequent survey; earlier attempts remain intact.

The live map uses a quadrotor symbol for the latest recorded UAV position. A **Gazebo · live 3D world** panel offers orbit, zoom, pan, follow, reset and expansion. Its read-only position/orientation come directly from Gazebo world poses through the authorized mission API. The browser renders a simplified quadrotor enlarged 4× over the default flat grid; this is not the native Gazebo GUI, surveyed terrain, or a camera feed. A live pose is shown only for the currently active mission; stale or missing pose data hides the UAV. Opening the panel never starts a simulator or flight. WebGL is required; the 2D map remains available without it.

The experimental coverage profile uses valid synthetic observations only: quality ≥0.8, relative altitude 1–8 m, speed ≤3 m/s and a 2 m ground footprint in the flat default simulation world. It unions and clips those footprints in PostGIS. Its score is an uncalibrated weighted feature indicator, not a probability of a landmine or evidence of clearance.

## Survey area progress and reassignment

Supervisors can inspect an area's metadata, operator, change history, sub-missions and completed/live/remaining geographic layers in **Survey Areas**. Completed progress is the non-overlapping union of successful completed attempts using the current coverage profile, clipped to the assigned polygon. Completed flight counts never create progress. Live valid footprints are yellow and excluded from completed percentage; failed/cancelled footprints remain in history and do not become completed area. Completion requires the entire assigned polygon to be covered; rounding cannot produce a false 100%. Status is derived from persisted attempts and coverage: `ASSIGNED`, `IN_PROGRESS`, or `COMPLETED`. All current coverage is mock/experimental, never landmine clearance.

Only Supervisors can create, edit, or reassign an area. Edits require the latest revision and are blocked during active missions. A modified polygon must still contain all linked mission polygons. Reassignment transfers `DRAFT`/`READY` missions to the new operator and resets them to `DRAFT`; prior completed attempts retain their operator and survey history. Expanding an area can reopen its progress. Existing pre-upgrade unassigned missions retain their history/workflow; all newly created missions require an assignment. Assignment lists and history are paginated. See [survey area assignment design and verification](docs/survey-area-assignments.md).

## Checks

```powershell
.\scripts\check.ps1
```

This runs unit tests, frontend interaction tests, TypeScript/production build and Compose validation. Unit tests use SQLite; they do not prove spatial compatibility. Run the disposable database suite, optionally including an actual isolated simulated flight:

```powershell
.\scripts\check-postgis.ps1
.\scripts\check-postgis.ps1 -IncludeSitl
```

The helper creates and removes only a uniquely named test database. The SITL option refuses an already armed simulator and can take several minutes. Do not run it while operating another simulated mission. Advanced manual integration tests require an **empty disposable** database, because they migrate/downgrade its schema:

```powershell
$env:TEST_POSTGIS_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/DISPOSABLE_TEST_DB'
Push-Location backend
& ../.venv/Scripts/python.exe -m pytest tests/test_postgis.py
Pop-Location
Remove-Item Env:TEST_POSTGIS_URL
```

CI configures unit/frontend and AMD64/ARM64 PostGIS jobs; a manually triggered workflow covers actual PX4/Gazebo E2E. Configured jobs are not evidence of remote success. See [prototype verification](docs/prototype-verification.md) for executed checks. Locks are in `backend/requirements-lock.txt`, `simulation/requirements-lock.txt`, and `web/package-lock.json`.

## Structure and remaining work

| Directory | Responsibility |
|---|---|
| `web/` | Role-aware React app and shared components |
| `backend/` | FastAPI, identity/RBAC, migrations, tests |
| `detection/` | Experimental synthetic-feature processor and footprint profile |
| `simulation/` | Authenticated isolated PX4/Gazebo process and MAVLink adapter |
| `mobile/` | Flutter Field Personnel source and widget test |
| `infrastructure/database/` | Native Postgres/PostGIS image build |
| `scripts/` | Windows setup, startup, account provisioning, checks |
| `docs/` | Decisions, data-model plan, visual references, test evidence |

Remaining beyond the connected simulation prototype: validated physical GPR/metal models and calibration data, real-aircraft integration, native Flutter/device builds, background push notifications, configurable approval policy, multiple vehicles, production HTTPS/throttling/MFA/recovery/privilege separation and deployment hardening. Account creation remains explicit through the local provisioning script. The app is for local development, not operational landmine clearance.

PostGIS and the pinned official PX4/Gazebo image built and ran on the local ARM64 Docker engine. Both base images publish AMD64/ARM64 manifests; native AMD64 runtime and full architecture matrices remain unverified. Windows Python used AMD64 wheels. See [data-model.md](docs/data-model.md) for schema and session contracts.

## Account access administration

Sign in as Administrator and open User Management or Roles & Permissions. Select Edit access, choose a role, toggle Account enabled and restrict permissions within that role, then Save access. Restrictions are enforced by FastAPI, including operational endpoints and WebSocket mission access. Changes revoke all sessions for that account. Administrators cannot edit their own access; another administrator is required. Active mission operators cannot be changed until their mission ends. Role templates remain fixed; per-account controls can remove permissions but cannot grant permissions outside the selected role. Account creation still uses the explicit provisioning script.
