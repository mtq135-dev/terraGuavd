import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { SurveyArea } from "./survey-areas-api";
import { Mission } from "./operations-api";

export default function AreaProgressMap({
  area,
  missions = [],
}: {
  area: SurveyArea;
  missions?: Mission[];
}) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | undefined>(undefined);
  const layers = useRef<L.LayerGroup | undefined>(undefined);
  const fitted = useRef("");
  useEffect(() => {
    if (!host.current) return;
    const current = L.map(host.current).setView([47.3978, 8.5456], 17);
    map.current = current;
    fitted.current = "";
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 20,
      attribution: "© OpenStreetMap contributors",
    }).addTo(current);
    layers.current = L.layerGroup().addTo(current);
    const observer = new ResizeObserver(() => current.invalidateSize());
    observer.observe(host.current);
    return () => {
      observer.disconnect();
      current.remove();
    };
  }, []);
  useEffect(() => {
    if (!layers.current) return;
    layers.current.clearLayers();
    for (const [geometry, color, label] of [
      [
        area.progress.remaining_geometry,
        "#85959c",
        "Remaining: no completed or live valid coverage",
      ],
      [
        area.progress.completed_geometry,
        "#43be8a",
        "Completed experimental coverage",
      ],
      [
        area.progress.in_progress_geometry,
        "#e6c961",
        "In-progress valid footprints; not completed",
      ],
    ] as const) {
      L.geoJSON(geometry, {
        style: { color, fillColor: color, fillOpacity: 0.4, weight: 1 },
      })
        .bindTooltip(label)
        .addTo(layers.current);
    }
    const boundary = L.geoJSON(area.boundary, {
      style: { color: "#b1a0e9", weight: 3, fillOpacity: 0 },
    }).addTo(layers.current);
    for (const mission of missions) {
      const label = document.createElement("span");
      label.textContent = `${mission.name} · ${mission.state} · planned sub-mission, not coverage`;
      L.geoJSON(mission.boundary, {
        style: {
          color: "#69b6ef",
          weight: 1.5,
          fillOpacity: 0,
          dashArray: "5 5",
        },
      })
        .bindTooltip(label)
        .addTo(layers.current);
    }
    const key = JSON.stringify(area.boundary);
    if (fitted.current !== key) {
      map.current?.fitBounds(boundary.getBounds(), {
        padding: [20, 20],
        maxZoom: 19,
      });
      fitted.current = key;
    }
  }, [area, missions]);
  return (
    <>
      <div
        ref={host}
        className="live-map"
        aria-label="Assigned survey area coverage map"
      />
      <p className="panel-note">
        Purple outline: assignment · Green: completed experimental coverage ·
        Yellow: in-progress valid footprints · Gray: remaining · Blue dashed:
        planned sub-missions on the current history page. Colors are also
        identified by layer tooltips. Surveyed does not mean cleared or safe.
      </p>
    </>
  );
}
