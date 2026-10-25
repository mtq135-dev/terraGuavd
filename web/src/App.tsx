import { FormEvent, useEffect, useState } from "react";
import { Dashboard, Identity, request } from "./api";
import { Empty, Metric, Panel } from "./components";

import AccountAccess from "./AccountAccess";
import PrototypeWorkspace from "./PrototypeWorkspace";

const workspaces: Record<
  string,
  { title: string; subtitle: string; nav: string[] }
> = {
  administrator: {
    title: "Administration",
    subtitle: "Manage access, system configuration and platform health.",
    nav: [
      "Dashboard",
      "User Management",
      "Roles & Permissions",
      "UAV Management",
      "System Monitoring",
      "Audit Logs",
    ],
  },
  mission_operator: {
    title: "Mission control",
    subtitle: "Plan and monitor assigned survey missions.",
    nav: [
      "Dashboard",
      "Mission Planning",
      "Survey Areas",
      "Live Monitoring",
      "Mission History",
      "Map View",
      "Alerts",
      "Reports",
    ],
  },
  detection_analyst: {
    title: "Detection analysis",
    subtitle: "Review sensor measurements and assess potential targets.",
    nav: [
      "Dashboard",
      "Detection Review",
      "Sensor Data",
      "Map & Results",
      "Classification",
      "Reports",
      "Export Data",
    ],
  },
  supervisor: {
    title: "Operational overview",
    subtitle: "Oversee operations, assignments and mission outcomes.",
    nav: [
      "Dashboard",
      "Missions Overview",
      "Survey Areas",
      "Team Management",
      "UAV Fleet",
      "Reports",
      "Approvals",
      "Alerts",
      "Audit Logs",
    ],
  },
  field_personnel: {
    title: "Field monitoring",
    subtitle: "Assigned missions, potential detections and alerts.",
    nav: ["Home", "Missions", "Detections", "Alerts", "More"],
  },
};
const icons = ["⌂", "▤", "◉", "◇", "▦", "◷", "△", "≡"];

