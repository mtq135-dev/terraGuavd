import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import SurveyAreas from "./SurveyAreas";
import { SurveyArea } from "./survey-areas-api";

const ring: [number, number][] = [
  [8.545, 47.397],
  [8.546, 47.397],
  [8.546, 47.398],
  [8.545, 47.397],
];
vi.mock("./PlanMap", () => ({
  default: ({
    onBoundary,
  }: {
    onBoundary: (p: [number, number][]) => void;
  }) => (
    <button type="button" onClick={() => onBoundary(ring)}>
      Draw test assignment polygon
    </button>
  ),
}));
vi.mock("./AreaProgressMap", () => ({
  default: () => <div>Geographic completed / live / remaining layers</div>,
}));
const area: SurveyArea = {
  id: "area-1",
  name: "North sector",
  description: "Survey by smaller missions",
  operator_id: "operator",
  operator_username: "operator",
  created_by: "supervisor",
  boundary: { type: "Polygon", coordinates: [ring] },
  deadline: null,
  revision: 1,
  created_at: "2026-10-25T10:00:00Z",
  updated_at: "2026-10-25T10:00:00Z",
  status: "ASSIGNED",
  overdue: false,
  progress: {
    completed_geometry: { type: "GeometryCollection", geometries: [] },
    in_progress_geometry: { type: "GeometryCollection", geometries: [] },
    remaining_geometry: { type: "Polygon", coordinates: [ring] },
    total_m2: 1000,
    completed_m2: 250,
    in_progress_m2: 100,
    remaining_m2: 650,
    coverage_percent: 25,
    fully_surveyed: false,
    simulated: true,
    algorithm_version: "experimental-test",
    notice: "Surveyed does not mean cleared or safe.",
  },
};
let fetcher: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetcher = vi.fn(async (url: string) => ({
    ok: true,
    json: async () =>
      url.includes("/mission-users")
        ? [{ id: "operator", username: "operator", role: "mission_operator" }]
        : { ...area, missions: [], surveys: [], history: [] },
  }));
  vi.stubGlobal("fetch", fetcher);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("lets a Supervisor draw and submit a named area with an operator", async () => {
  const refresh = vi.fn(async () => {});
  render(
    <SurveyAreas
      token="session"
      user={{
        id: "supervisor",
        username: "supervisor",
        role: "supervisor",
        permissions: ["survey_areas:manage"],
      }}
      areas={[]}
      onRefresh={refresh}
      onPlan={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "New area assignment" }));
  fireEvent.change(screen.getByLabelText("Assignment name"), {
    target: { value: "North sector" },
  });
  fireEvent.change(screen.getByLabelText("Description"), {
    target: { value: "Survey by smaller missions" },
  });
  await screen.findByRole("option", { name: "operator" });
  fireEvent.change(screen.getByLabelText("Assigned Mission Operator"), {
    target: { value: "operator" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Draw test assignment polygon" }),
  );
  fireEvent.submit(
    screen.getByRole("button", { name: "Assign survey area" }).closest("form")!,
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/survey-areas",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "North sector",
          description: "Survey by smaller missions",
          operator_id: "operator",
          boundary: ring,
          deadline: null,
        }),
      }),
    ),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "No flight command was issued",
  );
  expect(refresh).toHaveBeenCalled();
});

it("gives an Operator area progress and sub-mission planning without edit controls", async () => {
  const plan = vi.fn();
  render(
    <SurveyAreas
      token="session"
      user={{
        id: "operator",
        username: "operator",
        role: "mission_operator",
        permissions: ["survey_areas:read"],
      }}
      areas={[area]}
      onRefresh={vi.fn(async () => {})}
      onPlan={plan}
    />,
  );
  expect(
    screen.queryByRole("button", { name: "New area assignment" }),
  ).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: "Plan sub-mission in North sector" }),
  );
  expect(plan).toHaveBeenCalledWith(area);
  fireEvent.click(
    screen.getByRole("button", { name: /North sector ASSIGNED/ }),
  );
  expect(
    await screen.findByText("Geographic completed / live / remaining layers"),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Edit / reassign area" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("25.00%")).toBeInTheDocument();
});
