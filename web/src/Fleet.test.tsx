import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeAll, expect, it, vi } from "vitest";
import Fleet from "./Fleet";
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
});
const vehicles = [
  {
    id: "sitl-01",
    name: "First UAV",
    type_id: "quad",
    type_name: "Quadrotor",
    active: true,
    in_use: true,
    executable: true,
    runtime_slot: "sitl-01",
  },
  {
    id: "sitl-02",
    name: "Second UAV",
    type_id: "quad",
    type_name: "Quadrotor",
    active: true,
    in_use: false,
    executable: true,
    runtime_slot: "sitl-02",
  },
];
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function backend() {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => ({
    ok: true,
    status: 200,
    json: async () =>
      options?.method
        ? {}
        : url.endsWith("/vehicles/sitl-02")
          ? {
              id: "sitl-02",
              name: "Second UAV",
              created_at: "2026-11-06T10:00:00Z",
              runtime_slot: "sitl-02",
              type: {
                name: "Quadrotor",
                category: "quadrotor",
                simulation_profile: "px4-x500",
              },
              usage: {
                missions_planned: 4,
                missions_started: 3,
                missions_completed: 2,
                survey_attempts: 3,
                last_started_at: null,
              },
            }
          : url.endsWith("/types")
            ? [
                {
                  id: "quad",
                  name: "Quadrotor",
                  category: "quadrotor",
                  simulation_profile: "px4-x500",
                },
              ]
            : vehicles,
  }));
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
it("shows distinct vehicles and prevents disabling a reserved vehicle", async () => {
  const fetcher = backend();
  render(
    <Fleet
      token="test"
      user={{
        id: "admin",
        username: "admin",
        role: "administrator",
        permissions: ["fleet:read", "fleet:manage"],
      }}
    />,
  );
  fireEvent.click(await screen.findByRole("button", { name: /All UAVs/ }));
  expect(
    await screen.findByRole("cell", { name: /First UAV/ }),
  ).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: /Second UAV/ })).toBeInTheDocument();
  const buttons = screen.getAllByRole("button", { name: "Disable" });
  expect(buttons[0]).toBeDisabled();
  expect(buttons[1]).toBeEnabled();
  fireEvent.click(buttons[1]);
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/fleet/vehicles/sitl-02",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ active: false }),
      }),
    ),
  );
});
it("allows a supervisor to inspect the fleet without catalog mutation controls", async () => {
  backend();
  render(
    <Fleet
      token="test"
      user={{
        id: "sup",
        username: "sup",
        role: "supervisor",
        permissions: ["fleet:read"],
      }}
    />,
  );
  fireEvent.click(await screen.findByRole("button", { name: /All UAVs/ }));
  expect(
    await screen.findByRole("cell", { name: /First UAV/ }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Disable" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Register UAV" }),
  ).not.toBeInTheDocument();
});

const admin = {
  id: "admin",
  username: "admin",
  role: "administrator" as const,
  permissions: ["fleet:read", "fleet:manage"],
};
it("starts at the type hierarchy and combines name and availability filters", async () => {
  backend();
  render(<Fleet token="test" user={admin} />);
  await screen.findByRole("button", { name: /Quadrotor/ });
  expect(
    screen.queryByRole("cell", { name: /First UAV/ }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Quadrotor/ }));
  fireEvent.change(screen.getByLabelText("Search UAVs"), {
    target: { value: "Second" },
  });
  expect(
    screen.queryByRole("cell", { name: /First UAV/ }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("cell", { name: /Second UAV/ })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Availability"), {
    target: { value: "busy" },
  });
  expect(screen.getByText("No UAVs match these filters.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getAllByRole("button", { name: /^Info for/ })).toHaveLength(2);
  fireEvent.change(screen.getByLabelText("Search UAV types"), {
    target: { value: "no-such-type" },
  });
  expect(
    screen.getByText("No UAV types match your search."),
  ).toBeInTheDocument();
});
it("keeps registration sections independent and collapsed by default", async () => {
  backend();
  const { container } = render(<Fleet token="test" user={admin} />);
  await screen.findByRole("button", { name: /Quadrotor/ });
  const sections = container.querySelectorAll(".fleet-registration > details");
  expect(sections).toHaveLength(2);
  expect(sections[0]).not.toHaveAttribute("open");
  expect(sections[1]).not.toHaveAttribute("open");
  fireEvent.click(sections[0].querySelector("summary")!);
  expect(sections[0]).toHaveAttribute("open");
  expect(sections[1]).not.toHaveAttribute("open");
});
it("opens real recorded details and closes the information dialog", async () => {
  backend();
  render(<Fleet token="test" user={admin} />);
  fireEvent.click(await screen.findByRole("button", { name: /All UAVs/ }));
  fireEvent.click(screen.getByRole("button", { name: "Info for Second UAV" }));
  expect(
    await screen.findByRole("dialog", { name: "Second UAV" }),
  ).toBeInTheDocument();
  expect(await screen.findByText("Missions started")).toBeInTheDocument();
  expect(screen.getByText("Registered on")).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: "Close UAV information" }),
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("registers a UAV with an automatically generated identity", async () => {
  const fetcher = backend();
  const { container } = render(<Fleet token="test" user={admin} />);
  await screen.findByRole("button", { name: /Quadrotor/ });
  const section = container.querySelector(".fleet-registration > details")!;
  fireEvent.click(section.querySelector("summary")!);
  fireEvent.change(screen.getByLabelText("UAV name"), {
    target: { value: "Survey UAV" },
  });
  fireEvent.change(screen.getByLabelText("Type", { exact: true }), {
    target: { value: "quad" },
  });
  fireEvent.submit(section.querySelector("form")!);
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/fleet/vehicles",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  const call = fetcher.mock.calls.find(
    ([, options]) => options?.method === "POST",
  )!;
  const body = JSON.parse(call[1]!.body as string);
  expect(body).toMatchObject({
    name: "Survey UAV",
    type_id: "quad",
    runtime_slot: null,
  });
  expect(body.id).toMatch(/^[0-9a-f-]{36}$/);
});
