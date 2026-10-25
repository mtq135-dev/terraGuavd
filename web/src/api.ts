export type Identity = {
  id: string;
  username: string;
  role: string;
  permissions: string[];
  active?: boolean;
  denied_permissions?: string[];
};
export type Dashboard = {
  mode: string;
  missions: unknown[];
  potential_detections: unknown[];
  survey_attempts: unknown[];
  alerts: unknown[];
  telemetry: Record<string, unknown> | null;
  simulation: string;
  detection_engine: string;
  notice: string;
};
export async function request<T>(
  path: string,
  token?: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : Array.isArray(payload?.detail)
          ? payload.detail.map((item: { msg: string }) => item.msg).join("; ")
          : null;
    throw new Error(
      detail ??
        (response.status === 401
          ? "Session expired or invalid credentials. Sign in again."
          : response.status === 403
            ? "You do not have permission to access this workspace."
            : "Service unavailable. Check the backend and retry."),
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
