# TerraGuavd — Complete Project Discussion Summary

### Decisions, Features, Modifications, and Architecture

This document summarizes our discussion about TerraGuavd, including the decisions we made about the system foundation, prototype, user roles, interfaces, Docker, cross-platform support, UAV simulation, and survey coverage.
The goal is to establish a shared reference for future development so we don't lose decisions or introduce conflicting features.

---

# 1. Project Identity and Direction

**Project name: TerraGuavd**
We explicitly corrected the name from TerraGuard to TerraGuavd. The spelling must remain consistent across the application, documentation, interfaces, and project files.

### Project objective

TerraGuavd is a software platform for UAV-based landmine detection.
It is intended to help authorized personnel:

- Plan and manage survey missions.
- Monitor UAV flights and telemetry.
- Process sensor data.
- Identify and visualize potential landmine detections.
- Record surveyed areas and their survey dates.
- Review mission results and generate reports.
- Coordinate field personnel and operational teams.

### Software-focused approach

We are developing a software system rather than designing and manufacturing a physical drone.
The platform will integrate with UAV flight-control software and simulation tools, while supporting future integration with physical equipment.
**Important constraints:**

- The system will not have a camera.
- Field Personnel must not have camera functionality.
- Detection results must not be presented as confirmed landmines without appropriate verification.
- The project should support both x86-64 and ARM64 platforms.

---

# 2. The Five User Roles

We discussed how each type of user should have an interface suited to their responsibilities.
We settled on five roles.

## 2.1 System Administrator

**Purpose:** Manage the platform, users, and system configuration.
Main features:

- Manage user accounts.
- Assign roles and permissions.
- Register and manage UAVs.
- Configure system settings.
- Monitor backend and database health.
- Review audit logs and security events.

The administrator manages the software platform rather than routinely operating UAV missions.

## 2.2 Mission Operator

**Purpose:** Plan, execute, and monitor UAV missions.
Main features:

- Create and configure missions.
- Define survey boundaries and waypoints.
- Start, pause, resume, and stop missions through authorized commands.
- Monitor live UAV telemetry.
- View UAV position and mission progress on a map.
- Receive operational alerts.
- Manage mission handovers when supported.
- Review mission history.

This is the primary operational role.

## 2.3 Detection Analyst

**Purpose:** Analyze sensor data and review potential detections.
Main features:

- View potential target locations.
- Review detection classifications and confidence scores.
- Examine available GPR and metal-detector measurements.
- Record assessments.
- Review results from previous missions.
- Generate detection reports.
- Export authorized detection data.

The analyst focuses on interpreting results rather than controlling the aircraft.

## 2.4 Supervisor

**Purpose:** Oversee operations and evaluate mission outcomes.
Main features:

- View active and completed missions.
- Assign missions to operators.
- Approve mission plans when required.
- Review detection summaries.
- Access mission reports.
- Evaluate operational performance.
- Review authorized audit records.

Flight-control permissions should not be granted automatically to supervisors.

## 2.5 Field Personnel

**Purpose:** Monitor assigned missions and receive relevant information while working in the field.
Main features:

- View assigned missions.
- Track the UAV on a live map.
- Receive detection alerts.
- View potential target locations and classification results.
- Monitor UAV position, battery, and flight status.
- View mission progress and history.
- Request a mission stop when authorized.

### Important modification: No camera

We explicitly clarified that TerraGuavd will not have a camera.
Therefore, the Field Personnel interface must not include:

- Live camera feeds.
- Camera screens.
- Camera-based monitoring features.

Its focus is mission information, telemetry, detection results, and alerts.

### Role comparison

| Role              | Main responsibility           | Flight control                       |
| ----------------- | ----------------------------- | ------------------------------------ |
| Administrator     | Manage the platform           | No routine flight control by default |
| Mission Operator  | Execute missions              | Authorized control                   |
| Detection Analyst | Review detections             | No                                   |
| Supervisor        | Oversee operations            | Restricted, if authorized            |
| Field Personnel   | Monitor missions in the field | Limited, if authorized               |

We also established that **roles and permissions should be separate concepts**. The backend must enforce permissions, not merely hide interface elements.

