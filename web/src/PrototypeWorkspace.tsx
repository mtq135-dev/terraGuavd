import {
  FormEvent,
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useState,
} from "react";
import { Dashboard, Identity, request } from "./api";
import { Empty, Panel } from "./components";
import { Mission, MissionDetail, Target } from "./operations-api";
import SurveyMap from "./SurveyMap";
import PlanMap from "./PlanMap";
import SurveyAreas from "./SurveyAreas";
import DetectionList, {
  detectionLabel,
  usesLegacyMockLabel,
} from "./DetectionList";
import { SurveyArea } from "./survey-areas-api";
const GazeboView = lazy(() => import("./GazeboView"));

function points(value: string): [number, number][] {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) &&
      parsed.every(
        (p) =>
          Array.isArray(p) &&
          p.length === 2 &&
          p.every((n) => typeof n === "number" && Number.isFinite(n)),
      )
      ? parsed
      : [];
  } catch {
    return [];
  }
}

const boundary = [
  [8.5453, 47.3976],
  [8.5459, 47.3976],
  [8.5459, 47.39794],
  [8.5453, 47.39794],
  [8.5453, 47.3976],
];
const waypoints = [
  [8.5454, 47.3977],
  [8.5458, 47.3977],
  [8.5458, 47.39784],
  [8.5454, 47.39784],
];
const active = [
  "STARTING_SIMULATION",
  "WAITING_FOR_VEHICLE",
  "UPLOADING",
  "EXECUTING",
  "PAUSED",
  "CANCELLING",
];
type Person = { id: string; username: string; role: string };

