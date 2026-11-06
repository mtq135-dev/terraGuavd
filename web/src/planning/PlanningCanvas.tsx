import { useEffect, useState } from "react";
import {
  MapContainer,
  CircleMarker,
  TileLayer,
  Polygon,
  Polyline,
  Tooltip,
  useMap,
} from "react-leaflet";
import {
  AreaDrawer,
  AreaHandles,
  AreaLabels,
  outline,
  type Shape,
  type DrawTool,
  type LatLon,
} from "./AreaEditor";
import "leaflet/dist/leaflet.css";
type Overlay = {
  id: string;
  name: string;
  uav: string;
  points: LatLon[];
  color: string;
};
function Fit({ ring }: { ring: LatLon[] }) {
  const map = useMap();
  const key = JSON.stringify(ring);
  useEffect(() => {
    if (ring.length >= 3)
      map.fitBounds(ring, { padding: [28, 28], maxZoom: 19 });
  }, [key, map]);
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}
export default function PlanningCanvas({
  shape,
  tool,
  color,
  path,
  fitTo,
  overlays,
  onChange,
  onCommit,
  onDone,
  onDraft,
  onCancel,
  editable = true,
}: {
  editable?: boolean;
  shape: Shape;
  tool: DrawTool | null;
  color: string;
  path: LatLon[];
  fitTo: LatLon[];
  overlays: Overlay[];
  onChange: (s: Shape) => void;
  onCommit: (s: Shape) => void;
  onDone: (s: Shape) => void;
  onDraft: (p: LatLon[] | null) => void;
  onCancel: () => void;
}) {
  const area = outline(shape);
  const [tileError, setTileError] = useState(false);
  return (
    <MapContainer
      center={[47.3978, 8.54565]}
      zoom={18}
      className="reference-plan-map"
      aria-label="Survey area editor"
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="© OpenStreetMap contributors"
        maxZoom={20}
        eventHandlers={{ tileerror: () => setTileError(true) }}
      />
      <Fit ring={fitTo} />
      {tileError && (
        <div className="planner-tile-error" role="status">
          Base map tiles are unavailable. Outlines and coordinates remain
          editable.
        </div>
      )}
      {overlays.map(
        (o) =>
          o.points.length >= 3 && (
            <Polygon
              key={o.id}
              positions={o.points}
              interactive={false}
              pathOptions={{
                color: o.color,
                weight: 2,
                dashArray: "6 5",
                fillOpacity: 0.04,
              }}
            >
              <Tooltip permanent direction="center">
                {o.name} · {o.uav}
              </Tooltip>
            </Polygon>
          ),
      )}
      {area.length >= 3 && (
        <Polygon
          positions={area}
          interactive={false}
          pathOptions={{ color, weight: 3, fillOpacity: 0.1 }}
        />
      )}
      {path.length >= 2 && (
        <Polyline
          positions={path}
          interactive={false}
          pathOptions={{ color: "#f3ca80", weight: 2 }}
        />
      )}
      {path.length >= 2 && (
        <CircleMarker
          center={path[0]}
          radius={5}
          pathOptions={{ color: "#f3ca80", fillOpacity: 1 }}
        >
          <Tooltip>Planned simulation start</Tooltip>
        </CircleMarker>
      )}
      {tool ? (
        <AreaDrawer
          tool={tool}
          color={color}
          onDone={onDone}
          onDraft={onDraft}
          onCancel={onCancel}
        />
      ) : (
        area.length >= 3 && (
          <>
            <AreaLabels shape={shape} />
            {editable && (
              <AreaHandles shape={shape} onChange={onChange} onEnd={onCommit} />
            )}
          </>
        )
      )}
    </MapContainer>
  );
}
