import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { request } from "./api";
import { Empty, Panel } from "./components";
import type {
  ApprovalListItem,
  ApprovalPreview,
  ApprovalRequest,
  MissionApproval,
} from "./operations-api";
import PlanMap from "./PlanMap";

type Point = [number, number];
const outsideWarning =
  "This mission is outside your assigned survey area and requires supervisor approval.";

export function useApprovalPreview(
  token: string,
  assignmentId: string | undefined,
  boundary: Point[],
  revision: number | undefined,
) {
  const first = boundary[0];
  const last = boundary.at(-1);
  const payload =
    assignmentId &&
    boundary.length >= 4 &&
    last &&
    first[0] === last[0] &&
    first[1] === last[1]
      ? JSON.stringify({ assignment_id: assignmentId, boundary })
      : "";
  const key = `${revision}:${payload}`;
  const [result, setResult] = useState<{
    key: string;
    preview?: ApprovalPreview;
    error?: string;
  }>();
  useEffect(() => {
    if (!payload) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const preview = await request<ApprovalPreview>(
          "/mission-approval-preview",
          token,
          {
            method: "POST",
            body: payload,
            signal: controller.signal,
          },
        );
        if (!controller.signal.aborted) setResult({ key, preview });
      } catch (e) {
        if (!controller.signal.aborted)
          setResult({ key, error: (e as Error).message });
      }
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [key, payload, token]);
  return result?.key === key ? result : undefined;
}

function outsideArea(area: number) {
  return `${area.toLocaleString(undefined, { maximumFractionDigits: 2 })} m² outside the assignment`;
}

export function ApprovalPreviewNotice({
  preview,
}: {
  preview: ApprovalPreview;
}) {
  return preview.required ? (
    <p className="approval-notice" role="status">
      {outsideWarning} {outsideArea(preview.outside_m2)}. You can save it as a
      draft.
    </p>
  ) : (
    <p className="panel-note" role="status">
      The mission boundary is inside the selected assignment.
    </p>
  );
}

