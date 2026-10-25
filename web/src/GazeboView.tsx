import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { request } from "./api";

type SceneData = {
  live: boolean;
  source?: string;
  pose: {
    position: [number, number, number];
    quaternion: [number, number, number, number];
  } | null;
  notice?: string;
};
const active = [
  "STARTING_SIMULATION",
  "WAITING_FOR_VEHICLE",
  "UPLOADING",
  "EXECUTING",
  "PAUSED",
  "RESUMING",
  "CANCELLING",
];

export default function GazeboView({
  token,
  missionId,
  state,
}: {
  token: string;
  missionId: string;
  state: string;
}) {
  const host = useRef<HTMLDivElement>(null);
  const latest = useRef<SceneData | null>(null);
  const received = useRef(0);
  const reset = useRef<() => void>(() => {});
  const follow = useRef(true);
  const [following, setFollowing] = useState(true);
  const [status, setStatus] = useState("Waiting for Gazebo");
  const [graphicsError, setGraphicsError] = useState("");
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    latest.current = null;
    if (!active.includes(state)) {
      setStatus("No live scene · start a validated simulated mission");
      return;
    }
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const data = await request<SceneData>(
          `/missions/${missionId}/scene`,
          token,
          { signal: AbortSignal.timeout(2500) },
        );
        if (!alive) return;
        latest.current = data;
        received.current = performance.now();
        setStatus(
          data.live && data.source === "gazebo-world-pose"
            ? "Live Gazebo world poses"
            : data.notice || "Waiting for fresh Gazebo world poses",
        );
      } catch (error) {
        if (alive) {
          latest.current = null;
          setStatus((error as Error).message);
        }
      }
      if (alive) timer = setTimeout(poll, 250);
    };
    poll();
    return () => {
      alive = false;
      clearTimeout(timer);
      latest.current = null;
    };
  }, [token, missionId, state]);

  useEffect(() => {
    if (!host.current) return;
    const container = host.current;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      setGraphicsError(
        "WebGL is unavailable. The 2D map and telemetry remain available.",
      );
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.domElement.setAttribute(
      "aria-label",
      "Interactive Gazebo world visualization",
    );
    container.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#091922");
    // Gazebo uses Z-up. Keep its coordinates and quaternion unchanged.
    const camera = new THREE.PerspectiveCamera(48, 1, 0.05, 2000);
    camera.up.set(0, 0, 1);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.maxDistance = 250;
    controls.minDistance = 1;
    const grid = new THREE.GridHelper(200, 100, "#678078", "#263f46");
    grid.rotation.x = Math.PI / 2;
    scene.add(grid);
    scene.add(new THREE.HemisphereLight("#fff4d5", "#213943", 3));
    const light = new THREE.DirectionalLight("#ffffff", 3);
    light.position.set(20, -20, 40);
    scene.add(light);
    const uav = new THREE.Group();
    const material = new THREE.MeshStandardMaterial({
      color: "#eee1b7",
      roughness: 0.5,
    });
    const accent = new THREE.MeshStandardMaterial({ color: "#e84e5e" });
    const body = new THREE.Mesh(
      new THREE.BoxGeometry(0.25, 0.18, 0.12),
      material,
    );
    body.position.z = 0.24;
    uav.add(body);
    for (const x of [-0.174, 0.174])
      for (const y of [-0.174, 0.174]) {
        const arm = new THREE.Mesh(
          new THREE.BoxGeometry(0.5, 0.025, 0.025),
          material,
        );
        arm.rotation.z = Math.atan2(y, x);
        arm.position.z = 0.24;
        uav.add(arm);
        const rotor = new THREE.Mesh(
          new THREE.TorusGeometry(0.13, 0.012, 8, 32),
          x > 0 ? accent : material,
        );
        rotor.position.set(x, y, 0.3);
        uav.add(rotor);
      }
    // Display enlargement only, not a physical size measurement.
    uav.scale.setScalar(4);
    scene.add(uav);
    reset.current = () => {
      const target = uav.visible ? uav.position : new THREE.Vector3();
      controls.target.copy(target);
      camera.position.copy(target).add(new THREE.Vector3(18, -24, 18));
      controls.update();
    };
    reset.current();
    const observer = new ResizeObserver(() => {
      const width = container.clientWidth,
        height = container.clientHeight;
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    });
    observer.observe(container);
    let previous = new THREE.Vector3();
    let initialized = false;
    renderer.setAnimationLoop(() => {
      const data = latest.current;
      uav.visible = !!(
        performance.now() - received.current < 3000 &&
        data?.live &&
        data.source === "gazebo-world-pose" &&
        data.pose
      );
      if (uav.visible && data?.pose) {
        uav.position.fromArray(data.pose.position);
        uav.quaternion.fromArray(data.pose.quaternion).normalize();
        if (!initialized) {
          reset.current();
          initialized = true;
        } else if (follow.current) {
          camera.position.add(
            new THREE.Vector3().subVectors(uav.position, previous),
          );
          controls.target.copy(uav.position);
        }
        previous.copy(uav.position);
      }
      controls.update();
      renderer.render(scene, camera);
    });
    return () => {
      observer.disconnect();
      renderer.setAnimationLoop(null);
      controls.dispose();
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose();
        const materials = Array.isArray(mesh.material)
          ? mesh.material
          : [mesh.material];
        materials.forEach((m) => m?.dispose());
      });
      renderer.dispose();
      renderer.domElement.remove();
      reset.current = () => {};
    };
  }, [missionId]);
  return (
    <div className={expanded ? "gazebo-view expanded" : "gazebo-view"}>
      <div className="actions">
        <strong role="status">{status}</strong>
        <button
          onClick={() => {
            follow.current = !following;
            setFollowing(!following);
          }}
          aria-pressed={following}
        >
          Follow UAV
        </button>
        <button onClick={() => reset.current()}>Reset view</button>
        <button onClick={() => setExpanded(!expanded)}>
          {expanded ? "Close expanded view" : "Expand 3D view"}
        </button>
      </div>
      {graphicsError && <p role="alert">{graphicsError}</p>}
      <div className="gazebo-canvas" ref={host} />
      <p className="panel-note">
        Drag to orbit · Scroll to zoom · Right-drag to pan. Read-only Gazebo
        world poses, browser-rendered with a simplified UAV enlarged 4×. No
        camera feed. The grid is the default flat simulation world; it is not
        surveyed terrain. Sensor results use mock data.
      </p>
    </div>
  );
}
