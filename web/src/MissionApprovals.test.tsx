import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ApprovalInbox } from "./MissionApprovals";
import type { ApprovalListItem } from "./operations-api";

vi.mock("./PlanMap", () => ({
  default: () => <div>Submitted boundary map</div>,
}));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("requires a reason to reject a submitted request and records the decision without starting a mission", async () => {
  const boundary: GeoJSON.Polygon = {
    type: "Polygon",
    coordinates: [
      [
        [0, 0],
        [1, 0],
        [1, 1],
        [0, 0],
      ],
    ],
  };
  const row: ApprovalListItem = {
    current: true,
    status: "Pending",
    mission: { id: "mission", name: "Adjacent sector" },
    operator_username: "operator",
    request: {
      id: "request",
      status: "Pending",
      requested_at: "2026-11-02T12:00:00Z",
      reason: "Survey adjacent boundary",
      decision_reason: null,
      decided_at: null,
      snapshot: {
        assignment: {
          id: "area",
          name: "Assigned sector",
          boundary,
          revision: 1,
          supervisor_username: "supervisor",
        },
        configuration: {
          id: "mission",
          name: "Adjacent sector",
          boundary,
          waypoints: [
            [0, 0],
            [1, 0],
          ],
          altitude_m: 5,
          speed_m_s: 2,
          synthetic_sensors: true,
        },
        outside_geometry: boundary,
        outside_m2: 50,
      },
    },
  };
  const send = vi.fn(async (_path: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      row.status = "Rejected";
      row.request = {
        ...row.request,
        status: "Rejected",
        decision_reason: "Adjacent sector unavailable",
      };
      return { ok: true, json: async () => ({ request: row.request }) };
    }
    return { ok: true, json: async () => [structuredClone(row)] };
  });
  vi.stubGlobal("fetch", send);
  render(<ApprovalInbox token="session" supervisor />);
  const reject = await screen.findByRole("button", { name: "Reject" });
  fireEvent.click(reject);
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Enter a rejection reason",
  );
  expect(
    send.mock.calls.filter(([, options]) => options?.method === "POST"),
  ).toHaveLength(0);
  fireEvent.change(screen.getByLabelText(/Decision reason/), {
    target: { value: "Adjacent sector unavailable" },
  });
  fireEvent.click(reject);
  expect(
    await screen.findByText("Request rejected. No mission was started."),
  ).toBeVisible();
  const mutations = send.mock.calls.filter(
    ([, options]) => options?.method === "POST",
  );
  expect(mutations).toHaveLength(1);
  expect(mutations[0][0]).toBe("/api/v1/mission-approvals/request/decision");
  expect(JSON.parse(String(mutations[0][1]?.body))).toEqual({
    decision: "Rejected",
    reason: "Adjacent sector unavailable",
  });
});
