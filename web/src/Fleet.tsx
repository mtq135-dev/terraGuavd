import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Identity, request } from "./api";
import { Panel } from "./components";
import "./fleet.css";

export type FleetVehicle = {
  id: string;
  name: string;
  type_id: string;
  type_name: string;
  active: boolean;
  in_use: boolean;
  executable: boolean;
  runtime_slot: string | null;
};
type Kind = {
  id: string;
  name: string;
  category: string;
  simulation_profile: string;
  specifications?: Record<string, unknown>;
};
type Detail = {
  id: string;
  name: string;
  created_at: string;
  runtime_slot: string | null;
  type: Kind;
  usage: {
    missions_planned: number;
    missions_started: number;
    missions_completed: number;
    survey_attempts: number;
    last_started_at: string | null;
  };
};
function status(v: FleetVehicle) {
  return v.in_use
    ? { key: "busy", label: "In use" }
    : !v.active
      ? { key: "disabled", label: "Disabled" }
      : v.executable
        ? { key: "available", label: "Available" }
        : { key: "catalog", label: "Catalog only" };
}
function Status({ vehicle }: { vehicle: FleetVehicle }) {
  const s = status(vehicle);
  return (
    <span className={`fleet-status ${s.key}`}>
      <i aria-hidden="true" />
      {s.label}
    </span>
  );
}
function date(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Not recorded";
}
function VehicleInfo({
  vehicle,
  token,
  close,
}: {
  vehicle: FleetVehicle;
  token: string;
  close: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const result = await request<Detail>(
          `/fleet/vehicles/${encodeURIComponent(vehicle.id)}`,
          token,
        );
        if (active) {
          setDetail(result);
          setError("");
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [vehicle.id, token]);
  return (
    <dialog
      ref={dialog}
      className="fleet-dialog"
      aria-labelledby="uav-info-title"
      onCancel={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="fleet-dialog-content">
        <div className="fleet-dialog-heading">
          <div>
            <p className="panel-note">UAV information</p>
            <h2 id="uav-info-title">{vehicle.name}</h2>
          </div>
          <button onClick={close} aria-label="Close UAV information">
            Close ×
          </button>
        </div>
        <Status vehicle={vehicle} />
        {error && <p role="alert">{error}</p>}
        {!detail && !error && <p role="status">Loading UAV information…</p>}
        {detail && (
          <>
            <dl className="fleet-facts">
              <div>
                <dt>UAV ID</dt>
                <dd>{detail.id}</dd>
              </div>
              <div>
                <dt>Type</dt>
                <dd>{detail.type.name}</dd>
              </div>
              <div>
                <dt>Category</dt>
                <dd>{detail.type.category}</dd>
              </div>
              <div>
                <dt>Registered on</dt>
                <dd>{date(detail.created_at)}</dd>
              </div>
              <div>
                <dt>Simulation profile</dt>
                <dd>{detail.type.simulation_profile}</dd>
              </div>
              <div>
                <dt>Simulation channel</dt>
                <dd>{detail.runtime_slot || "No channel assigned"}</dd>
              </div>
            </dl>
            <h3>Recorded usage</h3>
            <dl className="fleet-usage">
              <div>
                <dt>Missions planned</dt>
                <dd>{detail.usage.missions_planned}</dd>
              </div>
              <div>
                <dt>Missions started</dt>
                <dd>{detail.usage.missions_started}</dd>
              </div>
              <div>
                <dt>Missions completed</dt>
                <dd>{detail.usage.missions_completed}</dd>
              </div>
              <div>
                <dt>Survey attempts</dt>
                <dd>{detail.usage.survey_attempts}</dd>
              </div>
            </dl>
            <p>Last mission start: {date(detail.usage.last_started_at)}</p>
            {Object.keys(detail.type.specifications || {}).length > 0 && (
              <>
                <h3>Registered type specifications</h3>
                <dl className="fleet-facts">
                  {Object.entries(detail.type.specifications!).map(
                    ([key, value]) => (
                      <div key={key}>
                        <dt>{key}</dt>
                        <dd>
                          {typeof value === "object"
                            ? JSON.stringify(value)
                            : String(value)}
                        </dd>
                      </div>
                    ),
                  )}
                </dl>
              </>
            )}
            <p className="panel-note">
              Registration date is the date this UAV was added to TerraGuavd.
              Manufacture date, physical age and maintenance history are not
              recorded. Usage reflects stored simulation missions only.
            </p>
          </>
        )}
      </div>
    </dialog>
  );
}
export default function Fleet({
  token,
  user,
}: {
  token: string;
  user: Identity;
}) {
  const [vehicles, setVehicles] = useState<FleetVehicle[]>([]);
  const [types, setTypes] = useState<Kind[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [selectedType, setSelectedType] = useState("");
  const [typeSearch, setTypeSearch] = useState("");
  const [nameSearch, setNameSearch] = useState("");
  const [availability, setAvailability] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const manage = user.permissions.includes("fleet:manage");
  const refresh = useCallback(async () => {
    try {
      const [v, t] = await Promise.all([
        request<FleetVehicle[]>("/fleet/vehicles", token),
        request<Kind[]>("/fleet/types", token),
      ]);
      setVehicles(v);
      setTypes(t);
      setError("");
      setLoaded(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [token]);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);
  async function save(event: FormEvent<HTMLFormElement>, kind: boolean) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setSaving(true);
    setNotice("");
    const body = kind
      ? {
          id: crypto.randomUUID(),
          name: data.get("name"),
          category: data.get("category"),
          simulation_profile: data.get("profile"),
        }
      : {
          id: crypto.randomUUID(),
          name: data.get("name"),
          type_id: data.get("type"),
          runtime_slot: data.get("slot") || null,
        };
    try {
      await request(kind ? "/fleet/types" : "/fleet/vehicles", token, {
        method: "POST",
        body: JSON.stringify(body),
      });
      form.reset();
      await refresh();
      setNotice(kind ? "UAV type registered." : "UAV registered.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  const matchingTypes = types.filter((t) =>
    `${t.name} ${t.category}`
      .toLowerCase()
      .includes(typeSearch.trim().toLowerCase()),
  );
  const filtered = vehicles.filter(
    (v) =>
      (selectedType === "all" || v.type_id === selectedType) &&
      matchingTypes.some((t) => t.id === v.type_id) &&
      `${v.name} ${v.id}`
        .toLowerCase()
        .includes(nameSearch.trim().toLowerCase()) &&
      (availability === "all" || status(v).key === availability),
  );
  const selected = vehicles.find((v) => v.id === selectedId);
  return (
    <Panel title="UAV fleet · simulation only" className="fleet-panel">
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {manage && (
        <div className="fleet-registration">
          <details>
            <summary>Register UAV</summary>
            <form onSubmit={(e) => save(e, false)}>
              <label>
                UAV name
                <input name="name" required maxLength={100} />
              </label>
              <label>
                Type
                <select name="type" required defaultValue="">
                  <option value="" disabled>
                    Select a UAV type
                  </option>
                  {types.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </label>
              <details className="fleet-advanced">
                <summary>Simulation settings</summary>
                <label>
                  Isolated simulation channel
                  <select name="slot">
                    <option value="">Catalog only</option>
                    {["sitl-01", "sitl-02", "sitl-03"]
                      .filter(
                        (slot) =>
                          !vehicles.some((v) => v.runtime_slot === slot),
                      )
                      .map((slot) => (
                        <option key={slot}>{slot}</option>
                      ))}
                  </select>
                </label>
                <p className="panel-note">
                  Only a supported type with an unassigned channel can execute
                  simulations. Registration does not start a flight.
                </p>
              </details>
              <button disabled={saving || !types.length}>Register UAV</button>
            </form>
          </details>
          <details>
            <summary>Register UAV type</summary>
            <form onSubmit={(e) => save(e, true)}>
              <label>
                Type name
                <input name="name" required maxLength={80} />
              </label>
              <label>
                Category
                <select name="category">
                  <option value="quadrotor">Quadrotor</option>
                  <option value="hexacopter">Hexacopter</option>
                  <option value="fixed-wing">Fixed-wing</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <details className="fleet-advanced">
                <summary>Simulation settings</summary>
                <label>
                  Simulation compatibility
                  <select name="profile">
                    <option value="catalog-only">Catalog only</option>
                    <option value="px4-x500">PX4 x500 quadrotor profile</option>
                    <option value="px4-x500-lidar-down">
                      PX4 x500 downward LiDAR profile
                    </option>
                  </select>
                </label>
                <p className="panel-note">
                  x500 profiles require the Quadrotor category. A new type name
                  alone does not add flight compatibility.
                </p>
              </details>
              <button disabled={saving}>Register type</button>
            </form>
          </details>
        </div>
      )}
      <div className="fleet-overview">
        <h3>Browse by type</h3>
        <span>
          {vehicles.length} UAVs · {types.length} types ·{" "}
          {vehicles.filter((v) => status(v).key === "available").length}{" "}
          available
        </span>
      </div>
      <label className="fleet-type-search">
        Search UAV types
        <input
          type="search"
          value={typeSearch}
          onChange={(e) => setTypeSearch(e.target.value)}
          placeholder="Type name or category"
        />
      </label>
      <div className="fleet-types" role="group" aria-label="Select UAV type">
        <button
          className="fleet-type"
          aria-pressed={selectedType === "all"}
          onClick={() => setSelectedType("all")}
        >
          <strong>All UAVs</strong>
          <span>{vehicles.length} registered</span>
        </button>
        {matchingTypes.map((t) => {
          const rows = vehicles.filter((v) => v.type_id === t.id);
          return (
            <button
              className="fleet-type"
              key={t.id}
              aria-pressed={selectedType === t.id}
              onClick={() => setSelectedType(t.id)}
            >
              <strong>{t.name}</strong>
              <span>
                {rows.length} UAVs ·{" "}
                {rows.filter((v) => status(v).key === "available").length}{" "}
                available
              </span>
              <small>{t.category}</small>
            </button>
          );
        })}
      </div>
      {!loaded && !error && <p role="status">Loading fleet…</p>}
      {loaded && !matchingTypes.length && (
        <p className="empty">No UAV types match your search.</p>
      )}
      {!selectedType ? (
        <p className="empty">
          Choose a type to view its UAVs, or select All UAVs.
        </p>
      ) : (
        <>
          <div className="fleet-filters">
            <label>
              Search UAVs
              <input
                type="search"
                value={nameSearch}
                onChange={(e) => setNameSearch(e.target.value)}
                placeholder="UAV name or ID"
              />
            </label>
            <label>
              Availability
              <select
                value={availability}
                onChange={(e) => setAvailability(e.target.value)}
              >
                <option value="all">All statuses</option>
                <option value="available">Available</option>
                <option value="busy">In use</option>
                <option value="disabled">Disabled</option>
                <option value="catalog">Catalog only</option>
              </select>
            </label>
            <button
              onClick={() => {
                setTypeSearch("");
                setNameSearch("");
                setAvailability("all");
              }}
            >
              Clear filters
            </button>
          </div>
          <p className="panel-note" aria-live="polite">
            {filtered.length} matching UAVs
          </p>
          {matchingTypes
            .filter((t) => filtered.some((v) => v.type_id === t.id))
            .map((t) => (
              <section className="fleet-group" key={t.id}>
                <h3>
                  {t.name}{" "}
                  <span>
                    {filtered.filter((v) => v.type_id === t.id).length} UAVs
                  </span>
                </h3>
                <div className="fleet-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>UAV</th>
                        <th>Availability</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered
                        .filter((v) => v.type_id === t.id)
                        .map((v) => (
                          <tr key={v.id}>
                            <td>
                              <strong>{v.name}</strong>
                              <small className="fleet-id">{v.id}</small>
                            </td>
                            <td>
                              <Status vehicle={v} />
                            </td>
                            <td>
                              <div className="fleet-actions">
                                <button
                                  onClick={() => setSelectedId(v.id)}
                                  aria-label={`Info for ${v.name}`}
                                >
                                  Info
                                </button>
                                {manage && (
                                  <button
                                    disabled={v.in_use}
                                    onClick={async () => {
                                      try {
                                        await request(
                                          `/fleet/vehicles/${encodeURIComponent(v.id)}`,
                                          token,
                                          {
                                            method: "PATCH",
                                            body: JSON.stringify({
                                              active: !v.active,
                                            }),
                                          },
                                        );
                                        await refresh();
                                      } catch (e) {
                                        setError((e as Error).message);
                                      }
                                    }}
                                  >
                                    {v.active ? "Disable" : "Enable"}
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ))}
          {!filtered.length && (
            <p className="empty">No UAVs match these filters.</p>
          )}
        </>
      )}
      {selected && (
        <VehicleInfo
          key={selected.id}
          vehicle={selected}
          token={token}
          close={() => setSelectedId(null)}
        />
      )}
    </Panel>
  );
}
