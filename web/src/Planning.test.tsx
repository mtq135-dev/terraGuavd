import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import MissionPlanner from "./planning/MissionPlanner";
import type { SurveyArea } from "./survey-areas-api";
import type { Shape } from "./planning/AreaEditor";
vi.mock("./planning/PlanningCanvas", () => ({
  default: (p: {
    tool: string | null;
    shape: Shape;
    overlays: { name: string; points: number[][] }[];
    onDone: (s: Shape) => void;
  }) => (
    <div>
      <span>
        Other drawn sectors:{" "}
        {
          p.overlays.filter(
            (o) => o.points.length >= 3 && o.name !== "Large area",
          ).length
        }
      </span>
      <span>Current shape: {p.shape.kind}</span>
      {p.tool && (
        <button
          type="button"
          onClick={() =>
            p.onDone(
              p.tool === "circle"
                ? { kind: "circle", centre: [47.3977, 8.5455], radiusM: 5 }
                : {
                    kind: "polygon",
                    points: [
                      [47.3976, 8.5453],
                      [47.3976, 8.5459],
                      [47.39794, 8.5459],
                      [47.39794, 8.5453],
                    ],
                  },
            )
          }
        >
          Finish drawing
        </button>
      )}
    </div>
  ),
}));
const user = {
  id: "op",
  username: "op",
  role: "mission_operator" as const,
  permissions: ["missions:plan"],
};
const props = {
  token: "test",
  user,
  areas: [
    {
      id: "parent",
      name: "Large area",
      operator_id: "op",
      boundary: {
        type: "Polygon",
        coordinates: [
          [
            [8.54, 47.39],
            [8.55, 47.39],
            [8.55, 47.4],
            [8.54, 47.39],
          ],
        ],
      },
    },
  ] as SurveyArea[],
  fleet: [
    {
      id: "uav1",
      name: "First UAV",
      type_id: "quad",
      type_name: "x500",
      active: true,
      in_use: false,
      executable: true,
      runtime_slot: "sitl-01",
    },
    {
      id: "uav2",
      name: "Second UAV",
      type_id: "quad",
      type_name: "x500",
      active: true,
      in_use: false,
      executable: true,
      runtime_slot: "sitl-02",
    },
  ],
  missions: [],
  people: [],
  initialAreaId: "",
  onSaved: vi.fn(async () => {}),
};
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});
function backend() {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => ({
    ok: true,
    status: 200,
    json: async () =>
      url.endsWith("/plans/preview")
        ? {
            ok: true,
            problems: [],
            path: [
              [8.5454, 47.3977],
              [8.5458, 47.3978],
            ],
            lanes: 2,
            area_m2: 900,
            path_length_m: 80,
            estimated_duration_s: 40,
          }
        : { id: "saved-mission" },
  }));
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
async function draw(tool = "Rectangle") {
  fireEvent.change(screen.getByLabelText("Assigned survey area"), {
    target: { value: "parent" },
  });
  fireEvent.change(screen.getByLabelText("UAV for this sector"), {
    target: { value: "uav1" },
  });
  fireEvent.click(screen.getByRole("button", { name: new RegExp(tool) }));
  fireEvent.click(screen.getByRole("button", { name: "Finish drawing" }));
  await screen.findByText("✓ Ready to save");
}
it("retains an unsaved sector when adding another and restores it on selection", async () => {
  backend();
  render(<MissionPlanner {...props} />);
  await draw();
  fireEvent.click(screen.getByRole("button", { name: "+ Add sector" }));
  expect(screen.getByText("Other drawn sectors: 1")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Sector 1/ }));
  await screen.findByText("✓ Ready to save");
  expect(screen.getByLabelText("UAV for this sector")).toHaveValue("uav1");
});
it("saves the checked route and UAV without clearing the outline or starting flight", async () => {
  const fetcher = backend();
  render(<MissionPlanner {...props} />);
  await draw();
  fireEvent.click(screen.getByRole("button", { name: "Save draft mission" }));
  await screen.findByText(/Draft mission saved/);
  const saved = fetcher.mock.calls.find(([url]) => url.endsWith("/missions"))!;
  const body = JSON.parse(saved[1]!.body as string);
  expect(body).toMatchObject({
    uav_id: "uav1",
    assignment_id: "parent",
    area_id: "parent",
    synthetic_sensors: true,
    waypoints: [
      [8.5454, 47.3977],
      [8.5458, 47.3978],
    ],
  });
  expect(body.boundary[0]).toEqual(body.boundary.at(-1));
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/start"))).toBe(
    false,
  );
  expect(screen.getByLabelText("Mission name")).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Copy sector to new draft" }),
  );
  expect(screen.getByLabelText("Mission name")).toHaveValue("Sector 1 retry");
  expect(screen.getByLabelText("UAV for this sector")).toHaveValue("uav1");
  expect(screen.getByText("Other drawn sectors: 1")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "+ Add sector" }));
  expect(screen.getByText("Other drawn sectors: 2")).toBeInTheDocument();
});
it("supports circle drawing, undo/redo, and session restoration", async () => {
  backend();
  const view = render(<MissionPlanner {...props} />);
  await draw("Circle");
  expect(screen.getByText("Current shape: circle")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  expect(screen.getByText("Current shape: polygon")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Redo" }));
  expect(screen.getByText("Current shape: circle")).toBeInTheDocument();
  view.unmount();
  render(<MissionPlanner {...props} />);
  expect(screen.getByText("Current shape: circle")).toBeInTheDocument();
  expect(screen.getByLabelText("UAV for this sector")).toHaveValue("uav1");
});
it("rejects invalid previews and never enables save", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        ok: false,
        problems: ["Split the concave sector"],
        path: [],
      }),
    })),
  );
  render(<MissionPlanner {...props} />);
  fireEvent.change(screen.getByLabelText("Assigned survey area"), {
    target: { value: "parent" },
  });
  fireEvent.change(screen.getByLabelText("UAV for this sector"), {
    target: { value: "uav1" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Free shape/ }));
  fireEvent.click(screen.getByRole("button", { name: "Finish drawing" }));
  await screen.findByText("Split the concave sector");
  expect(
    screen.getByRole("button", { name: "Save draft mission" }),
  ).toBeDisabled();
});
