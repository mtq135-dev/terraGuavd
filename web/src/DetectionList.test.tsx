import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import DetectionList, { detectionLabel } from "./DetectionList";
import { Target } from "./operations-api";

afterEach(cleanup);
const classes = [
  "potential_mine",
  "metallic_object",
  "potential_mine",
  "unknown",
  "potential_mine",
  "rock",
  "potential_mine",
];
const targets: Target[] = classes.map((classification, index) => ({
  id: `target-${index}`,
  mission_id: "mission",
  observation_id: `observation-${index}`,
  latitude: 47.3,
  longitude: 8.5,
  confidence: [0.87, 0.76, 0.91, 0.65, 0.82, 0.66, 0.88][index],
  classification,
  created_at: `2026-10-25T10:${String(23 - index).padStart(2, "0")}:00Z`,
  processing_version: "experimental",
  simulated: true,
}));

it("keeps the original cards with mock classification labels and selects the stored record", () => {
  const select = vi.fn();
  render(
    <DetectionList targets={targets} selectedId="target-0" onSelect={select} />,
  );
  const selected = screen.getByRole("button", {
    name: /Potential Mine Score 0.87/,
  });
  expect(selected).toHaveClass("mission-card", "selected");
  expect(selected).toHaveAttribute("aria-pressed", "true");
  expect(
    screen.getByRole("button", { name: /Unknown Score/ }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /Rock Score/ }),
  ).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: /Metallic Object Score/ }),
  );
  expect(select).toHaveBeenCalledWith(targets[1]);
  expect(
    screen.getByText("Potential detections - synthetic and unverified"),
  ).toBeInTheDocument();
});

it("shows an empty state without inventing detections", () => {
  render(<DetectionList targets={[]} onSelect={vi.fn()} />);
  expect(
    screen.getByText("No potential targets in recorded observations."),
  ).toBeInTheDocument();
});

it("labels legacy simulated records consistently without changing recorded evidence", () => {
  const legacy = {
    ...targets[0],
    classification: "potential_target",
    confidence: 0.84,
  };
  const before = JSON.stringify(legacy);
  expect(["Potential Mine", "Metallic Object", "Unknown", "Rock"]).toContain(
    detectionLabel(legacy),
  );
  expect(detectionLabel({ ...legacy })).toBe(detectionLabel(legacy));
  expect(JSON.stringify(legacy)).toBe(before);
  expect(detectionLabel({ ...legacy, simulated: false })).toBe(
    "Potential target",
  );
});
