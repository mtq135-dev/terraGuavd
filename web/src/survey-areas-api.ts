import { Mission } from "./operations-api";

export type AreaProgress = {
  completed_geometry: GeoJSON.Geometry;
  in_progress_geometry: GeoJSON.Geometry;
  remaining_geometry: GeoJSON.Geometry;
  total_m2: number;
  completed_m2: number;
  in_progress_m2: number;
  remaining_m2: number;
  coverage_percent: number;
  fully_surveyed: boolean;
  simulated: boolean;
  algorithm_version: string;
  notice: string;
};
export type SurveyArea = {
  id: string;
  name: string;
  description: string;
  operator_id: string;
  operator_username: string;
  created_by: string;
  boundary: GeoJSON.Polygon;
  deadline: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
  status: "ASSIGNED" | "IN_PROGRESS" | "COMPLETED";
  overdue: boolean;
  progress: AreaProgress;
};
export type SurveyAreaDetail = SurveyArea & {
  missions: Mission[];
  surveys: {
    id: string;
    mission_id: string;
    status: string;
    coverage_percent: number;
    algorithm_version: string;
    finished_at: string;
  }[];
  history: {
    id: string;
    kind: string;
    actor_id: string;
    created_at: string;
    snapshot: SurveyArea;
  }[];
};

export function parsePoints(value: string): [number, number][] {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) &&
      parsed.every(
        (p) =>
          Array.isArray(p) &&
          p.length === 2 &&
          p.every((n) => typeof n === "number" && Number.isFinite(n)),
      )
      ? parsed
      : [];
  } catch {
    return [];
  }
}