export default function App() {
  const [token, setToken] = useState<string>();
  const [user, setUser] = useState<Identity>();
  const [data, setData] = useState<Dashboard>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState("Dashboard");
  const [users, setUsers] = useState<Identity[]>();
  const [status, setStatus] = useState("Not checked");
  const [runtimeLabel, setRuntimeLabel] = useState("Not checked");
  const [auditRecords, setAuditRecords] =
    useState<
      { id: string; action: string; actor: string | null; created_at: string }[]
    >();
  const [search, setSearch] = useState("");
  useEffect(() => {
    if (!token || !user) return;
    let alive = true;
    const timer = setInterval(
      () =>
        request<Dashboard>(`/dashboards/${user.role}`, token)
          .then((value) => {
            if (alive) setData(value);
          })
          .catch((e) => {
            if (alive) setError(e.message);
          }),
      5000,
    );
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [token, user]);
  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const auth = await request<{ access_token: string }>(
        "/auth/login",
        undefined,
        {
          method: "POST",
          body: JSON.stringify({
            username: form.get("username"),
            password: form.get("password"),
          }),
        },
      );
      const identity = await request<Identity>("/auth/me", auth.access_token);
      const dashboard = await request<Dashboard>(
        `/dashboards/${identity.role}`,
        auth.access_token,
      );
      setToken(auth.access_token);
      setUser(identity);
      setData(dashboard);
      setView(identity.role === "field_personnel" ? "Home" : "Dashboard");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function signOut() {
    try {
      await request("/auth/logout", token, { method: "POST" });
    } catch {
      setError(
        "Local session cleared. Server session expires within 30 minutes.",
      );
    }
    setToken(undefined);
    setUser(undefined);
    setData(undefined);
    setUsers(undefined);
    setAuditRecords(undefined);
    setRuntimeLabel("Not checked");
    setStatus("Not checked");
    setSearch("");
  }
  async function refresh() {
    setBusy(true);
    setError("");
    try {
      if (user)
        setData(await request<Dashboard>(`/dashboards/${user.role}`, token));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function loadUsers() {
    setBusy(true);
    try {
      setUsers(await request<Identity[]>("/admin/users", token));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function checkHealth() {
    setStatus("Checking…");
    try {
      const [, simulation] = await Promise.all([
        request("/health/ready", token),
        request<{ ready: boolean; running: boolean; notice?: string }>(
          "/simulation/status",
          token,
        ),
      ]);
      setStatus("Database and PostGIS ready");
      setRuntimeLabel(
        simulation.notice
          ? "Service unavailable"
          : simulation.ready
            ? "MAVLink ready"
            : simulation.running
              ? "Starting simulator"
              : "Service ready · simulator stopped",
      );
    } catch (err) {
      setStatus((err as Error).message);
    }
  }
  const workspace = user && workspaces[user.role];
  const field = user?.role === "field_personnel";
  const home = view === "Dashboard" || view === "Home";
  const show = (...views: string[]) => home || views.includes(view);
  return (
    <div className={`app ${field ? "field-app" : ""}`}>
      <header>
        <a className="brand" href="/">
          <img
            className="brand-mark"
            src="/brand/terraguavd-mark-final.png"
            alt=""
          />
          TerraGuavd
        </a>
        <span className="badge">SIMULATION ONLY</span>
        {user ? (
          <div className="account">
            <span className="avatar">
              {user.username.slice(0, 1).toUpperCase()}
            </span>
            <span>{user.username}</span>
            <button className="subtle" onClick={signOut}>
              Sign out
            </button>
          </div>
        ) : (
          <span className="muted">Survey operations platform</span>
        )}
      </header>
      <div className="safety">
        Potential detections are unverified. Surveyed does not mean cleared or
        safe.
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!user ? (
        <main className="login">
          <p className="eyebrow">AUTHORIZED ACCESS</p>
          <h1>Sign in to TerraGuavd</h1>
          <p className="muted">
            Your workspace for responsible survey operations.
          </p>
          <form onSubmit={signIn}>
            <label>
              Username
              <input
                name="username"
                autoComplete="username"
                required
                maxLength={80}
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                maxLength={256}
              />
            </label>
            <button className="primary" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>
          <p className="muted">
            Use an account provisioned by your administrator.
          </p>
        </main>
      ) : (
        <div className="layout">
          <aside>
            <p className="eyebrow">{field ? "FIELD PERSONNEL" : "WORKSPACE"}</p>
            <nav aria-label="Workspace navigation">
              {workspace!.nav.map((label, index) => (
                <button
                  key={label}
                  className={view === label ? "nav-active" : ""}
                  aria-current={view === label ? "page" : undefined}
                  onClick={() => {
                    setView(label);
                    setSearch("");
                  }}
                >
                  <span aria-hidden>{icons[index % icons.length]}</span>
                  {label}
                </button>
              ))}
            </nav>
            <div className="sidebar-foot">
              <span className="status neutral">Prototype v0.2</span>
              <p>Isolated PX4 / Gazebo runtime</p>
            </div>
          </aside>
          <main>
            <div className="page-heading">
              <div>
                <p className="eyebrow">
                  {field ? "FIELD PERSONNEL" : "OPERATIONS WORKSPACE"}
                </p>
                <h1>{home ? workspace!.title : view}</h1>
                <p className="muted">{workspace!.subtitle}</p>
              </div>
              <button disabled={busy} onClick={refresh}>
                {busy ? "Refreshing…" : "↻ Refresh"}
              </button>
            </div>
            {!home && (
              <div className="view-banner">
                {view} · Simulation-only workspace
              </div>
            )}
            {home && (
              <div className="metrics">
                <Metric
                  title={field ? "Assigned missions" : "Recorded missions"}
                  value={data?.missions.length ?? "—"}
                  icon="◇"
                />
                <Metric
                  title="Potential detections"
                  value={data?.potential_detections.length ?? "—"}
                  icon="◎"
                  tone="red"
                />
                <Metric
                  title="Survey attempts"
                  value={data?.survey_attempts.length ?? "—"}
                  icon="▦"
                  tone="cream"
                />
                {!field && (
                  <Metric
                    title="Simulation runtime"
                    value={data?.simulation ?? "Unknown"}
                    icon="◌"
                    tone="green"
                  />
                )}
              </div>
            )}
            {user.role === "administrator" && (
              <>
                {show("System Monitoring") && (
                  <div className="grid two">
                    <Panel
                      title="Service health"
                      action={
                        <button onClick={checkHealth}>Check services</button>
                      }
                    >
                      <ul className="service-list">
                        <li>
                          <span>Backend API</span>
                          <span className="status green">Connected</span>
                        </li>
                        <li>
                          <span>PostgreSQL / PostGIS</span>
                          <span role="status">{status}</span>
                        </li>
                        <li>
                          <span>PX4 / Gazebo</span>
                          <span className="status neutral">{runtimeLabel}</span>
                        </li>
                        <li>
                          <span>Detection engine</span>
                          <span className="status neutral">
                            Experimental synthetic baseline
                          </span>
                        </li>
                      </ul>
                    </Panel>
                    <Panel title="Security & audit">
                      <p className="muted">
                        Authentication, mission commands, assignments and
                        analyst actions are recorded in append-only audit
                        records.
                      </p>
                      <button onClick={() => setView("Audit Logs")}>
                        Review audit logs
                      </button>
                    </Panel>
                  </div>
                )}
                {home && (
                  <Panel
                    title="User directory"
                    action={
                      <button disabled={busy} onClick={loadUsers}>
                        Load accounts
                      </button>
                    }
                  >
                    <label className="search-label">
                      Search accounts
                      <input
                        placeholder="Search by username…"
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                      />
                    </label>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Username</th>
                            <th>Role</th>
                            <th>Access policy</th>
                          </tr>
                        </thead>
                        <tbody>
                          {users
                            ?.filter((item) =>
                              item.username
                                .toLowerCase()
                                .includes(search.toLowerCase()),
                            )
                            .map((item) => (
                              <tr key={item.id}>
                                <td>{item.username}</td>
                                <td>{item.role.replaceAll("_", " ")}</td>
                                <td>{item.permissions.length} permissions</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                    {!users && (
                      <Empty>Load provisioned accounts from the backend.</Empty>
                    )}
                    {users &&
                      users.filter((item) =>
                        item.username
                          .toLowerCase()
                          .includes(search.toLowerCase()),
                      ).length === 0 && <Empty>No matching accounts.</Empty>}
                  </Panel>
                )}
                {["User Management", "Roles & Permissions"].includes(view) &&
                  token && <AccountAccess token={token} actorId={user.id} />}
                {view === "UAV Management" && (
                  <Panel title="Configured simulated vehicle">
                    <strong>sitl-01 · PX4 x500 / Gazebo</strong>
                    <p className="muted">
                      One isolated simulator is configured. Physical aircraft
                      registration is outside this prototype.
                    </p>
                    <button onClick={checkHealth}>Check services</button>
                    <p role="status">{runtimeLabel}</p>
                  </Panel>
                )}
                {view === "Audit Logs" && (
                  <Panel title="Audit logs">
                    <button
                      onClick={async () => {
                        try {
                          setAuditRecords(await request("/admin/audit", token));
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      Load recent audit records
                    </button>
                    {!auditRecords ? (
                      <Empty>Load the latest 100 audited events.</Empty>
                    ) : (
                      auditRecords.map((record) => (
                        <article key={record.id}>
                          <strong>{record.action.replaceAll("_", " ")}</strong>
                          <p>{record.actor ?? "Unauthenticated"}</p>
                          <small>
                            {new Date(record.created_at).toLocaleString()}
                          </small>
                        </article>
                      ))
                    )}
                  </Panel>
                )}
              </>
            )}
            {user.role !== "administrator" && token && (
              <PrototypeWorkspace
                token={token}
                user={user}
                data={data}
                view={view}
                onViewChange={setView}
              />
            )}
            <p className="workspace-foot">{data?.notice}</p>
          </main>
        </div>
      )}
      <footer>
        TerraGuavd · Simulation-only survey prototype · Potential targets are
        unverified
      </footer>
    </div>
  );
}