---

# 3. Interface Design

We discussed the appearance and organization of the role-specific interfaces.

### Decision: One web application, not five separate websites

The web application will provide different dashboards according to the user's role.
For example:

| Role              | Main interface                             |
| ----------------- | ------------------------------------------ |
| Administrator     | Administration dashboard                   |
| Mission Operator  | Mission control dashboard                  |
| Detection Analyst | Detection analysis dashboard               |
| Supervisor        | Operational overview                       |
| Field Personnel   | Mobile-friendly field monitoring interface |

The applications will share common design elements, authentication, APIs, and backend services.
Field Personnel will have a mobile-first interface because their primary tasks involve monitoring missions and receiving notifications in the field.
We also created visual interface concepts for the roles and specifically revised the Field Personnel design to match the dark navy, cream, and red theme used in the other TerraGuavd concepts.
These images are **design references**, not implemented application screens.

---

# 4. Foundation Versus Prototype

We clarified the difference between building the project foundation and building the prototype from scratch.

## 4.1 Project foundation

The foundation establishes how the entire system will be built.
It includes:

1. Requirements and system scope.
2. Software architecture.
3. Technology selection.
4. Repository structure.
5. Database design.
6. API contracts.
7. Authentication and authorization.
8. Development environment.
9. Testing strategy.
10. Team integration rules.

The objective is to create a stable structure on which the rest of the system can be developed.

## 4.2 Prototype

The prototype demonstrates that TerraGuavd actually works.
It should include:

- A functional web application.
- Authentication and role-based access.
- Mission creation and management.
- PX4 + Gazebo mission execution.
- Live telemetry.
- Detection processing and result visualization.
- A mobile interface for Field Personnel.
- Survey coverage and history.
- Mission reporting.

The prototype should connect these components into working workflows rather than presenting disconnected screens.

### The central prototype workflow

The workflow we discussed is:
**Operator logs in → creates a mission → starts the mission → PX4 + Gazebo execute it → telemetry appears on the dashboard → detection results are stored and displayed → authorized users review the results → a mission report is generated.**
Field Personnel should receive relevant mission updates and detection alerts without camera functionality.
We also clarified that the project should be built from the beginning when requested, rather than assuming that the existing prototype must be reused.

---

# 5. Technology Stack

We proposed the following technologies for the system.

| Component               | Proposed technology     | Responsibility                       |
| ----------------------- | ----------------------- | ------------------------------------ |
| Web frontend            | React + TypeScript      | Web dashboards                       |
| Mobile application      | Flutter                 | Mobile monitoring                    |
| Backend                 | Python + FastAPI        | APIs and business logic              |
| Database                | PostgreSQL + PostGIS    | Persistent and geographic data       |
| Real-time communication | WebSockets              | Telemetry and live updates           |
| UAV simulation          | PX4 + Gazebo            | Simulated flight execution           |
| UAV communication       | MAVSDK/MAVLink          | Communication with the autopilot     |
| Detection processing    | Python                  | Sensor processing and classification |
| Containerization        | Docker + Docker Compose | Service management                   |
| Version control         | Git + GitHub            | Collaboration and source control     |
| Backend testing         | Pytest                  | Automated tests                      |

These are proposed technologies, not confirmation that every component has been implemented.
Exact versions and compatibility must be verified during implementation.

---

# 6. Docker and the Two-Command Workflow

We discussed simplifying development so you do not need to start every component manually.

### Decision: Two startup commands

The intended development experience is:
**Terminal 1 — Start the backend**

```
.\scripts\start-backend.ps1
```

**Terminal 2 — Start the web application**

```
.\scripts\start-web.ps1
```

These are proposed commands. The scripts still need to be implemented and connected to the actual repository.
The backend startup script should manage the required backend services, including database readiness and migrations.
The web startup script should launch the frontend development server and configure its connection to the backend.

### Start PX4 + Gazebo from the Start Mission button

We agreed on the desired behavior:

1. The operator clicks **Start Mission**.
2. The backend validates the mission.
3. The backend checks whether PX4 + Gazebo are already running.
4. If they are stopped, the backend starts the simulation.
5. It waits for the simulator and vehicle to become ready.
6. It sends the mission through the existing flight-control integration.
7. PX4 executes the mission after the required checks pass.
8. Telemetry flows back to the backend.
9. The dashboard displays mission progress.

