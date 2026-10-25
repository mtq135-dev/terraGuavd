import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import AccountAccess from "./AccountAccess";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("edits role permission restrictions and saves backend access state", async () => {
  const account = {
    id: "analyst",
    username: "analyst",
    role: "detection_analyst",
    active: true,
    permissions: ["detections:review"],
    denied_permissions: [],
  };
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => ({
    ok: true,
    status: 200,
    json: async () =>
      url.endsWith("/roles")
        ? { detection_analyst: ["detections:review"] }
        : init?.method === "PUT"
          ? {
              ...account,
              denied_permissions: ["detections:review"],
              permissions: [],
            }
          : [account],
  }));
  vi.stubGlobal("fetch", fetcher);
  render(<AccountAccess token="session" actorId="admin" />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Edit access for analyst" }),
  );
  fireEvent.click(screen.getByRole("checkbox", { name: "detections:review" }));
  fireEvent.click(screen.getByRole("button", { name: "Save access" }));
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/admin/users/analyst/access",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          role: "detection_analyst",
          active: true,
          denied_permissions: ["detections:review"],
        }),
      }),
    ),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "sessions were revoked",
  );
});