export function MissionApprovalPanel({
  token,
  missionId,
  approval,
  canRequest,
  onUpdated,
}: {
  token: string;
  missionId: string;
  approval: MissionApproval;
  canRequest: boolean;
  onUpdated: (approval: MissionApproval) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const reason = String(new FormData(form).get("reason")).trim();
    if (reason.length < 3) {
      setError("Enter a justification of at least three characters.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      onUpdated(
        await request<MissionApproval>(
          `/missions/${missionId}/approval-requests`,
          token,
          {
            method: "POST",
            body: JSON.stringify({ reason }),
          },
        ),
      );
      form.reset();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Boundary approval">
      <p role="status">
        <strong>{approval.status ?? "Approval required"}</strong>
      </p>
      {approval.required && (
        <>
          <p className="panel-note">
            {outsideArea(approval.outside_m2)} · Supervisor:{" "}
            {approval.assignment?.supervisor_username ?? "Unavailable"}
          </p>
          {approval.can_execute ? (
            <p>
              Validate the approved plan before explicitly starting the
              simulated mission.
            </p>
          ) : (
            <p className="approval-notice">
              {approval.warning ?? outsideWarning}
            </p>
          )}
          {approval.request?.decision_reason && (
            <p>Decision reason: {approval.request.decision_reason}</p>
          )}
          {error && (
            <p role="alert" className="approval-notice">
              {error}
            </p>
          )}
          {canRequest &&
            !["Pending", "Approved"].includes(approval.status ?? "") && (
              <form onSubmit={submit}>
                <label>
                  Approval justification
                  <textarea
                    name="reason"
                    required
                    minLength={3}
                    maxLength={2000}
                  />
                </label>
                <button
                  type="submit"
                  className="primary-inline"
                  disabled={busy}
                >
                  Request Approval
                </button>
              </form>
            )}
        </>
      )}
    </Panel>
  );
}

function SubmittedBoundary({
  snapshot,
}: {
  snapshot: ApprovalRequest["snapshot"];
}) {
  return (
    <PlanMap
      readOnly
      boundary={snapshot.configuration.boundary.coordinates[0].map(([x, y]) => [
        x,
        y,
      ])}
      waypoints={snapshot.configuration.waypoints}
      assignedBoundary={snapshot.assignment.boundary}
      outsideGeometry={snapshot.outside_geometry}
    />
  );
}

export function ApprovalInbox({
  token,
  supervisor,
}: {
  token: string;
  supervisor: boolean;
}) {
  const [items, setItems] = useState<ApprovalListItem[]>();
  const [selected, setSelected] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [limit, setLimit] = useState(50);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const item =
    items?.find((row) => row.request.id === selected) ??
    items?.find((row) => row.status === "Pending") ??
    items?.[0];

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const rows = await request<ApprovalListItem[]>(
          `/mission-approvals?limit=${limit}`,
          token,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) {
          if (!Array.isArray(rows))
            throw new Error("Mission approval response is unavailable.");
          setItems(rows);
          setError("");
        }
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      }
    }
    void load();
    const timer = setInterval(load, 5000);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, [token, refresh, limit]);

  async function decide(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!item) return;
    const button = (event.nativeEvent as SubmitEvent)
      .submitter as HTMLButtonElement | null;
    const decision = button?.value;
    if (decision !== "Approved" && decision !== "Rejected") return;
    const reason = String(
      new FormData(event.currentTarget).get("reason"),
    ).trim();
    if (decision === "Rejected" && reason.length < 3) {
      setError("Enter a rejection reason of at least three characters.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await request<MissionApproval>(
        `/mission-approvals/${item.request.id}/decision`,
        token,
        {
          method: "POST",
          body: JSON.stringify({ decision, reason }),
        },
      );
      setItems((rows) =>
        rows?.map((row) =>
          row.request.id === item.request.id
            ? {
                ...row,
                status: decision,
                request: result.request ?? row.request,
              }
            : row,
        ),
      );
      setNotice(`Request ${decision.toLowerCase()}. No mission was started.`);
      setRefresh((value) => value + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title={supervisor ? "Mission Approval Requests" : "Approval updates"}
      action={
        <button onClick={() => setRefresh((value) => value + 1)}>
          Refresh approvals
        </button>
      }
    >
      {error && (
        <p role="alert" className="approval-notice">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {!items && !error && <Empty>Loading mission approvals…</Empty>}
      {items?.length === 0 && <Empty>No mission approval requests.</Empty>}
      {items && items.length > 0 && (
        <label>
          Approval request
          <select
            value={item?.request.id ?? ""}
            onChange={(event) => {
              setSelected(event.target.value);
              setNotice("");
              setError("");
            }}
          >
            {items.map((row) => (
              <option key={row.request.id} value={row.request.id}>
                {row.mission.name} · {row.status} ·{" "}
                {new Date(row.request.requested_at).toLocaleString()}
              </option>
            ))}
          </select>
        </label>
      )}
      {items?.length === limit && limit < 100 && (
        <button onClick={() => setLimit(100)}>Show older requests</button>
      )}
      {item && (
        <>
          <p>
            <strong>{item.mission.name}</strong> · {item.status}
          </p>
          <p className="panel-note">
            Mission {item.mission.id} · {item.operator_username ?? "Operator"} ·{" "}
            {item.request.snapshot.assignment.name}
          </p>
          <p className="panel-note">
            Requested {new Date(item.request.requested_at).toLocaleString()} ·{" "}
            {outsideArea(item.request.snapshot.outside_m2)}
          </p>
          <p>Justification: {item.request.reason}</p>
          {item.request.decision_reason && (
            <p>Decision reason: {item.request.decision_reason}</p>
          )}
          {supervisor && <SubmittedBoundary snapshot={item.request.snapshot} />}
          {supervisor && item.status === "Pending" && item.current && (
            <form key={item.request.id} onSubmit={decide}>
              <label>
                Decision reason (required to reject)
                <textarea name="reason" maxLength={2000} />
              </label>
              <div className="command-row">
                <button
                  type="submit"
                  value="Approved"
                  className="primary-inline"
                  disabled={busy}
                >
                  Approve
                </button>
                <button
                  type="submit"
                  value="Rejected"
                  className="danger"
                  disabled={busy}
                >
                  Reject
                </button>
              </div>
            </form>
          )}
        </>
      )}
    </Panel>
  );
}
