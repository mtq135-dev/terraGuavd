import { useEffect, useRef, useState } from "react";
import PlanningCanvas from "./planning/PlanningCanvas";
import { outline, type Shape, type DrawTool } from "./planning/AreaEditor";
import "./planning/planning.css";
type Point = [number, number];
export default function PlanMap({
  boundary,
  onBoundary,
}: {
  boundary: Point[];
  waypoints: Point[];
  onBoundary: (p: Point[]) => void;
  onWaypoints: (p: Point[]) => void;
  boundaryOnly?: boolean;
  assignedBoundary?: GeoJSON.Polygon;
}) {
  const [shape, setShape] = useState<Shape>({
    kind: "polygon",
    points: boundary.slice(0, -1).map(([x, y]) => [y, x]),
  });
  const [fitTo] = useState(outline(shape));
  const emitted = useRef(JSON.stringify(boundary));
  const boundaryKey = JSON.stringify(boundary);
  useEffect(() => {
    if (emitted.current === boundaryKey) return;
    emitted.current = boundaryKey;
    const pts =
      boundary.length > 1 &&
      boundary[0][0] === boundary.at(-1)![0] &&
      boundary[0][1] === boundary.at(-1)![1]
        ? boundary.slice(0, -1)
        : boundary;
    const next: Shape = {
      kind: "polygon",
      points: pts.map(([x, y]) => [y, x]),
    };
    setShape(next);
    setHistory([next]);
    setAt(0);
  }, [boundaryKey]);
  const [history, setHistory] = useState<Shape[]>([shape]);
  const [at, setAt] = useState(0);
  const [tool, setTool] = useState<DrawTool | null>(null);
  function commit(s: Shape) {
    setShape(s);
    const list = [...history.slice(0, at + 1), s];
    setHistory(list);
    setAt(list.length - 1);
    const ring = outline(s).map(([lat, lon]) => [lon, lat] as Point);
    if (ring.length) ring.push(ring[0]);
    emitted.current = JSON.stringify(ring);
    onBoundary(ring);
  }
  function step(n: number) {
    const next = at + n;
    if (next < 0 || next >= history.length) return;
    setAt(next);
    setShape(history[next]);
    const ring = outline(history[next]).map(
      ([lat, lon]) => [lon, lat] as Point,
    );
    if (ring.length) ring.push(ring[0]);
    emitted.current = JSON.stringify(ring);
    onBoundary(ring);
  }
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target?.isContentEditable ||
        ["INPUT", "SELECT", "TEXTAREA"].includes(target?.tagName)
      )
        return;
      const k = e.key.toLowerCase();
      if (e.ctrlKey || e.metaKey) {
        if (k === "z") {
          e.preventDefault();
          if (!tool) step(e.shiftKey ? 1 : -1);
        }
        if (k === "y") {
          e.preventDefault();
          if (!tool) step(1);
        }
      } else if (k === "escape") setTool(null);
      else {
        const next = (
          { r: "rect", c: "circle", f: "polygon" } as Record<string, DrawTool>
        )[k];
        if (next) setTool(next);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [history, at, tool]);
  return (
    <div>
      <div className="planner-draw-bar">
        {(
          [
            ["rect", "Rectangle"],
            ["circle", "Circle"],
            ["polygon", "Free shape"],
          ] as const
        ).map(([t, label]) => (
          <button
            key={t}
            type="button"
            aria-pressed={tool === t}
            onClick={() => setTool(tool === t ? null : t)}
          >
            {label}
          </button>
        ))}
        <button
          type="button"
          disabled={!!tool || at === 0}
          onClick={() => step(-1)}
        >
          Undo
        </button>
        <button
          type="button"
          disabled={!!tool || at === history.length - 1}
          onClick={() => step(1)}
        >
          Redo
        </button>
        {tool && (
          <button type="button" onClick={() => setTool(null)}>
            Cancel drawing
          </button>
        )}
      </div>
      <PlanningCanvas
        shape={shape}
        tool={tool}
        color="#b1a0e9"
        path={[]}
        fitTo={fitTo}
        overlays={[]}
        onChange={setShape}
        onCommit={commit}
        onDone={(s) => {
          commit(s);
          setTool(null);
        }}
        onDraft={() => {}}
        onCancel={() => setTool(null)}
      />
      <p className="panel-note">
        Rectangle: two opposite corners. Circle: centre then edge. Free shape:
        click corners and return to the first corner to finish. Drag handles to
        edit. This defines the Supervisor assignment; no flight is created.
      </p>
    </div>
  );
}
