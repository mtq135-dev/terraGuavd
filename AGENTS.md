# TerraGuavd development rules

Read REQUIREMENTS.md, architecture.md and README.md before changing behavior. Record ambiguities in docs/consistency-review.md. Use TerraGuavd consistently.

- No camera UI, ingestion, permissions or dependencies.
- Prototype is simulation-only. Never label model output as a verified landmine or surveyed ground as cleared/safe.
- Keep web/, backend/, mobile/, detection/, simulation/ and infrastructure/ independently owned. Shared API changes require cross-module review and OpenAPI updates.
- FastAPI is the authority for identity and permissions. Roles map to permissions; UI visibility is not authorization. Operators require mission assignment for future commands. Administrators and supervisors get no flight control by default.
- Simulation lifecycle is separate from flight commands. Startup never arms, uploads or starts a mission. Commands require explicit authorization, validation, assignment, state and simulator-mode checks. The user has authorized the connected prototype increment: support isolated SITL only; never connect this prototype to physical aircraft.
- Separate planned polygons, flight tracks, readings and validated coverage. Preserve survey attempts and UTC timestamps; never fabricate telemetry or coverage.
- New missions require a Supervisor-owned survey area assignment. Enforce parent ownership and geometric containment on create/validate/start. Lock parent assignments before child missions. Progress unions completed valid footprint coverage, never mission counts; live footprints cannot complete an area. Preserve assignment revisions and history.
- Explicitly opted-in synthetic sensor fixtures are permitted for simulation demos/tests only. Preserve synthetic provenance and experimental algorithm versions throughout UI, API, storage and reports. Never substitute fixture results for physical measurements or verified ground clearance.
- PostgreSQL/PostGIS is the runtime store. Use versioned Alembic migrations; SQLite is only a unit-test substitute. Do not use create_all at application startup.
- No committed secrets, default accounts or plaintext passwords. Use ignored local configuration and explicit account provisioning. Audit security events without recording passwords or tokens.
- One codebase for AMD64/ARM64. Prefer native multi-architecture dependencies; record actual tests separately from intended compatibility. No hard-coded platform emulation.
- Run backend tests, frontend tests/typecheck/build and Compose validation. Database, browser and simulator tests must be reported as unverified if unavailable.
- Use codex/ feature branches and reviewed PRs. Do not merge untested flight-control changes. Keep QGroundControl diagnostic-only.
