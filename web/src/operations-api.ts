export type Mission = {
  id: string;
  name: string;
  area_id: string;
  assignment_id?: string | null;
  operator_id: string;
  field_ids: string[];
  boundary: GeoJSON.Polygon;
  waypoints: [number, number][];
  altitude_m: number;
  speed_m_s: number;
  state: string;
  synthetic_sensors: boolean;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  error?: string;
};
export type Observation = {
  id: string;
  sequence: number;
  longitude: number;
  latitude: number;
  altitude_m: number;
  speed_m_s: number;
  battery_percent: number | null;
  source: string;
  sensor: {
    gpr_response: number;
    metal_response: number;
    quality: number;
    provenance: string;
  } | null;
  created_at: string;
};
export type Target = {
  id: string;
  mission_id: string;
  observation_id: string;
  longitude: number;
  latitude: number;
  confidence: number;
  processing_version: string;
  simulated: boolean;
  classification?: string;
  created_at?: string;
};
export type MissionDetail = {
  mission: Mission;
  observations: Observation[];
  detections: Target[];
  reviews: {
    id: string;
    detection_id: string;
    assessment: string;
    notes: string;
    created_at: string;
  }[];
  events: { id: string; kind: string; detail: string; created_at: string }[];
  coverage: {
    geometry: GeoJSON.Geometry;
    coverage_percent: number;
    algorithm_version: string;
    simulated: boolean;
    notice: string;
  };
  notice: string;
};