If the simulation is already running, the backend should reuse it rather than launch another instance.
**Important:** Starting the simulator must not automatically initiate a flight. Mission execution must follow an explicit, validated request.

### Simulation Manager

We proposed a dedicated backend component responsible for:

- Starting and stopping the simulation.
- Checking simulator readiness.
- Managing the PX4 connection.
- Preventing duplicate instances.
- Reporting startup and communication failures.
- Coordinating mission execution.

This keeps simulation lifecycle logic separate from the mission API and frontend.

---

# 7. Cross-Platform Support: x86-64 and ARM64

This is a core requirement we explicitly established.
**TerraGuavd should support both conventional Intel/AMD computers and ARM64 computers.**
We should not maintain two separate application codebases.

### Proposed strategy

Use one repository with compatible dependencies and architecture-aware container images.

| Component          | x86-64                       | ARM64                        |
| ------------------ | ---------------------------- | ---------------------------- |
| Backend            | Supported                    | Supported                    |
| Web frontend       | Supported                    | Supported                    |
| Database           | Compatible image required    | Compatible image required    |
| Detection engine   | Supported                    | Supported                    |
| Simulation manager | Supported                    | Supported                    |
| PX4 SITL           | Compatibility must be tested | Compatibility must be tested |
| Gazebo             | Compatibility must be tested | Compatibility must be tested |

### Docker strategy

We discussed using multi-platform Docker images where possible.
For example:

```
terraguavd/backend
    ├── linux/amd64
    └── linux/arm64
```

Docker can select the appropriate image for the host when the image publishes both architectures.
However, not every third-party image supports both.
We previously discussed ARM64 image compatibility problems, so we must verify the actual database and simulation images rather than assume compatibility.

### Important simulation decision

We recommended a hybrid approach:

- Use Docker for the database and supporting services.
- Keep the simulation runtime behind a dedicated backend interface.
- Use a compatible PX4 + Gazebo runtime for each architecture.
- Prefer native execution when it is reliable.
- Avoid relying on x86 emulation on ARM64 when a suitable native solution is available.

The backend should expose the same mission workflow regardless of the underlying simulation runtime.

### Compatibility testing

Before declaring support, we must test both architectures for:

- Image builds.
- Database startup and migrations.
- Authentication and API behavior.
- Mission creation.
- Detection processing.
- PX4 + Gazebo startup.
- Mission execution.
- Telemetry delivery.
- End-to-end operation.

A successful Docker build alone does not prove that the simulation runs correctly.

---

# 8. Map Technology

We discussed how TerraGuavd should display mission routes, UAV positions, and detected targets.

### Decision: Leaflet + OpenStreetMap

We recommended:

- **Leaflet:** Interactive map library.
- **OpenStreetMap:** Default geographic map data.
- **PostgreSQL/PostGIS:** Geographic storage and queries.
- **Optional satellite imagery:** An additional layer if a suitable provider is selected.

Official resources:

