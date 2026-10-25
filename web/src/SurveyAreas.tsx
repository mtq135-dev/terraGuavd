import { FormEvent, useEffect, useState } from "react";
import { Identity, request } from "./api";
import { Empty, Metric, Panel } from "./components";
import PlanMap from "./PlanMap";
import AreaProgressMap from "./AreaProgressMap";
import { SurveyArea, SurveyAreaDetail, parsePoints } from "./survey-areas-api";

function localDeadline(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

function AreaForm({
  area,
  operators,
  busy,
  onSave,
  onClose,
}: {
  area: SurveyArea | null;
  operators: { id: string; username: string }[];
  busy: boolean;
  onSave: (body: unknown) => void;
  onClose: () => void;
}) {
  const [boundary, setBoundary] = useState(
    JSON.stringify(area?.boundary.coordinates[0] ?? []),
  );
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSave({
      name: form.get("name"),
      description: form.get("description"),
      operator_id: form.get("operator"),
      boundary: parsePoints(boundary),
      deadline: form.get("deadline")
        ? new Date(String(form.get("deadline"))).toISOString()
        : null,
      ...(area ? { revision: area.revision } : {}),
    });
  }
  return (
    <Panel
      title={
        area ? "Edit survey area assignment" : "Create survey area assignment"
      }
    >
      <form onSubmit={submit}>
        <div className="grid two">
          <label>
            Assignment name
            <input
              name="name"
              maxLength={100}
              required
              defaultValue={area?.name ?? ""}
            />
          </label>
          <label>
            Assigned Mission Operator
            <select
              name="operator"
              required
              defaultValue={area?.operator_id ?? ""}
            >
              <option value="" disabled>
                Select operator
              </option>
              {operators.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.username}
                </option>
              ))}
            </select>
          </label>
          <label>
            Description
            <textarea
              name="description"
              maxLength={4000}
              defaultValue={area?.description ?? ""}
            />
          </label>
          <label>
            Deadline (optional, local time)
            <input
              name="deadline"
              type="datetime-local"
              defaultValue={localDeadline(area?.deadline ?? null)}
            />
          </label>
        </div>
        <PlanMap
          boundary={parsePoints(boundary)}
          waypoints={[]}
          onBoundary={(value) => setBoundary(JSON.stringify(value))}
          onWaypoints={() => {}}
          boundaryOnly
        />
        <label>
          Assignment boundary · closed [longitude, latitude] ring
          <textarea
            value={boundary}
            onChange={(event) => setBoundary(event.target.value)}
            required
          />
        </label>
        <p className="panel-note">
          Valid areas: 10 m²–100 km². Child missions keep their existing size,
          route and simulator-home limits. Reassignment transfers unflown drafts
          and requires revalidation. Active flights block edits. Boundary edits
          must retain all linked mission polygons.
        </p>
        <div className="command-row">
          <button disabled={busy} className="primary">
            {area ? "Save assignment changes" : "Assign survey area"}
          </button>
          <button type="button" disabled={busy} onClick={onClose}>
            Cancel editing
          </button>
        </div>
      </form>
    </Panel>
  );
}

