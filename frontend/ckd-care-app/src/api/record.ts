import { api } from "./client";

export type DrinkType = "WATER" | "COFFEE" | "JUICE" | "OTHER";
export type GoalType = "target" | "limit";
export type WarningLevel = "none" | "warn" | "over";

export interface WaterEntry {
  id: number;
  amount_ml: number;
  drink_type: DrinkType;
  created_at: string;
}

export interface WaterToday {
  date: string;
  total_ml: number;
  goal_ml: number;
  goal_type: GoalType;
  progress_pct: number;
  warning_level: WarningLevel;
  entries: WaterEntry[];
  disclaimer: string | null;
}

export interface AutoCheckin {
  performed: boolean;
  reason: string;
}

export interface AddWaterResponse {
  today: WaterToday;
  auto_checkin: AutoCheckin;
}

export interface WaterHistory {
  days: number;
  items: { date: string; total_ml: number }[];
}

export interface RecordSettings {
  water_goal_ml: number;
  goal_type: GoalType;
}

// ── 체중 기록 타입 ──
export interface WeightToday {
  date: string;
  weight_kg: number | null;
  prev_weight_kg: number | null;
  delta_kg: number | null;
  warning_level: WarningLevel;
  note: string | null;
  measured_at: string | null;
  has_record: boolean;
  disclaimer: string | null;
}
export interface LogWeightResponse {
  today: WeightToday;
  auto_checkin: AutoCheckin;
}
export interface WeightHistory {
  days: number;
  items: { date: string; weight_kg: number }[];
}

export const recordApi = {
  // 오늘 수분 섭취 현황 조회
  getWaterToday: () => api.get<WaterToday>("/records/water/today"),
  // 수분 섭취 기록 추가
  addWater: (amount_ml: number, drink_type: DrinkType) =>
    api.post<AddWaterResponse>("/records/water", { amount_ml, drink_type }),
  // 수분 섭취 기록 삭제
  deleteWater: (id: number) => api.delete<WaterToday>(`/records/water/${id}`),
  // 수분 섭취 이력 조회 (기본 30일)
  getWaterHistory: (days = 30) =>
    api.get<WaterHistory>(`/records/water/history?days=${days}`),
  // 수분 목표 설정 조회
  getSettings: () => api.get<RecordSettings>("/records/settings"),
  // 수분 목표 설정 변경
  setSettings: (water_goal_ml: number) =>
    api.put<RecordSettings>("/records/settings", { water_goal_ml }),
  // 오늘 체중 조회
  getWeightToday: () => api.get<WeightToday>("/records/weight/today"),
  // 체중 기록/수정 (upsert)
  logWeight: (weight_kg: number, note?: string) =>
    api.put<LogWeightResponse>("/records/weight", { weight_kg, note: note ?? null }),
  // 오늘 체중 삭제
  deleteWeight: () => api.delete<WeightToday>("/records/weight"),
  // 체중 추이
  getWeightHistory: (days = 7) =>
    api.get<WeightHistory>(`/records/weight/history?days=${days}`),
};
