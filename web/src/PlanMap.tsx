import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

type Point = [number, number];
export default function PlanMap({
  boundary,
  waypoints,
  onBoundary,
  onWaypoints,
  assignedBoundary,
  boundaryOnly = false,
}: {
  boundary: Point[];
  waypoints: Point[];
  onBoundary: (points: Point[]) => void;
  onWaypoints: (points: Point[]) => void;
  assignedBoundary?: GeoJSON.Polygon;
  boundaryOnly?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | undefined>(undefined);
  const layer = useRef<L.LayerGroup | undefined>(undefined);
  const fitted = useRef("");
  const [mode, setMode] = useState<"boundary" | "waypoints">("boundary");
  useEffect(() => {
    if (!host.current) return;
    const current = L.map(host.current).setView([47.3978, 8.54565], 18);
    map.current = current;
    fitted.current = "";
    if (boundaryOnly && boundary.length >= 4) {
      current.fitBounds(
        L.latLngBounds(boundary.map(([x, y]) => L.latLng(y, x))),
        { padding: [20, 20] },
      );
      fitted.current = "initial";
    }
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 20,
      attribution: "© OpenStreetMap contributors",
    }).addTo(current);
    layer.current = L.layerGroup().addTo(current);
    const observer = new ResizeObserver(() => current.invalidateSize());
    observer.observe(host.current);
    return () => {
      observer.disconnect();
      current.remove();
    };
  }, []);
  useEffect(() => {
    if (!map.current) return;
    const clicked = (event: L.LeafletMouseEvent) => {
      const point: Point = [
        Number(event.latlng.lng.toFixed(7)),
        Number(event.latlng.lat.toFixed(7)),
      ];
      if (mode === "waypoints") {
        onWaypoints([...waypoints, point]);
      } else {
        const open =
          boundary.length > 1 &&
          boundary[0][0] === boundary.at(-1)![0] &&
          boundary[0][1] === boundary.at(-1)![1]
            ? boundary.slice(0, -1)
            : boundary;
        const points = [...open, point];
        onBoundary(points.length > 1 ? [...points, points[0]] : points);
      }
    };
    map.current.on("click", clicked);
    return () => {
      map.current?.off("click", clicked);
    };
  }, [boundary, waypoints, mode, onBoundary, onWaypoints]);
  useEffect(() => {
    if (!layer.current) return;
    layer.current.clearLayers();
    if (assignedBoundary) {
      const context = L.geoJSON(assignedBoundary, {
        style: {
          color: "#b1a0e9",
          weight: 3,
          fillOpacity: 0.04,
          dashArray: "7 5",
        },
      }).addTo(layer.current);
      const key = JSON.stringify(assignedBoundary);
      if (fitted.current !== key) {
        map.current?.fitBounds(context.getBounds(), {
          padding: [20, 20],
          maxZoom: 19,
        });
        fitted.current = key;
      }
    }
    const ring = boundary.map(([x, y]) => L.latLng(y, x));
    if (ring.length >= 3)
      L.polygon(ring, { color: "#5ba9f0", fillOpacity: 0.12 }).addTo(
        layer.current,
      );
    else L.polyline(ring, { color: "#5ba9f0" }).addTo(layer.current);
    L.polyline(
      waypoints.map(([x, y]) => L.latLng(y, x)),
      { color: "#e1cc8e", dashArray: "5 4" },
    ).addTo(layer.current);
    waypoints.forEach(([x, y], index) =>
      L.circleMarker([y, x], { radius: 5, color: "#e1cc8e" })
        .bindTooltip(`Waypoint ${index + 1}`)
        .addTo(layer.current!),
    );
  }, [boundary, waypoints, assignedBoundary, boundaryOnly]);
  return (
    <div>
      <div className="command-row">
        <button
          type="button"
          aria-pressed={mode === "boundary"}
          onClick={() => setMode("boundary")}
        >
          Draw boundary
        </button>
        {!boundaryOnly && (
          <button
            type="button"
            aria-pressed={mode === "waypoints"}
            onClick={() => setMode("waypoints")}
          >
            Add waypoints
          </button>
        )}
        <button type="button" onClick={() => onBoundary([])}>
          Clear boundary
        </button>
        {!boundaryOnly && (
          <button type="button" onClick={() => onWaypoints([])}>
            Clear waypoints
          </button>
        )}
      </div>
      <p className="panel-note">
        Click map vertices in order. Boundary closes automatically.{" "}
        {boundaryOnly
          ? "Draw the large assignment area; no flight is created."
          : "Draw a smaller mission and route inside the purple assigned boundary. Flight execution remains limited to the simulator home."}
      </p>
      <div
        ref={host}
        className="live-map"
        aria-label="Interactive survey planning map"
      />
    </div>
  );
}
