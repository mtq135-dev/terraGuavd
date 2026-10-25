import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import PrototypeWorkspace from "./PrototypeWorkspace";
import { Mission, MissionDetail } from "./operations-api";

vi.mock("./SurveyMap", () => ({
  default: () => <div>Recorded survey map</div>,
}));
vi.mock("./PlanMap", () => ({
  default: () => <div>Interactive plan map</div>,
}));
vi.mock("./GazeboView", () => ({
  default: () => <div>Read-only Gazebo viewer</div>,
}));
const mission: Mission = {
  id: "mission-1",
  name: "Test SITL survey",
  area_id: "area-a",
  operator_id: "operator",
  field_ids: ["field"],
  boundary: {
    type: "Polygon",
    coordinates: [
      [
        [8.5, 47.3],
        [8.6, 47.3],
        [8.6, 47.4],
        [8.5, 47.3],
      ],
    ],
  },
  waypoints: [
    [8.5, 47.3],
    [8.6, 47.3],
  ],
  altitude_m: 5,
  speed_m_s: 2,
  state: "DRAFT",
  synthetic_sensors: true,
  created_at: "2026-10-17T10:00:00Z",
};
let detail: MissionDetail;
let fetcher: ReturnType<typeof vi.fn>;
beforeEach(() => {
  detail = {
    mission: { ...mission },
    observations: [],
    detections: [],
    reviews: [],
    events: [],
    coverage: {
      geometry: { type: "GeometryCollection", geometries: [] },
      coverage_percent: 0,
      algorithm_version: "experimental/1",
      simulated: true,
      notice: "Synthetic experimental coverage",
    },
    notice: "Surveyed does not mean cleared or safe.",
  };
  vi.stubGlobal(
    "WebSocket",
    class {
      send = vi.fn();
      close = vi.fn();
    },
  );
  fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/validate")) detail.mission.state = "READY";
    if (url.endsWith("/start")) detail.mission.state = "STARTING_SIMULATION";
    if (url.endsWith("/stop-request"))
      return {
        ok: true,
        json: async () => ({
          notice: "Operator notified. No autopilot command was sent.",
        }),
      };
    if (url.endsWith("/reviews")) {
      detail.reviews.push({
        id: "review-1",
        detection_id: "target-1",
        assessment: "needs_investigation",
        notes: JSON.parse(String(options?.body)).notes,
        created_at: "2026-10-17T10:01:00Z",
      });
    }
    return {
      ok: true,
      json: async () =>
        url.includes("/areas/")
          ? []
          : url.endsWith("/missions")
            ? [detail.mission]
            : structuredClone(detail),
    };
  });
  vi.stubGlobal("fetch", fetcher);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("selects clearly labelled mock sensor data for new web drafts", () => {
  show("mission_operator", "operator", "Mission Planning");
  expect(
    screen.getByRole("checkbox", {
      name: "Use mock GPR/metal sensor data and synthetic detections",
    }),
  ).toBeChecked();
});
function show(role: string, id: string, view = "Dashboard") {
  render(
    <PrototypeWorkspace
      token="session"
      user={{
        id,
        username: id,
        role,
        permissions:
          role === "mission_operator"
            ? [
                "missions:plan",
                "missions:execute",
                "missions:read",
                "reports:read",
              ]
            : role === "field_personnel"
              ? ["missions:assigned:read", "stop:request"]
              : ["missions:read", "detections:review", "reports:read"],
      }}
      data={{
        missions: [detail.mission],
        potential_detections: [],
        survey_attempts: [],
        alerts: [],
        telemetry: null,
        mode: "simulation-only",
        simulation: "px4-gazebo",
        detection_engine: "experimental",
        notice: "",
      }}
      view={view}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /Test SITL survey/ }));
}
it("requires successful validation before enabling explicit start", async () => {
  show("mission_operator", "operator");
  expect(
    await screen.findByRole("button", { name: "Start simulated mission" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Validate plan" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Start simulated mission" }),
    ).toBeEnabled(),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Start simulated mission" }),
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/missions/mission-1/start",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer session" }),
      }),
    ),
  );
});
it("sends a field stop request without exposing flight controls", async () => {
  detail.mission.state = "EXECUTING";
  show("field_personnel", "field", "Alerts");
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Request mission stop" }),
    ).toBeEnabled(),
  );
  expect(
    screen.queryByRole("button", { name: "Start simulated mission" }),
  ).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Reason for stop request"), {
    target: { value: "Field safety exercise" },
  });
  fireEvent.submit(
    screen
      .getByRole("button", { name: "Request mission stop" })
      .closest("form")!,
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "No autopilot command was sent",
  );
  expect(fetcher).toHaveBeenCalledWith(
    "/api/v1/missions/mission-1/stop-request",
    expect.objectContaining({
      body: JSON.stringify({ reason: "Field safety exercise" }),
    }),
  );
});
it("records analyst notes with an assessment that does not verify a mine", async () => {
  detail.detections = [
    {
      id: "target-1",
      mission_id: "mission-1",
      observation_id: "observation-1",
      longitude: 8.5,
      latitude: 47.3,
      confidence: 0.84,
      processing_version: "experimental/1",
      simulated: true,
    },
  ];
  show("detection_analyst", "analyst", "Detection Review");
  fireEvent.click(await screen.findByRole("button", { name: /Score 0.84/ }));
  fireEvent.change(screen.getByLabelText("Analyst notes"), {
    target: { value: "Synthetic score requires independent investigation" },
  });
  fireEvent.submit(
    screen.getByRole("button", { name: "Record assessment" }).closest("form")!,
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "does not verify a landmine",
  );
  expect(fetcher).toHaveBeenCalledWith(
    "/api/v1/detections/target-1/reviews",
    expect.objectContaining({ method: "POST" }),
  );
});
it("gives classification a register rather than the review cards or flight workspace", async () => {
  show("detection_analyst", "analyst", "Classification");
  expect(
    await screen.findByRole("heading", { name: "Classification register" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("columnheader", { name: "Assessment" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: /Potential detections/ }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Live survey map" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Mission reports" }),
  ).not.toBeInTheDocument();
});
it("keeps report downloads on the reports page without unrelated target review", async () => {
  show("mission_operator", "operator", "Reports");
  expect(
    await screen.findByRole("button", { name: "Download CSV report" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Start simulated mission" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: /Potential detections/ }),
  ).not.toBeInTheDocument();
});

it("shows persisted detections in analyst export preview with download controls", async () => {
  detail.detections = [
    {
      id: "export-target",
      mission_id: "mission-1",
      observation_id: "observation-1",
      latitude: 47.3,
      longitude: 8.5,
      confidence: 0.84,
      classification: "potential_target",
      processing_version: "experimental/1",
      simulated: true,
    },
  ];
  show("detection_analyst", "analyst", "Export Data");
  expect(
    await screen.findByRole("heading", { name: "Export data preview" }),
  ).toBeInTheDocument();
  expect(screen.getByText("export-target")).toBeInTheDocument();
  expect(screen.getByText("potential_target")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Download CSV report" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Record assessment" }),
  ).not.toBeInTheDocument();
});
