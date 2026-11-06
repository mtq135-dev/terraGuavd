import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.removeItem("terraguavd.theme");
  delete document.documentElement.dataset.theme;
});
it("follows the system palette, then persists an explicit theme and matching logo", () => {
  let dark = false;
  const query = new EventTarget() as MediaQueryList;
  Object.defineProperty(query, "matches", { get: () => dark });
  vi.stubGlobal("matchMedia", () => query);
  const app = render(<App />);
  const theme = screen.getByRole("combobox", { name: "Appearance theme" });
  const logo = () =>
    screen.getByRole("link", { name: "TerraGuavd" }).querySelector("img");
  expect(theme).toHaveValue("system");
  expect(logo()).toHaveAttribute("src", "/brand/terraguavd-ivory.png");
  dark = true;
  act(() => {
    query.dispatchEvent(new Event("change"));
  });
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  expect(logo()).toHaveAttribute("src", "/brand/terraguavd-evergreen.png");
  fireEvent.change(theme, { target: { value: "light" } });
  expect(document.documentElement).toHaveAttribute("data-theme", "light");
  app.unmount();
  render(<App />);
  expect(
    screen.getByRole("combobox", { name: "Appearance theme" }),
  ).toHaveValue("light");
  expect(document.documentElement).toHaveAttribute("data-theme", "light");
});
describe("role workspaces", () => {
  for (const [role, title] of Object.entries({
    administrator: "Administration",
    mission_operator: "Mission control",
    detection_analyst: "Detection analysis",
    supervisor: "Operational overview",
    field_personnel: "Field monitoring",
  })) {
    it(`loads the authenticated ${role} workspace`, async () => {
      const fetcher = vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ access_token: "test" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            id: "1",
            username: "user",
            role,
            permissions: [],
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            missions: [],
            potential_detections: [],
            survey_attempts: [],
          }),
        });
      vi.stubGlobal("fetch", fetcher);
      render(<App />);
      fireEvent.change(screen.getByLabelText("Username"), {
        target: { value: "user" },
      });
      fireEvent.change(screen.getByLabelText("Password"), {
        target: { value: "password" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
      expect(
        await screen.findByRole("heading", { name: title }),
      ).toBeInTheDocument();
      expect(fetcher.mock.calls[2][0]).toBe(`/api/v1/dashboards/${role}`);
      expect(
        screen.getAllByText(/Surveyed does not mean cleared or safe/).length,
      ).toBeGreaterThan(0);
    });
  }
  it("reports rejected login", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({
          detail: "Session expired or invalid credentials. Sign in again.",
        }),
      }),
    );
    render(<App />);
    fireEvent.submit(
      screen.getByRole("button", { name: "Sign in" }).closest("form")!,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "invalid credentials",
    );
  });
  it("loads and searches administrator accounts from the backend", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: "test" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "1",
          username: "admin",
          role: "administrator",
          permissions: [],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          missions: [],
          potential_detections: [],
          survey_attempts: [],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            id: "2",
            username: "operator-alice",
            role: "mission_operator",
            permissions: ["missions:read"],
          },
        ],
      });
    vi.stubGlobal("fetch", fetcher);
    render(<App />);
    fireEvent.submit(
      screen.getByRole("button", { name: "Sign in" }).closest("form")!,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Load accounts" }),
    );
    expect(await screen.findByText("operator-alice")).toBeInTheDocument();
    expect(fetcher.mock.calls[3][0]).toBe("/api/v1/admin/users");
    expect(fetcher.mock.calls[3][1].headers.Authorization).toBe("Bearer test");
    fireEvent.change(screen.getByLabelText("Search accounts"), {
      target: { value: "nobody" },
    });
    expect(screen.getByText("No matching accounts.")).toBeInTheDocument();
  });
  it("navigates field alerts and keeps stop requests disabled", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: "test" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "1",
          username: "field",
          role: "field_personnel",
          permissions: [],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          missions: [],
          potential_detections: [],
          survey_attempts: [],
          alerts: [],
        }),
      })
      .mockResolvedValueOnce({ ok: true, status: 204 });
    vi.stubGlobal("fetch", fetcher);
    render(<App />);
    fireEvent.submit(
      screen.getByRole("button", { name: "Sign in" }).closest("form")!,
    );
    fireEvent.click(await screen.findByRole("button", { name: "More" }));
    expect(
      screen.getByRole("combobox", { name: "Appearance theme" }),
    ).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Alerts" }));
    expect(
      screen.queryByRole("combobox", { name: "Appearance theme" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Request mission stop" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(
      await screen.findByRole("heading", { name: "Sign in to TerraGuavd" }),
    ).toBeInTheDocument();
    expect(fetcher.mock.calls[3][0]).toBe("/api/v1/auth/logout");
  });
});
