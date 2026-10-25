import { useEffect, useState } from "react";
import { Identity, request } from "./api";
import { Panel } from "./components";

export default function AccountAccess({
  token,
  actorId,
}: {
  token: string;
  actorId: string;
}) {
  const [accounts, setAccounts] = useState<Identity[]>([]);
  const [roles, setRoles] = useState<Record<string, string[]>>({});
  const [selected, setSelected] = useState<Identity>();
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    let alive = true;
    setError("");
    Promise.all([
      request<Identity[]>(`/admin/users?offset=${offset}`, token),
      request<Record<string, string[]>>("/admin/roles", token),
    ])
      .then(([users, catalog]) => {
        if (alive) {
          setAccounts(users);
          setRoles(catalog);
          setSelected(undefined);
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [token, offset]);
  async function save() {
    if (!selected) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await request<Identity>(
        `/admin/users/${selected.id}/access`,
        token,
        {
          method: "PUT",
          body: JSON.stringify({
            role: selected.role,
            active: selected.active ?? true,
            denied_permissions: selected.denied_permissions ?? [],
          }),
        },
      );
      setAccounts((items) =>
        items.map((item) => (item.id === updated.id ? updated : item)),
      );
      setSelected(updated);
      setMessage(
        `Access saved for ${updated.username}. Their sessions were revoked; sign-in is required.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel title="Account roles & access">
      <p className="panel-note">
        Select an account, choose its role, and restrict individual permissions.
        Only permissions belonging to that role can be enabled. Changes revoke
        the account's sessions.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Username</th>
              <th>Role</th>
              <th>Status</th>
              <th>Access</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((account) => (
              <tr key={account.id}>
                <td>{account.username}</td>
                <td>{account.role.replaceAll("_", " ")}</td>
                <td>{account.active === false ? "Disabled" : "Enabled"}</td>
                <td>
                  <button
                    disabled={busy || account.id === actorId}
                    onClick={() => {
                      setSelected({ ...account });
                      setMessage("");
                    }}
                  >
                    Edit access for {account.username}
                  </button>
                  {account.id === actorId && <small> Current account</small>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="command-row">
        <button
          disabled={busy || offset === 0}
          onClick={() => setOffset(offset - 50)}
        >
          Previous accounts
        </button>
        <button
          disabled={busy || accounts.length < 50}
          onClick={() => setOffset(offset + 50)}
        >
          Next accounts
        </button>
      </div>
      {selected && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <h3>Access for {selected.username}</h3>
          <label>
            Account role
            <select
              disabled={busy}
              value={selected.role}
              onChange={(e) =>
                setSelected({
                  ...selected,
                  role: e.target.value,
                  denied_permissions: [],
                })
              }
            >
              {Object.keys(roles).map((role) => (
                <option key={role} value={role}>
                  {role.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          <label>
            <input
              type="checkbox"
              disabled={busy}
              checked={selected.active ?? true}
              onChange={(e) =>
                setSelected({ ...selected, active: e.target.checked })
              }
            />
            Account enabled
          </label>
          <fieldset disabled={busy}>
            <legend>Enabled permissions</legend>
            {(roles[selected.role] ?? []).map((permission) => (
              <label key={permission}>
                <input
                  type="checkbox"
                  checked={!selected.denied_permissions?.includes(permission)}
                  disabled={
                    selected.role === "administrator" &&
                    permission === "users:read"
                  }
                  onChange={(e) =>
                    setSelected({
                      ...selected,
                      denied_permissions: e.target.checked
                        ? (selected.denied_permissions ?? []).filter(
                            (p) => p !== permission,
                          )
                        : [...(selected.denied_permissions ?? []), permission],
                    })
                  }
                />
                {permission}
              </label>
            ))}
          </fieldset>
          <p className="panel-note">
            Your own access must be changed by another administrator. Active
            mission operators cannot be changed during a flight.
          </p>
          <button disabled={busy}>
            {busy ? "Saving access…" : "Save access"}
          </button>
        </form>
      )}
    </Panel>
  );
}
