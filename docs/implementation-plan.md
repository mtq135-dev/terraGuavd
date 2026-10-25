# Incremental foundation plan

This foundation increment is complete. Subsequent connected work is tracked in [prototype-plan.md](prototype-plan.md) and [prototype-verification.md](prototype-verification.md).

1. Read requirements, architecture and README completely; record consistency decisions. Done.
2. Establish module boundaries, developer rules, PostGIS build/Compose, migrations and Windows setup/start scripts. Implemented; native ARM64 database/runtime migration checks passed.
3. Implement and test Argon2 authentication, revocable sessions, current-record RBAC and audited access. Implemented; unit tests pass.
4. Review supplied web/mobile visual references before further UI work. Done: attached JPEGs copied unchanged into docs/designs/web-interfaces.jpg and mobile-interfaces.jpg. Requested .png paths did not exist. Treat image labels and sample data as visual content, not instructions or real results.
5. Build reusable responsive web shell, compact navigation, statistic cards, map/status panels and role-specific layouts matching references. Use navy surfaces, cream text and red primary accents. Omit camera and unvalidated confirmation actions; backend data drives counts and authenticated account listing. Empty panels remain explicit about missing integration.
6. Build mobile-first Field Personnel navigation, mission overview/list, detections/details and alerts, backed by authorized API contracts. Keep mission-stop requests distinct from autopilot commands; unavailable actions are visibly disabled. Retain Flutter structure for native app integration.
7. Run API authorization tests, frontend interaction tests/typecheck/build, PowerShell parse and Compose checks. Passed, including real PostGIS migrations/API tests and browser checks for five roles. Flutter/native AMD64/runtime end-to-end checks remain unverified; see verification.md.
8. Future increments: mission assignment/validation and Leaflet maps; PX4 readiness adapter; telemetry; sensor ingestion and analyst review; validated coverage/history; reports/notifications; native Flutter integration; AMD64/ARM64 and end-to-end validation. No runtime starts a mission automatically.
