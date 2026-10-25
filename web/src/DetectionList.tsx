import { Empty, Panel } from "./components";
import { Target } from "./operations-api";

export function usesLegacyMockLabel(target: Target) {
  return (
    target.simulated &&
    (!target.classification || target.classification === "potential_target")
  );
}

export function detectionLabel(target: Target) {
  if (usesLegacyMockLabel(target)) {
    // Stable display-only demo labels; historical classification and score remain intact.
    const labels = ["Potential Mine", "Metallic Object", "Unknown", "Rock"];
    const hash = Array.from(target.id).reduce(
      (value, char) => (value * 31 + char.charCodeAt(0)) >>> 0,
      0,
    );
    return labels[hash % labels.length];
  }
  return (
    (
      {
        potential_mine: "Potential Mine",
        metallic_object: "Metallic Object",
        unknown: "Unknown",
        rock: "Rock",
        potential_target: "Potential target",
      } as Record<string, string>
    )[target.classification ?? "potential_target"] ?? "Potential target"
  );
}

export default function DetectionList({
  targets,
  selectedId,
  onSelect,
}: {
  targets: Target[];
  selectedId?: string;
  onSelect: (target: Target) => void;
}) {
  return (
    <Panel title="Potential detections - synthetic and unverified">
      {!targets.length ? (
        <Empty>No potential targets in recorded observations.</Empty>
      ) : (
        <div className="mission-cards">
          {targets.map((target) => (
            <button
              key={target.id}
              className={`mission-card${selectedId === target.id ? " selected" : ""}`}
              aria-pressed={selectedId === target.id}
              onClick={() => onSelect(target)}
            >
              <strong>{detectionLabel(target)}</strong>
              <span>
                Score {target.confidence.toFixed(2)} - Synthetic fixture
              </span>
              <small>
                {target.latitude.toFixed(6)}, {target.longitude.toFixed(6)}
              </small>
            </button>
          ))}
        </div>
      )}
    </Panel>
  );
}