export default function SurveyAreas({
  token,
  user,
  areas,
  onRefresh,
  onPlan,
  onLoadMore,
  hasMore = false,
}: {
  token: string;
  user: Identity;
  areas: SurveyArea[];
  onRefresh: () => Promise<void>;
  onPlan: (area: SurveyArea) => void;
  onLoadMore?: () => void;
  hasMore?: boolean;
}) {
  const supervisor = user.role === "supervisor";
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<SurveyAreaDetail>();
  const [editor, setEditor] = useState<SurveyArea | null | undefined>();
  const [operators, setOperators] = useState<
    { id: string; username: string; role: string }[]
  >([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    if (!supervisor) return;
    request<typeof operators>("/mission-users", token)
      .then((people) =>
        setOperators(people.filter((p) => p.role === "mission_operator")),
      )
      .catch((error) => setError(error.message));
  }, [token, supervisor]);
  useEffect(() => {
    setDetail(undefined);
    if (!selected) return;
    let alive = true;
    const refresh = () =>
      request<SurveyAreaDetail>(
        `/survey-areas/${selected}?offset=${offset}&limit=20`,
        token,
      )
        .then((data) => {
          if (alive) setDetail(data);
        })
        .catch((error) => {
          if (alive) {
            setError(error.message);
            setDetail(undefined);
          }
        });
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, [selected, offset, token]);
  async function save(body: unknown) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const saved = await request<SurveyArea>(
        editor ? `/survey-areas/${editor.id}` : "/survey-areas",
        token,
        { method: editor ? "PUT" : "POST", body: JSON.stringify(body) },
      );
      setEditor(undefined);
      setSelected(saved.id);
      setOffset(0);
      setDetail(
        await request<SurveyAreaDetail>(
          `/survey-areas/${saved.id}?limit=20`,
          token,
        ),
      );
      await onRefresh();
      setMessage("Assignment saved. No flight command was issued.");
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Survey area assignments">
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <Panel
        title={
          supervisor ? "Survey area assignments" : "Your assigned survey areas"
        }
        action={
          <div className="command-row">
            <button onClick={onRefresh}>Refresh areas</button>
            {supervisor && (
              <button
                onClick={() => {
                  setEditor(null);
                  setError("");
                }}
                className="primary"
              >
                New area assignment
              </button>
            )}
          </div>
        }
      >
        {!areas.length && (
          <Empty>
            {supervisor
              ? "Draw a large area and assign a Mission Operator to begin."
              : "No survey areas assigned. A Supervisor must assign an area before you create new missions."}
          </Empty>
        )}
        <div className="assignment-cards">
          {areas.map((area) => (
            <article key={area.id} className="assignment-card">
              <button
                className="assignment-select"
                onClick={() => {
                  setSelected(area.id);
                  setOffset(0);
                  setError("");
                }}
              >
                <strong>{area.name}</strong>
                <span className="status neutral">
                  {area.status.replaceAll("_", " ")}
                </span>
                <span>
                  {area.operator_username} ·{" "}
                  {area.progress.coverage_percent.toFixed(2)}% completed
                  experimental coverage
                </span>
                <progress
                  max={100}
                  value={area.progress.coverage_percent}
                  aria-label={`${area.name} completed coverage`}
                />
                <small>
                  Created {new Date(area.created_at).toLocaleString()}
                  {area.deadline
                    ? ` · Deadline ${new Date(area.deadline).toLocaleString()}`
                    : " · No deadline"}
                  {area.overdue ? " · Overdue" : ""}
                </small>
              </button>
              {!supervisor && area.status !== "COMPLETED" && (
                <button onClick={() => onPlan(area)}>
                  Plan sub-mission in {area.name}
                </button>
              )}
            </article>
          ))}
        </div>
        {hasMore && (
          <button onClick={onLoadMore}>Load more area assignments</button>
        )}
        <p className="panel-note">
          Showing {areas.length} assignments. Progress uses the union of
          clipped, completed valid sensor footprints; overlapping surveys count
          once. Live footprints do not count as completed. All current sensor
          coverage is experimental and synthetic.
        </p>
      </Panel>
      {editor !== undefined && (
        <AreaForm
          key={editor?.id + ":" + editor?.revision}
          area={editor}
          operators={operators}
          busy={busy}
          onSave={save}
          onClose={() => setEditor(undefined)}
        />
      )}
      {detail && (
        <>
          <Panel
            title={detail.name}
            action={
              supervisor ? (
                <button
                  onClick={() => {
                    setEditor(detail);
                    setError("");
                  }}
                >
                  Edit / reassign area
                </button>
              ) : undefined
            }
          >
            <p>{detail.description || "No description provided."}</p>
            <p>
              {detail.status.replaceAll("_", " ")} · Assigned to{" "}
              {detail.operator_username} · Revision {detail.revision} · Created{" "}
              {new Date(detail.created_at).toLocaleString()}
            </p>
            <p>
              Deadline:{" "}
              {detail.deadline
                ? new Date(detail.deadline).toLocaleString()
                : "None"}
              {detail.overdue ? " · Overdue" : ""}
            </p>
            <div className="grid two">
              <Metric
                title={`Completed (${detail.progress.completed_m2.toFixed(1)} m²)`}
                value={`${detail.progress.coverage_percent.toFixed(2)}%`}
                icon="✓"
              />
              <Metric
                title="In-progress footprints"
                value={`${detail.progress.in_progress_m2.toFixed(1)} m²`}
                icon="◷"
              />
              <Metric
                title="Remaining ground"
                value={`${detail.progress.remaining_m2.toFixed(1)} m²`}
                icon="▧"
              />
              <Metric
                title="Assigned area"
                value={`${detail.progress.total_m2.toFixed(1)} m²`}
                icon="◇"
              />
            </div>
            <AreaProgressMap area={detail} missions={detail.missions} />
            <p className="panel-note">
              {detail.progress.notice} Completion requires the entire polygon to
              be covered by successful completed attempts using the current
              validated fixture profile. Cancelled/failed attempts remain in
              history and do not count toward completed area.
            </p>
          </Panel>
          <Panel title="Sub-missions and survey history">
            {detail.missions.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Mission</th>
                      <th>State</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.missions.map((m) => (
                      <tr key={m.id}>
                        <td>{m.name}</td>
                        <td>{m.state}</td>
                        <td>{new Date(m.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>No linked missions on this page.</Empty>
            )}
            <ul>
              {detail.surveys.map((s) => (
                <li key={s.id}>
                  {new Date(s.finished_at).toLocaleString()} · {s.status} ·{" "}
                  {s.coverage_percent.toFixed(2)}% of sub-mission ·{" "}
                  {s.algorithm_version}
                </li>
              ))}
            </ul>
            <p className="panel-note">
              Each attempt is retained. Mission completion alone never completes
              the assignment.
            </p>
            <div className="command-row">
              <button
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - 20))}
              >
                Previous history
              </button>
              <button
                disabled={
                  Math.max(
                    detail.missions.length,
                    detail.surveys.length,
                    detail.history.length,
                  ) < 20
                }
                onClick={() => setOffset(offset + 20)}
              >
                Next history
              </button>
            </div>
          </Panel>
          <Panel title="Assignment change history">
            <ul>
              {detail.history.map((event) => (
                <li key={event.id}>
                  {new Date(event.created_at).toLocaleString()} · {event.kind} ·
                  Revision {event.snapshot.revision} · Operator{" "}
                  {event.snapshot.operator_id} · {event.snapshot.name}
                </li>
              ))}
            </ul>
          </Panel>
        </>
      )}
    </section>
  );
}
