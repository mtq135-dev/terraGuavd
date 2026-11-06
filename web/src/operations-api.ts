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
  plan_revision?: number;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  error?: string;
};
export type ApprovalStatus =
  "Pending" | "Approved" | "Rejected" | "Invalidated";
type ApprovalAssignment = {
  id: string;
  name: string;
  boundary: GeoJSON.Polygon;
  revision: number;
  supervisor_username: string | null;
};
export type ApprovalRequest = {
  id: string;
  status: ApprovalStatus;
  reason: string;
  requested_at: string;
  decision_reason: string | null;
  decided_at: string | null;
  snapshot: {
    assignment: ApprovalAssignment;
    configuration: Pick<
      Mission,
      | "id"
      | "name"
      | "boundary"
      | "waypoints"
      | "altitude_m"
      | "speed_m_s"
      | "synthetic_sensors"
    >;
    outside_geometry: GeoJSON.Geometry;
    outside_m2: number;
  };
};
export type ApprovalPreview = {
  required: boolean;
  outside_geometry: GeoJSON.Geometry;
  outside_m2: number;
};
export type MissionApproval = ApprovalPreview & {
  status: ApprovalStatus | "Not Required" | null;
  can_execute: boolean;
  warning: string | null;
  assignment: ApprovalAssignment | null;
  request: ApprovalRequest | null;
  history: ApprovalRequest[];
};
export type ApprovalListItem = {
  request: ApprovalRequest;
  status: ApprovalStatus;
  current: boolean;
  mission: Pick<Mission, "id" | "name">;
  operator_username: string | null;
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
  approval?: MissionApproval | null;
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