export default function PrototypeWorkspace({
  token,
  user,
  data,
  view,
  onViewChange,
}: {
  token: string;
  user: Identity;
  data?: Dashboard;
  view: string;
  onViewChange?: (view: string) => void;
}) {
  const [missions, setMissions] = useState<Mission[]>(
    (data?.missions ?? []) as Mission[],
  );
  const [selected, setSelected] = useState("");
  const [boundaryText, setBoundaryText] = useState(JSON.stringify(boundary));
  const [waypointText, setWaypointText] = useState(JSON.stringify(waypoints));
  const [detail, setDetail] = useState<MissionDetail>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [people, setPeople] = useState<Person[]>([]);
  const [areas, setAreas] = useState<SurveyArea[]>([]);
  const [areaPages, setAreaPages] = useState(1);
  const [assignmentId, setAssignmentId] = useState("");
  const [target, setTarget] = useState<Target>();
  const [history, setHistory] = useState<
    {
      id: string;
      mission_id: string;
      status: string;
      coverage_percent: number;
      finished_at: string;
    }[]
  >([]);
  const [connection, setConnection] = useState("No mission selected");
  const operator = user.role === "mission_operator";
  const areaAccess = operator || user.role === "supervisor";
  const parent = areas.find((area) => area.id === assignmentId);
  const refreshAreas = useCallback(async () => {
    if (!areaAccess) return;
    try {
      const batches = await Promise.all(
        Array.from({ length: areaPages }, (_, page) =>
          request<SurveyArea[]>(
            `/survey-areas?offset=${page * 100}&limit=100`,
            token,
          ),
        ),
      );
      setAreas(
        batches.flatMap((result) => (Array.isArray(result) ? result : [])),
      );
    } catch (error) {
      setError((error as Error).message);
      setAreas([]);
    }
  }, [token, areaAccess, areaPages]);
  useEffect(() => {
    refreshAreas();
    const timer = setInterval(refreshAreas, 5000);
    return () => clearInterval(timer);
  }, [refreshAreas]);
  const field = user.role === "field_personnel";
  const analyst = user.permissions.includes("detections:review");
  const parentStillAssigned =
    !detail?.mission.assignment_id ||
    areas.some(
      (area) =>
        area.id === detail.mission.assignment_id &&
        area.operator_id === user.id,
    );
  const canPlan =
    operator &&
    parentStillAssigned &&
    detail?.mission.operator_id === user.id &&
    user.permissions.includes("missions:plan");
  const canCommand =
    operator &&
    parentStillAssigned &&
    detail?.mission.operator_id === user.id &&
    user.permissions.includes("missions:execute");
  const refreshMissions = useCallback(async () => {
    try {
      const list = await request<Mission[]>("/missions", token);
      setMissions(list);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [token]);
  useEffect(() => {
    setMissions((data?.missions ?? []) as Mission[]);
  }, [data]);
  useEffect(() => {
    const interval = setInterval(refreshMissions, 3000);
    return () => clearInterval(interval);
  }, [refreshMissions]);
  useEffect(() => {
    if (!selected) return;
    let alive = true;
    let socket: WebSocket | undefined;
    const fetchDetail = async () => {
      try {
        const result = await request<MissionDetail>(
          `/missions/${selected}`,
          token,
        );
        if (alive) setDetail(result);
      } catch (e) {
        if (alive) {
          setError((e as Error).message);
          if ((e as Error).message === "Mission not found") {
            setSelected("");
            setDetail(undefined);
            setTarget(undefined);
            setMessage("");
          }
        }
      }
    };
    fetchDetail();
    socket = new WebSocket(
      `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/v1/ws/missions/${selected}`,
    );
    socket.onopen = () => {
      socket?.send(JSON.stringify({ token }));
      setConnection("Live SITL event stream");
    };
    socket.onmessage = (event) => {
      if (alive) setDetail(JSON.parse(event.data));
    };
    socket.onclose = () => {
      if (alive)
        setConnection(
          "Event stream disconnected · using authenticated polling",
        );
    };
    const interval = setInterval(fetchDetail, 5000);
    return () => {
      alive = false;
      clearInterval(interval);
      socket?.close();
    };
  }, [selected, token]);
  useEffect(() => {
    if (!detail?.mission.area_id) return;
    request<typeof history>(`/areas/${detail.mission.area_id}/surveys`, token)
      .then(setHistory)
      .catch((e) => setError(e.message));
  }, [detail?.mission.id, detail?.mission.state, token]);
  useEffect(() => {
    if (view === "Team Management" || view === "Mission Planning")
      request<Person[]>("/mission-users", token)
        .then(setPeople)
        .catch((e) => setError(e.message));
  }, [view, token]);
  async function act(command: string) {
    if (!selected) return;
    setMessage("");
    setBusy(true);
    setError("");
    try {
      await request(`/missions/${selected}/${command}`, token, {
        method: "POST",
      });
      setDetail(await request<MissionDetail>(`/missions/${selected}`, token));
      await refreshMissions();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      if (!parent)
        throw new Error(
          "Select a survey area assigned by your Supervisor first.",
        );
      const mission = await request<Mission>("/missions", token, {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          area_id: form.get("area_id"),
          assignment_id: parent.id,
          boundary: JSON.parse(String(form.get("boundary"))),
          waypoints: JSON.parse(String(form.get("waypoints"))),
          altitude_m: Number(form.get("altitude")),
          speed_m_s: Number(form.get("speed")),
          synthetic_sensors: form.get("synthetic") === "on",
          field_ids: form.getAll("field_ids"),
        }),
      });
      setDetail(undefined);
      setSelected(mission.id);
      await refreshMissions();
      setMessage("Draft saved. Validate, then explicitly start when ready.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function assess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!target) return;
    const form = new FormData(event.currentTarget);
    try {
      await request(`/detections/${target.id}/reviews`, token, {
        method: "POST",
        body: JSON.stringify({
          assessment: form.get("assessment"),
          notes: form.get("notes"),
        }),
      });
      setDetail(await request<MissionDetail>(`/missions/${selected}`, token));
      setMessage("Assessment recorded. This does not verify a landmine.");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function stop(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const response = await request<{ notice: string }>(
        `/missions/${selected}/stop-request`,
        token,
        {
          method: "POST",
          body: JSON.stringify({ reason: form.get("reason") }),
        },
      );
      setMessage(response.notice);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function download(format: "json" | "csv") {
    try {
      const response = await fetch(
        `/api/v1/missions/${selected}/report?format=${format}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!response.ok) throw new Error("Report access failed");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `terraguavd-${selected}.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const telemetry = detail?.observations.at(-1);
  const home = ["Dashboard", "Home"].includes(view);
  const showMap =
    home ||
    [
      "Live Monitoring",
      "Map View",
      "Map & Results",
      "Missions Overview",
    ].includes(view);
  const showDetections =
    home || ["Detection Review", "Detections", "Classification"].includes(view);
  const showHistory =
    home || ["Mission History", "Missions", "Reports"].includes(view);
  const showCommands =
    operator &&
    (home || ["Mission Planning", "Live Monitoring"].includes(view));
  const showReports = ["Reports", "Export Data"].includes(view);
  return (
    <div className="prototype-workspace">
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="view-banner" role="status">
          {message}
        </p>
      )}
      {areaAccess && ["Dashboard", "Survey Areas"].includes(view) && (
        <SurveyAreas
          token={token}
          user={user}
          areas={areas}
          onRefresh={refreshAreas}
          onLoadMore={() => setAreaPages(areaPages + 1)}
          hasMore={areas.length === areaPages * 100}
          onPlan={(area) => {
            setAssignmentId(area.id);
            setBoundaryText("[]");
            setWaypointText("[]");
            onViewChange?.("Mission Planning");
          }}
        />
      )}
      {["Approvals", "UAV Fleet"].includes(view) && (
        <Panel
          title={
            view === "Approvals"
              ? "Mission approval policy"
              : "Configured UAV fleet"
          }
        >
          {view === "Approvals" ? (
            <p>
              Separate supervisor approval is not configured in this prototype.
              Assigned operators validate their mission plans; assignment
              management is available in Survey Areas.
            </p>
          ) : (
            <>
              <strong>sitl-01 - PX4 x500 / Gazebo</strong>
              <p>
                One isolated simulated vehicle. View Missions Overview for
                assigned mission status. Physical aircraft are outside this
                prototype.
              </p>
            </>
          )}
        </Panel>
      )}
      {!["Survey Areas", "Approvals", "UAV Fleet"].includes(view) && (
        <>
          {view === "More" ? (
            <Panel title="Account & permissions">
              <p>
                {user.username} · {user.role.replaceAll("_", " ")}
              </p>
              <ul>
                {user.permissions.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </Panel>
          ) : (
            <>
              {operator && view === "Mission Planning" && (
                <Panel title="Create simulated survey mission">
                  <form onSubmit={create}>
                    <label>
                      Assigned survey area
                      <select
                        required
                        value={assignmentId}
                        onChange={(event) => {
                          setAssignmentId(event.target.value);
                          setBoundaryText("[]");
                          setWaypointText("[]");
                        }}
                      >
                        <option value="">
                          Select a Supervisor-assigned area
                        </option>
                        {areas
                          .filter((area) => area.operator_id === user.id)
                          .map((area) => (
                            <option key={area.id} value={area.id}>
                              {area.name} ·{" "}
                              {area.progress.coverage_percent.toFixed(2)}%
                              completed
                            </option>
                          ))}
                      </select>
                    </label>
                    {!areas.length && (
                      <p className="panel-note">
                        A Supervisor must assign a survey area before you can
                        create a new mission.
                      </p>
                    )}
                    <div className="grid two">
                      <label>
                        Mission name
                        <input
                          name="name"
                          required
                          maxLength={100}
                          defaultValue="SITL survey"
                        />
                      </label>
                      <label>
                        Survey area ID
                        <input
                          name="area_id"
                          required
                          pattern="[a-zA-Z0-9_-]+"
                          defaultValue="sitl-area-a"
                        />
                      </label>
                      <label>
                        Altitude (m)
                        <input
                          name="altitude"
                          type="number"
                          min={2}
                          max={8}
                          step="0.5"
                          defaultValue={5}
                        />
                      </label>
                      <label>
                        Speed (m/s)
                        <input
                          name="speed"
                          type="number"
                          min="0.5"
                          max={3}
                          step="0.5"
                          defaultValue={2}
                        />
                      </label>
                    </div>
                    <PlanMap
                      boundary={points(boundaryText)}
                      waypoints={points(waypointText)}
                      onBoundary={(value) =>
                        setBoundaryText(JSON.stringify(value))
                      }
                      onWaypoints={(value) =>
                        setWaypointText(JSON.stringify(value))
                      }
                      assignedBoundary={parent?.boundary}
                    />
                    <label>
                      Boundary · closed [longitude, latitude] ring
                      <textarea
                        name="boundary"
                        required
                        value={boundaryText}
                        onChange={(event) =>
                          setBoundaryText(event.target.value)
                        }
                      />
                    </label>
                    <label>
                      Waypoints · [longitude, latitude] pairs
                      <textarea
                        name="waypoints"
                        required
                        value={waypointText}
                        onChange={(event) =>
                          setWaypointText(event.target.value)
                        }
                      />
                    </label>
                    <label className="check-label">
                      <input name="synthetic" type="checkbox" defaultChecked />
                      Use mock GPR/metal sensor data and synthetic detections
                    </label>
                    <label>
                      Assigned Field Personnel
                      <select name="field_ids" multiple>
                        {people
                          .filter((p) => p.role === "field_personnel")
                          .map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.username}
                            </option>
                          ))}
                      </select>
                    </label>
                    <p className="panel-note">
                      Default coordinates are near the PX4 simulator home. No
                      mission runs on save. Synthetic features are experimental
                      fixtures, not physical sensor measurements.
                    </p>
                    <button className="primary" disabled={busy || !parent}>
                      Save draft mission
                    </button>
                  </form>
                </Panel>
              )}
              <Panel
                title={field ? "Assigned missions" : "Mission workspace"}
                action={
                  <button disabled={busy} onClick={refreshMissions}>
                    Refresh missions
                  </button>
                }
              >
                {!missions.length ? (
                  <Empty>
                    No missions recorded.{" "}
                    {operator
                      ? "Use Mission Planning to create a survey."
                      : "Your authorized missions will appear here."}
                  </Empty>
                ) : (
                  <div className="mission-cards">
                    {missions.map((m) => (
                      <button
                        className={
                          selected === m.id
                            ? "mission-card selected"
                            : "mission-card"
                        }
                        key={m.id}
                        onClick={() => {
                          setSelected(m.id);
                          setDetail(undefined);
                          setMessage("");
                          setTarget(undefined);
                        }}
                      >
                        <strong>{m.name}</strong>
                        <span className="status neutral">
                          {m.state.replaceAll("_", " ")}
                        </span>
                        <small>
                          {m.area_id} ·{" "}
                          {new Date(m.created_at).toLocaleString()} · SITL
                        </small>
                        <small>
                          {m.synthetic_sensors
                            ? "Synthetic sensor fixtures enabled"
                            : "Telemetry only · no sensor coverage"}
                        </small>
                      </button>
                    ))}
                  </div>
                )}
                {areas.length === areaPages * 100 && (
                  <button
                    type="button"
                    onClick={() => setAreaPages(areaPages + 1)}
                  >
                    Load more assigned areas
                  </button>
                )}
              </Panel>
              {view === "Export Data" && !detail && (
                <Empty>
                  Select a mission above to preview its stored data and export
                  files.
                </Empty>
              )}
              {detail && (
                <>
                  <div className="view-banner">
                    <strong>{detail.mission.name}</strong> ·{" "}
                    {detail.mission.state} · {connection}
                    {detail.mission.error && (
                      <p role="alert">{detail.mission.error}</p>
                    )}
                  </div>
                  {showCommands && (canCommand || canPlan) && (
                    <Panel title="Assigned operator commands">
                      <div className="command-row">
                        <button
                          disabled={
                            busy ||
                            !canPlan ||
                            !["DRAFT", "READY"].includes(detail.mission.state)
                          }
                          onClick={() => act("validate")}
                        >
                          Validate plan
                        </button>
                        <button
                          className="primary-inline"
                          disabled={
                            busy ||
                            !canCommand ||
                            detail.mission.state !== "READY"
                          }
                          onClick={() => act("start")}
                        >
                          Start simulated mission
                        </button>
                        <button
                          disabled={
                            busy ||
                            !canCommand ||
                            detail.mission.state !== "EXECUTING"
                          }
                          onClick={() => act("pause")}
                        >
                          Pause
                        </button>
                        <button
                          disabled={
                            busy ||
                            !canCommand ||
                            detail.mission.state !== "PAUSED"
                          }
                          onClick={() => act("resume")}
                        >
                          Resume
                        </button>
                        <button
                          className="danger"
                          disabled={
                            busy ||
                            !canCommand ||
                            !["EXECUTING", "PAUSED"].includes(
                              detail.mission.state,
                            )
                          }
                          onClick={() => act("cancel")}
                        >
                          Cancel & return
                        </button>
                      </div>
                      <p className="panel-note">
                        Start explicitly starts/reuses Gazebo, waits for
                        MAVLink, uploads, then commands PX4. Simulator startup
                        alone never flies.
                      </p>
                    </Panel>
                  )}
                  {showMap && (
                    <div className="grid mission-grid">
                      <Panel title="Live survey map">
                        <SurveyMap detail={detail} />
                      </Panel>
                      <div className="stack">
                        <Panel title="Vehicle telemetry · PX4 SITL">
                          <dl className="telemetry">
                            {[
                              [
                                "Battery",
                                telemetry?.battery_percent == null
                                  ? "—"
                                  : `${telemetry.battery_percent}%`,
                              ],
                              [
                                "Altitude",
                                telemetry
                                  ? `${telemetry.altitude_m.toFixed(1)} m`
                                  : "—",
                              ],
                              [
                                "Speed",
                                telemetry
                                  ? `${telemetry.speed_m_s.toFixed(1)} m/s`
                                  : "—",
                              ],
                              ["Samples", detail.observations.length],
                            ].map(([k, v]) => (
                              <div key={k}>
                                <dt>{k}</dt>
                                <dd>{v}</dd>
                              </div>
                            ))}
                          </dl>
                          <p className="panel-note">
                            {telemetry
                              ? `Last sample: ${new Date(telemetry.created_at).toLocaleString()}`
                              : "Waiting for telemetry after explicit mission start."}
                          </p>
                        </Panel>
                        <Panel title="Experimental survey coverage">
                          <strong className="coverage-value">
                            {detail.coverage.coverage_percent.toFixed(2)}%
                          </strong>
                          <p className="panel-note">{detail.coverage.notice}</p>
                          <p className="panel-note">
                            {detail.coverage.algorithm_version}
                          </p>
                        </Panel>
                      </div>
                    </div>
                  )}
                  {(home || view === "Live Monitoring") && (
                    <Panel title="Gazebo · live 3D world">
                      <Suspense fallback={<p>Loading 3D viewer…</p>}>
                        <GazeboView
                          token={token}
                          missionId={detail.mission.id}
                          state={detail.mission.state}
                        />
                      </Suspense>
                    </Panel>
                  )}
                  {view === "Sensor Data" && (
                    <Panel title="GPR / metal normalized features · synthetic">
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Time</th>
                              <th>GPR response</th>
                              <th>Metal response</th>
                              <th>Quality</th>
                              <th>Provenance</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.observations
                              .filter((o) => o.sensor)
                              .slice(-100)
                              .map((o) => (
                                <tr key={o.id}>
                                  <td>
                                    {new Date(
                                      o.created_at,
                                    ).toLocaleTimeString()}
                                  </td>
                                  <td>{o.sensor?.gpr_response}</td>
                                  <td>{o.sensor?.metal_response}</td>
                                  <td>{o.sensor?.quality}</td>
                                  <td>{o.sensor?.provenance}</td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    </Panel>
                  )}
                  <>
                    {showDetections && view !== "Classification" && (
                      <DetectionList
                        key={detail.mission.id}
                        targets={detail.detections}
                        selectedId={target?.id}
                        onSelect={setTarget}
                      />
                    )}
                    {view === "Classification" && (
                      <Panel title="Classification register">
                        <p className="panel-note">
                          Compare mock labels with recorded analyst assessments.
                          Select a record to assess it below. Labels are
                          unverified; legacy demo labels are display-only.
                        </p>
                        <div className="table-wrap">
                          <table>
                            <thead>
                              <tr>
                                <th>Target</th>
                                <th>Mock label</th>
                                <th>Score</th>
                                <th>Assessment</th>
                                <th>Action</th>
                              </tr>
                            </thead>
                            <tbody>
                              {detail.detections.map((record, index) => {
                                const reviews = detail.reviews.filter(
                                  (review) => review.detection_id === record.id,
                                );
                                return (
                                  <tr key={record.id}>
                                    <td>
                                      #{String(index + 1).padStart(3, "0")}
                                    </td>
                                    <td>{detectionLabel(record)}</td>
                                    <td>{record.confidence.toFixed(2)}</td>
                                    <td>
                                      {reviews.length
                                        ? reviews
                                            .at(-1)!
                                            .assessment.replaceAll("_", " ")
                                        : "Not assessed"}
                                    </td>
                                    <td>
                                      <button onClick={() => setTarget(record)}>
                                        Assess target #{index + 1}
                                      </button>
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                        {!detail.detections.length && (
                          <Empty>No recorded targets to classify.</Empty>
                        )}
                      </Panel>
                    )}
                    {showDetections && target && (
                      <Panel title="Potential target details">
                        <dl>
                          <dt>Mock classification</dt>
                          <dd>
                            {detectionLabel(target)} · unverified fixture label
                            {usesLegacyMockLabel(target) && (
                              <p>
                                Display-only demo label for a legacy simulated
                                record. Stored classification:{" "}
                                {target.classification ?? "unspecified"}.
                                Recorded score is unchanged.
                              </p>
                            )}
                          </dd>
                          <dt>Detection ID</dt>
                          <dd>{target.id}</dd>
                          <dt>Experimental score</dt>
                          <dd>{target.confidence.toFixed(2)}</dd>
                          <dt>Processing version</dt>
                          <dd>{target.processing_version}</dd>
                          <dt>Source observation</dt>
                          <dd>{target.observation_id}</dd>
                        </dl>
                        <p>
                          Confidence is not verification. Simulated:{" "}
                          {String(target.simulated)}
                        </p>
                        {analyst && (
                          <form onSubmit={assess}>
                            <label>
                              Assessment
                              <select name="assessment">
                                <option value="needs_investigation">
                                  Needs investigation
                                </option>
                                <option value="likely_false_positive">
                                  Likely false positive
                                </option>
                                <option value="inconclusive">
                                  Inconclusive
                                </option>
                              </select>
                            </label>
                            <label>
                              Analyst notes
                              <textarea
                                name="notes"
                                required
                                maxLength={4000}
                              />
                            </label>
                            <button>Record assessment</button>
                          </form>
                        )}
                        {detail.reviews
                          .filter((r) => r.detection_id === target.id)
                          .map((r) => (
                            <article key={r.id}>
                              <strong>
                                {r.assessment.replaceAll("_", " ")}
                              </strong>
                              <p>{r.notes}</p>
                              <small>
                                {new Date(r.created_at).toLocaleString()}
                              </small>
                            </article>
                          ))}
                      </Panel>
                    )}
                  </>
                  {view === "Team Management" && user.role === "supervisor" && (
                    <Panel title="Mission assignment">
                      <form
                        onSubmit={async (event) => {
                          event.preventDefault();
                          const form = new FormData(event.currentTarget);
                          try {
                            await request(
                              `/missions/${selected}/assign`,
                              token,
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  operator_id: form.get("operator"),
                                  field_ids: form.getAll("fields"),
                                }),
                              },
                            );
                            await refreshMissions();
                            setMessage("Assignment saved");
                          } catch (e) {
                            setError((e as Error).message);
                          }
                        }}
                      >
                        <label>
                          Operator
                          <select
                            name="operator"
                            defaultValue={detail.mission.operator_id}
                          >
                            {people
                              .filter((p) => p.role === "mission_operator")
                              .map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.username}
                                </option>
                              ))}
                          </select>
                        </label>
                        <label>
                          Field Personnel
                          <select
                            name="fields"
                            multiple
                            defaultValue={detail.mission.field_ids}
                          >
                            {people
                              .filter((p) => p.role === "field_personnel")
                              .map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.username}
                                </option>
                              ))}
                          </select>
                        </label>
                        <button
                          disabled={
                            !["DRAFT", "READY"].includes(detail.mission.state)
                          }
                        >
                          Save assignment
                        </button>
                      </form>
                    </Panel>
                  )}
                  {(view === "Alerts" ||
                    view === "Audit Logs" ||
                    (home && active.includes(detail.mission.state))) && (
                    <Panel title="Mission events & alerts">
                      {detail.events.map((e) => (
                        <article key={e.id}>
                          <span className="status neutral">
                            {e.kind.replaceAll("_", " ")}
                          </span>
                          <p>{e.detail}</p>
                          <small>
                            {new Date(e.created_at).toLocaleString()}
                          </small>
                        </article>
                      ))}
                      {field && (
                        <form onSubmit={stop}>
                          <label>
                            Reason for stop request
                            <textarea
                              name="reason"
                              minLength={3}
                              maxLength={1000}
                              required
                            />
                          </label>
                          <button
                            className="danger"
                            disabled={
                              !active.includes(detail.mission.state) ||
                              !user.permissions.includes("stop:request")
                            }
                          >
                            Request mission stop
                          </button>
                          <p className="panel-note">
                            Notifies the operator; never directly commands PX4.
                          </p>
                        </form>
                      )}
                    </Panel>
                  )}
                  {showHistory && (
                    <Panel title="Survey history & dates">
                      {!history.length ? (
                        <Empty>No finalized survey attempts yet.</Empty>
                      ) : (
                        history.map((h) => (
                          <article key={h.id}>
                            <strong>
                              {new Date(h.finished_at).toLocaleString()}
                            </strong>
                            <p>
                              {h.status} · {h.coverage_percent}% experimental
                              coverage
                            </p>
                            <small>{h.mission_id}</small>
                          </article>
                        ))
                      )}
                    </Panel>
                  )}
                  {view === "Export Data" &&
                    user.permissions.includes("reports:read") && (
                      <Panel title="Export data preview">
                        <p>
                          {detail.mission.name}: {detail.detections.length}{" "}
                          detections, {detail.observations.length} readings and{" "}
                          {detail.reviews.length} assessments.
                        </p>
                        <p className="panel-note">
                          Preview of stored detection fields included in CSV and
                          JSON. Display-only legacy demo labels are not exported
                          as recorded classifications. JSON also includes
                          readings, assessments, events and coverage.
                        </p>
                        <dl>
                          <dt>Mission ID</dt>
                          <dd>{detail.mission.id}</dd>
                          <dt>Mission status</dt>
                          <dd>{detail.mission.state}</dd>
                          <dt>Experimental coverage</dt>
                          <dd>
                            {detail.coverage.coverage_percent.toFixed(2)}%
                          </dd>
                        </dl>
                        {!detail.detections.length ? (
                          <Empty>
                            No detections recorded for this mission. JSON still
                            contains available mission data.
                          </Empty>
                        ) : (
                          <div className="table-wrap">
                            <table>
                              <thead>
                                <tr>
                                  <th>Detection ID</th>
                                  <th>Stored classification</th>
                                  <th>Score</th>
                                  <th>Latitude</th>
                                  <th>Longitude</th>
                                  <th>Processing version</th>
                                  <th>Simulated</th>
                                </tr>
                              </thead>
                              <tbody>
                                {detail.detections.map((record) => (
                                  <tr key={record.id}>
                                    <td>{record.id}</td>
                                    <td>
                                      {record.classification ?? "Unavailable"}
                                    </td>
                                    <td>{record.confidence}</td>
                                    <td>{record.latitude}</td>
                                    <td>{record.longitude}</td>
                                    <td>{record.processing_version}</td>
                                    <td>{String(record.simulated)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                        <p className="panel-note">
                          Simulation only. Potential detections are unverified.
                          Surveyed does not mean cleared or safe.
                        </p>
                      </Panel>
                    )}
                  {showReports && user.permissions.includes("reports:read") && (
                    <Panel title="Mission reports">
                      <div className="command-row">
                        <button onClick={() => download("json")}>
                          Download JSON report
                        </button>
                        <button onClick={() => download("csv")}>
                          Download CSV report
                        </button>
                        <button onClick={() => window.print()}>
                          Print / save PDF
                        </button>
                      </div>
                      <p className="panel-note">
                        Reports include simulated provenance, source readings,
                        assessments and coverage rules. Surveyed does not mean
                        cleared or safe.
                      </p>
                    </Panel>
                  )}
                </>
              )}
              {field && !detail && view === "Alerts" && (
                <Panel title="Operational alerts">
                  <Empty>Select an assigned mission to view its alerts.</Empty>
                  <button className="danger" disabled>
                    Request mission stop
                  </button>
                </Panel>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