- [Leaflet](https://leafletjs.com/?utm_source=chatgpt.com)
- [OpenStreetMap](https://www.openstreetmap.org/?utm_source=chatgpt.com)

The map should display:

- Planned mission routes.
- Actual UAV flight paths.
- Current UAV position.
- Survey boundaries.
- Survey coverage.
- Potential detection locations.
- Survey history.

Satellite imagery is optional and requires an appropriate provider. The initial map does not depend on it.

---

# 9. New Feature Added: Survey Coverage & History

This is one of the most important additions from our latest discussion.
You specified that:

> The system should mark a surveyed area and show when it was surveyed.

We expanded that into a feature called **Survey Coverage & History**.
Its purpose is to show which parts of a geographic area have actually been surveyed and when.

## 9.1 Visual map behavior

We proposed the following color scheme:

| Color  | Meaning                            |
| ------ | ---------------------------------- |
| Green  | Survey completed successfully      |
| Yellow | Survey in progress                 |
| Red    | Survey interrupted or unsuccessful |
| Gray   | Not surveyed                       |
| Blue   | Selected survey area               |

The map should also provide labels or other visual indicators so status is not communicated through color alone.
These colors are proposed design choices and can be finalized during UI implementation.

## 9.2 Survey workflow

The intended workflow is:

1. An operator defines a survey boundary.
2. The operator starts the mission.
3. The system records telemetry and available sensor measurements.
4. TerraGuavd determines which portions of the area were adequately surveyed.
5. The system records the resulting coverage and survey timestamps.
6. The map displays the completed and incomplete portions.
7. Users can select an area to review its survey history.

If a mission is interrupted, the system should not mark the entire planned area as completed.
Only the coverage supported by recorded data and the defined coverage rules should be marked as surveyed.

## 9.3 Survey details

Selecting a surveyed area should display information such as:

| Field                | Example         |
| -------------------- | --------------- |
| Survey status        | Completed       |
| Survey date          | 15 October 2026 |
| Start time           | 09:30           |
| Completion time      | 10:12           |
| Mission ID           | MIS-0042        |
| UAV                  | UAV-01          |
| Coverage             | 96%             |
| Potential detections | 4               |
| Last surveyed        | 15 October 2026 |

These values are illustrative, not actual mission results.

## 9.4 Preserve survey history

A new survey must not overwrite the historical record of an earlier survey.
For example:

| Survey   | Date       | Coverage | Result      |
| -------- | ---------- | -------- | ----------- |
| Survey 1 | 10 October | 85%      | Interrupted |
| Survey 2 | 12 October | 100%     | Completed   |
| Survey 3 | 15 October | 96%      | Completed   |

The map can show the latest successful coverage by default while allowing users to inspect previous surveys.
This distinguishes the date an area was last surveyed from the complete history of all surveys performed there.

## 9.5 Flight coverage versus survey coverage

We established an important technical distinction:
**Flight coverage:** Where the UAV actually traveled.
**Survey coverage:** Which portions of the ground were adequately surveyed according to the validated sensor and coverage rules.
These are not necessarily identical.
For example, flying over a location does not automatically prove that the sensor collected adequate measurements there.
Therefore, the green overlay should represent validated survey coverage, not simply the UAV's path.
The coverage calculation will depend on sensor footprint, flight altitude, route spacing, data availability, and telemetry quality.

## 9.6 Where this feature belongs

Survey Coverage & History should be accessible to:

- **Mission Operators:** Plan surveys and monitor progress.
- **Supervisors:** Review coverage and survey dates.
- **Detection Analysts:** Compare coverage with detection results.
- **Field Personnel:** View coverage and survey dates for assigned areas.
- **Administrators:** Access relevant records when needed for system management or auditing.

The feature should use shared backend services and geographic data rather than separate implementations for each role.
**Safety distinction:** A surveyed area is not necessarily a landmine-free area. The map must never imply that survey completion guarantees safety.

---

# 10. Reporting and Data Management

We also discussed storing mission and detection results so the system can generate useful reports.
The proposed data model includes:

| Entity                | Purpose                            |
| --------------------- | ---------------------------------- |
| Users                 | User accounts                      |
| Roles and Permissions | Authorization                      |
| UAVs                  | Aircraft records                   |
| Missions              | Mission configuration and status   |
| Waypoints             | Planned geographic locations       |
| Telemetry             | Flight data and timestamps         |
| Sensor Readings       | Available sensor measurements      |
| Detections            | Potential target results           |
| Survey Coverage       | Geographic areas actually surveyed |
| Survey History        | Records of previous surveys        |
| Alerts                | Operational notifications          |
| Mission Events        | Important mission lifecycle events |
| Audit Logs            | Important user and system actions  |

PostgreSQL/PostGIS would store the geographic data and support operations involving survey boundaries, flight paths, coverage geometry, and target coordinates.
The exact schema and relationships still need to be designed.

---

# 11. Development Order We Established

We discussed both the foundation and the prototype. The following order combines those decisions into a practical implementation plan.

| Phase | Main work                              | Expected outcome                         |
| ----- | -------------------------------------- | ---------------------------------------- |
| 1     | Requirements and role definitions      | Agreed scope and permissions             |
| 2     | Architecture and API contracts         | Defined component boundaries             |
| 3     | Repository and development environment | Reproducible setup                       |
| 4     | Database and backend foundation        | Working data layer and APIs              |
| 5     | Authentication and authorization       | Secure role-based access                 |
| 6     | Web application                        | Functional role-specific dashboards      |
| 7     | Mission management                     | Working mission lifecycle                |
| 8     | PX4 + Gazebo integration               | Simulated mission execution              |
| 9     | Telemetry integration                  | Live updates on the dashboard            |
| 10    | Detection pipeline                     | Stored and visualized detection results  |
| 11    | Survey Coverage & History              | Geographic survey records and timestamps |
| 12    | Mobile application                     | Field Personnel monitoring               |
| 13    | Reports and notifications              | Mission summaries and operational alerts |
| 14    | Cross-platform testing                 | Verified AMD64 and ARM64 support         |
| 15    | End-to-end testing                     | Integrated prototype                     |

Some tasks can be developed in parallel after their interfaces and data contracts are agreed upon.
For example, the frontend can be developed against documented API contracts while the backend implements them.

---

# 12. What We Have Actually Decided Versus What Still Needs Implementation

It is important to distinguish our decisions from completed development work.

### Decisions established in our discussion

- The correct name is **TerraGuavd**.
- The project is software-focused.
- The system has five proposed user roles.
- Field Personnel must not have camera functionality.
- One web application should provide role-specific dashboards.
- The mobile application should support Field Personnel.
- The intended development workflow uses two startup commands.
- The Start Mission button should initiate simulation startup when needed.
- Docker should manage appropriate services.
- The platform should support AMD64 and ARM64.
- PX4 + Gazebo must be compatible with the target architecture.
- Leaflet and OpenStreetMap are the proposed default mapping solution.
- Survey Coverage & History is a core feature.
- The system must distinguish actual flight paths from validated survey coverage.
- Survey records and timestamps must be preserved.
- Survey completion must not imply that an area is free of landmines.

### Items that still need to be built or verified

- Final requirements and permission definitions.
- Repository structure and implementation.
- Database schema and migrations.
- API contracts.
- Authentication and role enforcement.
- The five role-specific interfaces.
- The two startup scripts.
- Automatic simulation startup from the mission workflow.
- PX4 readiness and mission execution handling.
- Telemetry integration.
- Detection processing and validation.
- Survey coverage calculation and visualization.
- Survey history storage and retrieval.
- Mobile notifications.
- AMD64 and ARM64 compatibility tests.
- End-to-end automated tests.

The proposed startup commands and architecture are design decisions, not evidence that the features are already implemented.

---

# 13. Final Agreed Vision for TerraGuavd

The system we have been discussing is a cross-platform UAV landmine-detection software platform with:
**Five user roles**

- System Administrator
- Mission Operator
- Detection Analyst
- Supervisor
- Field Personnel

**Two primary user applications**

- Web application for mission operations, detection analysis, supervision, and administration.
- Mobile application for Field Personnel.

**A shared backend**

- Authentication and authorization.
- Mission management.
- Telemetry.
- Detection processing and results.
- Geographic data.
- Survey coverage and history.
- Alerts and reports.

**A simulation integration**

- PX4 + Gazebo.
- On-demand startup through the backend.
- Explicit mission execution.
- Live telemetry.
- Compatible runtimes for AMD64 and ARM64.

**A geographic survey-history feature**

- Mark surveyed areas on the map.
- Show when each area was surveyed.
- Calculate and display validated coverage.
- Preserve previous survey records.
- Display potential detection locations.
- Distinguish completed surveys from confirmed safe areas.

**A streamlined development experience**

- One backend startup command.
- One web startup command.
- The Start Mission button manages simulation startup and mission execution.

## My conclusion

The most significant new functional requirement we added was **Survey Coverage & History**. The most important architectural constraints we clarified were **cross-platform support, role-based authorization, no camera functionality, and on-demand PX4 + Gazebo startup**.
These decisions should now serve as the reference for future TerraGuavd architecture, implementation, UI design, and testing.