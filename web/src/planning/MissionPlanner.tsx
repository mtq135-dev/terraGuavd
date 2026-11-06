import { useEffect, useMemo, useRef, useState } from "react";
import { request, type Identity } from "../api";
import { Panel } from "../components";
import type { FleetVehicle } from "../Fleet";
import type { Mission } from "../operations-api";
import type { SurveyArea } from "../survey-areas-api";
import { outline, type Shape, type DrawTool, type LatLon } from "./AreaEditor";
import PlanningCanvas from "./PlanningCanvas";
import "./planning.css";
type Draft = {
  id: string;
  parent: string;
  name: string;
  uav: string;
  shape: Shape;
  history: Shape[];
  at: number;
  altitude: number;
  speed: number;
  spacing: number;
  synthetic: boolean;
  fieldIds: string[];
  savedId?: string;
  savedPath?: [number, number][];
};
type Preview = {
  ok: boolean;
  problems: string[];
  path: [number, number][];
  lanes?: number;
  area_m2?: number;
  path_length_m?: number;
  estimated_duration_s?: number;
};
const empty: Shape = { kind: "polygon", points: [] };
const colors = ["#79c9b4", "#b2bce9", "#dfaa75", "#e5a5c5"];
function newDraft(parent = "", n = 1): Draft {
  return {
    id: crypto.randomUUID(),
    parent,
    name: `Sector ${n}`,
    uav: "",
    shape: empty,
    history: [empty],
    at: 0,
    altitude: 5,
    speed: 2,
    spacing: 5,
    synthetic: true,
    fieldIds: [],
  };
}
export default function MissionPlanner({
  token,
  user,
  areas,
  fleet,
  missions,
  people,
  initialAreaId,
  onSaved,
}: {
  token: string;
  user: Identity;
  areas: SurveyArea[];
  fleet: FleetVehicle[];
  missions: Mission[];
  people: { id: string; username: string; role: string }[];
  initialAreaId: string;
  onSaved: (m: Mission) => Promise<void>;
}) {
  const storageKey = `terraguavd:planning:${user.id}`;
  const [drafts, setDrafts] = useState<Draft[]>(() => {
    try {
      const stored = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      if (
        Array.isArray(stored) &&
        stored.length &&
        stored.every(
          (d) =>
            d.id &&
            d.shape &&
            Array.isArray(d.history) &&
            Array.isArray(d.fieldIds),
        )
      )
        return stored;
    } catch {}
    return [newDraft(initialAreaId)];
  });
  const [selected, setSelected] = useState(
    () => sessionStorage.getItem(storageKey + ":selected") || drafts[0].id,
  );
  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey + ":selected", selected);
    } catch {}
  }, [selected, storageKey]);
  const draft = drafts.find((d) => d.id === selected) || drafts[0];
  const [tool, setTool] = useState<DrawTool | null>(null);
  const [drawing, setDrawing] = useState<LatLon[] | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [checkedKey, setCheckedKey] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const checkSeq = useRef(0);
  const area = areas.find(
    (a) => a.id === draft.parent && a.operator_id === user.id,
  );
  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(drafts));
    } catch {
      setMessage(
        "Browser draft storage is unavailable. Keep this page open until your sectors are saved.",
      );
    }
  }, [drafts, storageKey]);
  useEffect(() => {
    if (!initialAreaId) return;
    const found = drafts.find((d) => d.parent === initialAreaId && !d.savedId);
    if (found) {
      setSelected(found.id);
      return;
    }
    const next = newDraft(initialAreaId, drafts.length + 1);
    setDrafts((list) => [...list, next]);
    setSelected(next.id);
  }, [initialAreaId]);
  function update(patch: Partial<Draft>) {
    setDrafts((list) =>
      list.map((d) => (d.id === draft.id ? { ...d, ...patch } : d)),
    );
  }
  function commit(shape: Shape) {
    const list = [...draft.history.slice(0, draft.at + 1), shape].slice(-50);
    update({ shape, history: list, at: list.length - 1 });
  }
  function cancel() {
    setTool(null);
    setDrawing(null);
  }
  function select(id: string) {
    cancel();
    setSelected(id);
    setPreview(null);
    setError("");
    setMessage("");
  }
  function add() {
    const next = newDraft(draft.parent, drafts.length + 1);
    setDrafts((list) => [...list, next]);
    select(next.id);
  }
  function step(by: number) {
    if (tool || draft.savedId) return;
    const at = draft.at + by;
    if (at >= 0 && at < draft.history.length)
      update({ shape: draft.history[at], at });
  }
  const keys = useRef<(e: KeyboardEvent) => void>(() => {});
  keys.current = (e) => {
    const el = e.target as HTMLElement;
    if (
      el?.isContentEditable ||
      ["INPUT", "TEXTAREA", "SELECT"].includes(el?.tagName)
    )
      return;
    const k = e.key.toLowerCase();
    if (e.ctrlKey || e.metaKey) {
      if (k === "z") {
        e.preventDefault();
        step(e.shiftKey ? 1 : -1);
      }
      if (k === "y") {
        e.preventDefault();
        step(1);
      }
    } else if (k === "escape") cancel();
    else if (!draft.savedId) {
      const t = (
        { r: "rect", c: "circle", f: "polygon" } as Record<string, DrawTool>
      )[k];
      if (t) {
        cancel();
        setTool(t);
      }
    }
  };
  useEffect(() => {
    const f = (e: KeyboardEvent) => keys.current(e);
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, []);
  const ring = outline(draft.shape);
  const checkingRing = drawing || ring;
  const checkKey = JSON.stringify([
    draft.id,
    draft.parent,
    draft.uav,
    checkingRing,
    draft.altitude,
    draft.speed,
    draft.spacing,
    draft.savedId,
  ]);
  const boundary = checkingRing.map(([lat, lon]) => [lon, lat]);
  if (boundary.length >= 3) boundary.push(boundary[0]);
  useEffect(() => {
    const seq = ++checkSeq.current;
    setPreview(null);
    setError("");
    if (!area || !draft.uav || boundary.length < 4 || draft.savedId) {
      setChecking(false);
      return;
    }
    setChecking(true);
    const timer = setTimeout(
      () =>
        request<Preview>("/plans/preview", token, {
          method: "POST",
          body: JSON.stringify({
            assignment_id: draft.parent,
            uav_id: draft.uav,
            boundary,
            altitude_m: draft.altitude,
            speed_m_s: draft.speed,
            spacing_m: draft.spacing,
          }),
        })
          .then((p) => {
            if (seq === checkSeq.current) {
              setPreview(p);
              setCheckedKey(checkKey);
              setChecking(false);
            }
          })
          .catch((e) => {
            if (seq === checkSeq.current) {
              setError(e.message);
              setChecking(false);
            }
          }),
      250,
    );
    return () => {
      clearTimeout(timer);
      checkSeq.current++;
    };
  }, [checkKey, token, !!area]);
  const fitTo = useMemo(
    () =>
      area?.boundary.coordinates[0].map(([lon, lat]) => [lat, lon] as LatLon) ||
      [],
    [JSON.stringify(area?.boundary)],
  );
  const otherDrafts = drafts.filter(
    (d) => d.id !== draft.id && d.parent === draft.parent,
  );
  const overlays = [
    {
      id: "parent",
      name: area?.name || "Assigned area",
      uav: "Supervisor boundary",
      points: fitTo,
      color: "#b1a0e9",
    },
    ...missions
      .filter(
        (m) =>
          m.assignment_id === draft.parent &&
          !drafts.some((d) => d.savedId === m.id),
      )
      .map((m) => ({
        id: m.id,
        name: m.name,
        uav: m.uav_id || "",
        points: m.boundary.coordinates[0].map(
          ([lon, lat]) => [lat, lon] as LatLon,
        ),
        color: "#90b7bd",
      })),
    ...otherDrafts.map((d) => ({
      id: d.id,
      name: d.name,
      uav: `${fleet.find((v) => v.id === d.uav)?.name || "No UAV"} · ${d.savedId ? "Saved" : "Draft"}`,
      points: outline(d.shape),
      color: colors[drafts.findIndex((x) => x.id === d.id) % colors.length],
    })),
  ];
  async function save() {
    if (
      !preview?.ok ||
      checkedKey !== checkKey ||
      tool ||
      checking ||
      draft.savedId
    )
      return;
    setBusy(true);
    setError("");
    try {
      const closed = ring.map(([lat, lon]) => [lon, lat]);
      closed.push(closed[0]);
      const mission = await request<Mission>("/missions", token, {
        method: "POST",
        body: JSON.stringify({
          name: draft.name.trim(),
          assignment_id: draft.parent,
          area_id: draft.parent,
          uav_id: draft.uav,
          boundary: closed,
          waypoints: preview.path,
          altitude_m: draft.altitude,
          speed_m_s: draft.speed,
          synthetic_sensors: draft.synthetic,
          field_ids: draft.fieldIds,
        }),
      });
      update({ savedId: mission.id, savedPath: preview.path });
      setMessage(
        "Draft mission saved. Add another sector, or validate and start it in Mission workspace. Nothing flies on save.",
      );
      await onSaved(mission);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel title="Plan a mission" className="reference-planner">
      <div className="planner-sectors">
        <div>
          <strong>Survey sectors</strong>
          <small>Drafts stay visible when you add another sector.</small>
        </div>
        {drafts.map((d, i) => (
          <button
            key={d.id}
            aria-pressed={d.id === draft.id}
            disabled={!!tool || busy}
            onClick={() => select(d.id)}
          >
            <i style={{ background: colors[i % colors.length] }} />
            {d.name}
            <small>{d.savedId ? "Saved" : "Draft"}</small>
          </button>
        ))}
        {draft.savedId && (
          <button
            disabled={busy}
            onClick={() => {
              const next = {
                ...draft,
                id: crypto.randomUUID(),
                name: draft.name + " retry",
                savedId: undefined,
                savedPath: undefined,
                history: [draft.shape],
                at: 0,
              };
              setDrafts((list) => [...list, next]);
              select(next.id);
            }}
          >
            Copy sector to new draft
          </button>
        )}
        <button onClick={add} disabled={!!tool || busy}>
          + Add sector
        </button>
      </div>
      <div className="reference-planner-layout">
        <div className="planner-map-pane">
          <div
            className="planner-draw-bar"
            role="toolbar"
            aria-label="Draw the survey area"
          >
            {(
              [
                ["rect", "Rectangle", "R"],
                ["circle", "Circle", "C"],
                ["polygon", "Free shape", "F"],
              ] as const
            ).map(([t, label, key]) => (
              <button
                key={t}
                disabled={!!draft.savedId || !area}
                aria-pressed={tool === t}
                onClick={() => {
                  cancel();
                  setTool(tool === t ? null : t);
                }}
              >
                {label} <kbd>{key}</kbd>
              </button>
            ))}
            <button
              disabled={!!draft.savedId || !!tool || draft.at === 0}
              onClick={() => step(-1)}
            >
              Undo
            </button>
            <button
              disabled={
                !!draft.savedId ||
                !!tool ||
                draft.at === draft.history.length - 1
              }
              onClick={() => step(1)}
            >
              Redo
            </button>
          </div>
          <PlanningCanvas
            editable={!draft.savedId}
            shape={draft.shape}
            tool={tool}
            color={error || (preview && !preview.ok) ? "#ef9c9c" : "#79c9b4"}
            path={(draft.savedId
              ? draft.savedPath ||
                missions.find((m) => m.id === draft.savedId)?.waypoints ||
                []
              : preview?.path || []
            ).map(([lon, lat]) => [lat, lon])}
            fitTo={fitTo}
            overlays={overlays}
            onChange={(s) => update({ shape: s })}
            onCommit={commit}
            onDone={(s) => {
              commit(s);
              cancel();
            }}
            onDraft={setDrawing}
            onCancel={cancel}
          />
          <div className="planner-hint" role="status">
            {draft.savedId
              ? "Saved sector. Add a new sector to plan another UAV."
              : tool === "rect"
                ? "Click two opposite corners."
                : tool === "circle"
                  ? "Click the centre, then a point on the edge."
                  : tool === "polygon"
                    ? "Click each corner; click the first corner or double-click to finish. Backspace removes the last corner."
                    : "Choose a drawing tool, or drag a corner, side dot or centre handle to edit the outline."}
            {tool && <button onClick={cancel}>Cancel · Esc</button>}
          </div>
          <p className="panel-note">
            Purple: Supervisor assignment · Other colored outlines: retained
            sectors · Gold: planned survey lanes. Saving or drawing does not
            start a flight.
          </p>
        </div>
        <aside className="planner-side">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              save();
            }}
          >
            <fieldset disabled={!!draft.savedId || busy}>
              <label>
                Assigned survey area
                <select
                  required
                  value={draft.parent}
                  onChange={(e) => {
                    cancel();
                    update({ parent: e.target.value });
                  }}
                >
                  <option value="">Select a Supervisor-assigned area</option>
                  {areas
                    .filter((a) => a.operator_id === user.id)
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                UAV for this sector
                <select
                  required
                  value={draft.uav}
                  onChange={(e) => update({ uav: e.target.value })}
                >
                  <option value="">Select UAV</option>
                  {fleet
                    .filter((v) => v.executable)
                    .map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} / {v.type_name}
                        {v.in_use ? " · In use" : " · Available"}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Mission name
                <input
                  value={draft.name}
                  required
                  maxLength={100}
                  onChange={(e) => update({ name: e.target.value })}
                />
              </label>
              <div className="planner-check" aria-live="polite">
                {checking ? (
                  "Checking outline…"
                ) : error ? (
                  error
                ) : draft.savedId ? (
                  "Mission saved"
                ) : !area ? (
                  "Choose your assigned survey area first."
                ) : !draft.uav ? (
                  "Choose a UAV to preview the plan."
                ) : !ring.length && !drawing ? (
                  "Draw a survey sector on the map."
                ) : preview?.ok ? (
                  <>
                    <strong>✓ Ready to save</strong>
                    <span>
                      {Math.round(preview.area_m2 || 0)} m² · {preview.lanes}{" "}
                      lanes · {Math.round(preview.path_length_m || 0)} m
                    </span>
                    <small>
                      Estimated route time:{" "}
                      {Math.ceil((preview.estimated_duration_s || 0) / 60)} min,
                      excluding takeoff and return.
                    </small>
                  </>
                ) : (
                  preview?.problems.join(" ") ||
                  "Finish the outline to check it."
                )}
              </div>
              <div className="planner-settings">
                <label>
                  Altitude (m)
                  <input
                    type="number"
                    min={2}
                    max={8}
                    step={0.5}
                    value={draft.altitude}
                    onChange={(e) =>
                      update({ altitude: Number(e.target.value) })
                    }
                  />
                </label>
                <label>
                  Speed (m/s)
                  <input
                    type="number"
                    min={0.5}
                    max={3}
                    step={0.5}
                    value={draft.speed}
                    onChange={(e) => update({ speed: Number(e.target.value) })}
                  />
                </label>
                <label>
                  Lane spacing (m)
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={draft.spacing}
                    onChange={(e) =>
                      update({ spacing: Number(e.target.value) })
                    }
                  />
                </label>
              </div>
              <details>
                <summary>Simulation and field assignment</summary>
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={draft.synthetic}
                    onChange={(e) => update({ synthetic: e.target.checked })}
                  />
                  Use mock GPR/metal sensor data and synthetic detections
                </label>
                <label>
                  Assigned Field Personnel
                  <select
                    multiple
                    value={draft.fieldIds}
                    onChange={(e) =>
                      update({
                        fieldIds: [...e.target.selectedOptions].map(
                          (o) => o.value,
                        ),
                      })
                    }
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
              </details>
            </fieldset>
            {message && <p role="status">{message}</p>}
            {!draft.savedId && (
              <button
                className="primary"
                disabled={
                  busy ||
                  checking ||
                  checkedKey !== checkKey ||
                  !!tool ||
                  !preview?.ok ||
                  !area ||
                  !draft.name.trim()
                }
              >
                {busy ? "Saving…" : "Save draft mission"}
              </button>
            )}
            <p className="panel-note">
              Plans must stay inside the assigned area. Routes are limited to
              the isolated simulator home at execution. Planning boundaries are
              not an autopilot geofence; separate simulators do not validate
              collision avoidance. Lane spacing is a planning setting, not proof
              of completed coverage.
            </p>
          </form>
        </aside>
      </div>
    </Panel>
  );
}
