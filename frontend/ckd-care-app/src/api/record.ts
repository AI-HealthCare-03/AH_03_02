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
};
