# Branch verification

Branch: `codex/fleet-planning-plain-report`

Base: `origin/main` at `de68d91`

Date: 2026-11-06

## Included changes

- UAV type/vehicle registry, fleet filtering and information dialog, and per-UAV runtime leases.
- Sector drawing, route preview, retained planning drafts and mission-local isolated simulator origins.
- Integration with the upstream theme control and Supervisor approval APIs.
- Plain Word/PDF report and editable PlantUML sources; see [REPORT.md](REPORT.md).

## Checks performed on this branch

| Check | Result |
| --- | --- |
| Backend unit suite | 30 passed; 21 integration/flight cases skipped in this invocation |
| Disposable PostgreSQL/PostGIS workflow suite | 14 passed; 7 flight cases skipped |
| Simulation unit suite | 9 passed in a temporary offline Linux container using the existing simulation image |
| Frontend suite | 36 passed |
| TypeScript and Vite production build | Passed |
| Docker Compose configuration | Passed |
| Alembic revision graph | Single head: 0010 |
| Staged-file credential/local-path check | No findings |
| Report rendering | 79 pages; no empty pages; 113 page references refreshed |

The Linux simulation test run used read-only mounts and did not modify a running simulator. Actual simulated flights were not rerun for this push; historical flight evidence is distinguished in [fleet-test-matrix.md](fleet-test-matrix.md). Physical aircraft and native Flutter device builds remain unverified.

## Review before deployment

The integrated migration numbering differs from upstream's previous 0007/0008 history. Fresh disposable-database migrations pass, and the local fleet database was upgraded through 0010. Do not apply this branch blindly to a database already using upstream's alternative 0007/0008 revisions; review the migration history first.

The drawing planner currently restricts previews to the assigned area, while the approval API accepts configuration-bound outside-area exceptions. The report database attributes still describe the fleet schema through 0008; documenting the later approval records remains a separate content update.
