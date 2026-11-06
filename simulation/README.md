# Isolated PX4/Gazebo runtime

Docker builds on a digest-pinned official `px4io/px4-sitl-gazebo` multi-architecture image. The service starts an authenticated Python API only. `/runtime/start` starts/reuses the headless x500 simulator without uploading, arming or flying. Explicit mission requests arrive only after backend identity, permission, assignment, state, geometry and vehicle-lease checks. A fixed MAVLink allowlist uploads takeoff/speed/waypoints/RTL; no API-provided shell commands execute. No physical aircraft endpoints, devices or externally published MAVLink ports exist.

The adapter checks fresh heartbeat and global-position messages, bounded upload/command acknowledgements, disarmed upload/start prerequisites, near-home routes and simulator provenance. Pause/resume uses PX4 Hold/Mission modes; cancellation requests RTL. The backend retains its lease until disarming, persists telemetry and stops the isolated process group on failure or lifecycle recovery. One API worker, one simulator and one active test session are supported.

Only the authenticated service API is exposed on localhost:8090. MAVLink binds container loopback and never redirects to the host. Do not enable QGroundControl control concurrently. The default model has no camera sensor integration in TerraGuavd. The runtime is native ARM64 tested; AMD64 manifests exist but native AMD64 runtime testing remains pending. See docs/prototype-verification.md and the optional `scripts/check-postgis.ps1 -IncludeSitl` check. `docker compose stop simulation` stops its service and processes.

Upstream runtime layout and environment: https://docs.px4.io/main/en/simulation/px4_sitl_prebuilt_packages . Dependencies are locked in requirements-lock.txt; requirements.txt records direct version ranges for intentional updates.

## Pre-arm readiness

Fresh telemetry establishes connectivity only. Explicit mission start additionally waits up to 30 seconds for a fresh `SYS_STATUS` with the `MAV_SYS_STATUS_PREARM_CHECK` health bit before sending the normal arm command. PX4 sets this health bit without setting the corresponding presence bit. Failed checks remain enforced; force arming and disabled checks are not used. Rejections include recent PX4 status text. References: [MAVLink SYS_STATUS](https://mavlink.io/en/messages/common.html#SYS_STATUS), [PX4 health encoding](https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/mavlink/streams/SYS_STATUS.hpp).

Regression tests, using the running service's installed Python dependencies without starting a flight:

```powershell
docker compose cp simulation/tests/test_prearm.py simulation:/tmp/test_prearm.py
docker compose exec -T -e PYTHONPATH=/srv simulation /opt/terraguavd/bin/python /tmp/test_prearm.py
```

Failed mission attempts remain immutable history. Create and validate a new draft to repeat a failed survey.

## Web 3D view

The runtime starts a fixed `gz topic -e -t /world/default/pose/info --json-output` subscriber with PX4/Gazebo. It selects only `x500_0` and serves its world position/quaternion at authenticated `/scene`. No Gazebo control commands or sensor images are forwarded. Missing, stopped, or older-than-three-second poses return `live:false` and no pose. FastAPI scopes this to the current mission's active vehicle lease; the browser never receives the runtime secret. The Three.js panel is a simplified browser visualization driven by real Gazebo poses, not the native desktop GUI or full scene-asset renderer. Coordinates retain Gazebo Z-up meters and quaternion xyzw. No new ports are exposed.

Additional no-flight tests:

```powershell
docker compose cp simulation/tests/test_scene.py simulation:/tmp/test_scene.py
docker compose exec -T -e PYTHONPATH=/srv simulation /opt/terraguavd/bin/python /tmp/test_scene.py
```
# Two isolated runtime channels

The fleet increment runs this unchanged single-vehicle runtime in two independent Compose containers, published only on localhost 8090 and 8091. Their Gazebo partitions are distinct. Each service starts idle and launches its own x500 only on an explicit authorized mission request through FastAPI. The runtime never accepts arbitrary physical-aircraft transports. Two concurrent flights were exercised; other airframe profiles remain unsupported. See ../docs/multi-uav.md for contracts and executed evidence.

## Three-channel profile matrix

The three Compose services expose authenticated local runtime APIs at 8090, 8091 and 8092, each in a separate Gazebo transport partition. Runtime start accepts only `px4-x500` or `px4-x500-lidar-down`; the latter uses installed airframe 4016 and the camera-free downward-LiDAR model. A profile switch is rejected while armed. Selected model names also control the read-only scene pose filter. No camera data is exposed or consumed. Run the opt-in fleet matrix as described in [fleet-test-matrix.md](../docs/fleet-test-matrix.md); type categories without a tested allowlisted profile remain catalog-only.

## Per-mission geographic world origin

Explicit mission start passes the first survey waypoint as the isolated world origin. The installed PX4 Gazebo startup sets its spherical coordinates through PX4_HOME_LAT/LON/ALT before model creation; elevation is the synthetic flat-world default of 488 m. A model/origin change is forbidden while armed. Existing local route-distance, readiness and prearm checks remain active. The backend also rejects oversized executable sectors at preview/start. These coordinates are actual simulated MAVLink positions, not relabelled telemetry or surveyed terrain.
