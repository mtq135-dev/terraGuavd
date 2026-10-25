import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MissionDetail } from "./operations-api";

export default function SurveyMap({ detail }: { detail: MissionDetail }) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | undefined>(undefined);
  const layers = useRef<L.LayerGroup | undefined>(undefined);
  const selected = useRef("");
  useEffect(() => {
    if (!host.current) return;
    map.current = L.map(host.current).setView([47.397742, 8.545594], 18);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 20,
      attribution: "© OpenStreetMap contributors",
    }).addTo(map.current);
    layers.current = L.layerGroup().addTo(map.current);
    const observer = new ResizeObserver(() => map.current?.invalidateSize());
    observer.observe(host.current);
    return () => {
      observer.disconnect();
      map.current?.remove();
      map.current = undefined;
    };
  }, []);
  useEffect(() => {
    if (!map.current || !layers.current) return;
    const layer = layers.current;
    layer.clearLayers();
    const boundary = L.geoJSON(detail.mission.boundary, {
      style: { color: "#5ba9f0", weight: 2, fillOpacity: 0.05 },
    }).addTo(layer);
    L.polyline(
      detail.mission.waypoints.map(([x, y]) => [y, x]),
      { color: "#e1cc8e", dashArray: "6 5", weight: 2 },
    ).addTo(layer);
    if (detail.observations.length) {
      L.polyline(
        detail.observations.map((p) => [p.latitude, p.longitude]),
        { color: "#71dbbf", weight: 2 },
      ).addTo(layer);
      const p = detail.observations.at(-1)!;
      L.marker([p.latitude, p.longitude], {
        icon: L.divIcon({
          className: "uav-marker",
          html: '<svg viewBox="0 0 64 64" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="4"><path d="M20 20L44 44M44 20L20 44"/><circle cx="16" cy="16" r="11"/><circle cx="48" cy="16" r="11"/><circle cx="16" cy="48" r="11"/><circle cx="48" cy="48" r="11"/></g><rect x="24" y="23" width="16" height="20" rx="5" fill="currentColor"/><path d="M28 24L32 18L36 24" fill="#fff5dc"/></svg>',
          iconSize: [40, 40],
          iconAnchor: [20, 20],
        }),
        title: "Simulated UAV · latest recorded position",
      })
        .bindTooltip("Simulated UAV")
        .addTo(layer);
    }
    L.geoJSON(detail.coverage.geometry, {
      style: {
        color:
          detail.mission.state === "COMPLETED"
            ? "#43be8a"
            : [
                  "EXECUTING",
                  "PAUSED",
                  "RESUMING",
                  "STARTING_SIMULATION",
                  "WAITING_FOR_VEHICLE",
                  "UPLOADING",
                ].includes(detail.mission.state)
              ? "#e6c961"
              : "#d47668",
        weight: 1,
        fillOpacity: 0.25,
      },
    }).addTo(layer);
    for (const target of detail.detections)
      L.circleMarker([target.latitude, target.longitude], {
        radius: 5,
        color: "#f35b6d",
        fillOpacity: 0.8,
      })
        .bindTooltip(
          `Synthetic potential target · ${target.confidence.toFixed(2)} · unverified`,
        )
        .addTo(layer);
    if (selected.current !== detail.mission.id) {
      map.current.fitBounds(boundary.getBounds(), {
        padding: [20, 20],
        maxZoom: 19,
      });
      selected.current = detail.mission.id;
    }
  }, [detail]);
  return (
    <>
      <div
        ref={host}
        className="live-map"
        aria-label="Simulated survey mission map"
      />
      <p className="panel-note">
        Blue: planned area · Cream dashed: planned route · Mint: actual SITL
        track · Filled: experimental synthetic sensor coverage · Red: unverified
        synthetic targets. Map tiles require internet.
      </p>
    </>
  );
}
