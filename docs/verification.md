# Foundation verification — 17 October 2026

Historical first-increment evidence. The connected prototype and current checks are documented in [prototype-verification.md](prototype-verification.md).

## Checks executed locally

| Check | Result |
|---|---|
| Complete read of REQUIREMENTS.md, architecture.md, original README.md | Done before implementation; consistency decisions recorded |
| Backend unit/API tests | 9 passed using isolated SQLite fixtures |
| PostGIS integration | 1 passed against a separate disposable PostgreSQL database: upgrade/downgrade, extension/spatial query, append-only audit trigger, login, RBAC and logout |
| Frontend interaction tests | 8 passed: all five roles, rejected login, admin account retrieval/search, field navigation/disabled stop request/logout |
| TypeScript and Vite production build | Passed |
| Frontend Prettier format check | Passed |
| npm dependency audit | Zero known vulnerabilities after toolchain updates |
| PowerShell script parse checks and Compose configuration | Passed |
| Windows setup.ps1 | Passed with locked dependency install, npm ci, ignored local configuration |
| Windows start-backend.ps1 | Passed: reused healthy DB, migration, API startup; readiness returned 200 |
| Windows start-web.ps1 | Passed: backend readiness check, Vite startup on 127.0.0.1:5173 |
| Docker/PostGIS runtime | Built native linux/arm64 image on aarch64 Docker engine; PostgreSQL 17 / PostGIS 3.6.4 installed, extension ready |
| Base image manifests | postgres:17-bookworm publishes linux/amd64 and linux/arm64/v8; manifest digest 3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826 inspected |
| Python source compilation and repository whitespace checks | Passed |

The default check script skips PostGIS integration unless TEST_POSTGIS_URL is set. The integration test was run separately and passed. The dependency stack emits a Starlette/httpx TestClient deprecation warning; current tests pass. Python packages used Windows AMD64 wheels; this does not establish native Windows ARM64 backend compatibility. Native AMD64 PostGIS runtime and both complete end-to-end architecture matrices remain unverified. CI is configured but has not been run remotely.

## Browser verification

Real FastAPI/PostGIS QA service, test-only accounts in a separate disposable database. Logged into and out of all five roles; checked role-specific content and empty operational states. Administrator account listing and database readiness reached the real API. Desktop views inspected at 1440×1000; Field Personnel at 390×844 (375px content width with scrollbar), with no horizontal overflow. Checked Home, Missions, Detections and Alerts; stop request visibly disabled. QA database and integration database removed afterward; no seeded accounts in the development DB.

Screenshots contain test identities only and no operational mission records:

- [Administrator](screenshots/administrator.jpg)
- [Mission Operator](screenshots/mission-operator.jpg)
- [Detection Analyst](screenshots/detection-analyst.jpg)
- [Supervisor](screenshots/supervisor.jpg)
- [Field Personnel overview](screenshots/field-personnel.jpg)
- [Field Personnel alerts](screenshots/field-alerts.jpg)

Browser inspection prompted a mobile layout refinement: field lists use cards rather than desktop table headers; the narrow login header omits its secondary tagline. Shared component styles use the supplied references, with unavailable maps/sensor graphs clearly labelled rather than fabricated.

## Not verified or implemented

Flutter SDK is absent: native Dart analysis, widget test and device builds were not run. Platform runners are not generated. Mobile-first React rendering was tested; this is separate from native Flutter validation.

PX4/Gazebo/MAVSDK, mission execution, telemetry, detection inference, geospatial coverage algorithms, map tiles, survey-history persistence, reporting and notifications are not implemented. Their empty or disconnected UI states are intentional. No camera functionality or automatic flight startup was added. Simulation/detection packages provide interfaces only.

Development configuration uses a database owner account for setup convenience; production privilege separation, HTTPS, login throttling, recovery/MFA and audit retention remain required before deployment. Survey completion must never imply ground clearance.
