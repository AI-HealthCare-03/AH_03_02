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

// ── 수면 기록 타입 ──
export interface SleepToday {
  date: string;
  bed_time: string | null;
  wake_time: string | null;
  wake_count: number | null;
  duration_min: number | null;
  goal_met: boolean;
  has_record: boolean;
}
export interface LogSleepResponse {
  today: SleepToday;
  auto_checkin: AutoCheckin;
}
export interface SleepHistory {
  days: number;
  items: { date: string; duration_min: number }[];
}

// ── 스트레스(감정 쓰레기통) 타입 ──
export type StressEmotion =
  | "ANXIOUS"
  | "TENSE"
  | "ANGRY"
  | "SAD"
  | "LONELY"
  | "LISTLESS"
  | "GRATEFUL"
  | "RELIEVED";
export interface StressToday {
  date: string;
  has_record: boolean;
  drop_count: number;
  today_emotions: StressEmotion[];
}
export interface DropStressResponse {
  today: StressToday;
  auto_checkin: AutoCheckin;
}
export interface StressHistory {
  days: number;
  counts: { emotion: StressEmotion; count: number }[];
}

// ── 운동 피로도 타입 ──
export type ExerciseType = "WALK" | "CYCLE" | "STRENGTH" | "STRETCH" | "OTHER";
export interface ExerciseEntry {
  id: number;
  exercise_type: ExerciseType;
  duration_min: number;
  fatigue_level: number;
  note: string | null;
  created_at: string;
}
export interface ExerciseToday {
  date: string;
  entries: ExerciseEntry[];
  total_duration_min: number;
  max_fatigue: number | null;
  has_record: boolean;
  suggest_rest: boolean;
  rest_message: string | null;
}
export interface LogExerciseResponse {
  today: ExerciseToday;
  auto_checkin: AutoCheckin;
}
export interface ExerciseHistory {
  days: number;
  items: { date: string; avg_fatigue: number }[];
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
  // 오늘 수면 조회
  getSleepToday: () => api.get<SleepToday>("/records/sleep/today"),
  // 수면 기록/수정 (upsert) — bed_time/wake_time = "HH:MM"
  logSleep: (bed_time: string, wake_time: string, wake_count: number) =>
    api.put<LogSleepResponse>("/records/sleep", { bed_time, wake_time, wake_count }),
  // 오늘 수면 삭제
  deleteSleep: () => api.delete<SleepToday>("/records/sleep"),
  // 수면 추이
  getSleepHistory: (days = 7) =>
    api.get<SleepHistory>(`/records/sleep/history?days=${days}`),
  // 오늘 감정 기록 조회
  getStressToday: () => api.get<StressToday>("/records/stress/today"),
  // 감정 '버리기' (이벤트 append, emotions만 전송 — 텍스트는 저장 안 함)
  dropStress: (emotions: StressEmotion[]) =>
    api.post<DropStressResponse>("/records/stress", { emotions }),
  // 최근 7일 감정 빈도
  getStressHistory: (days = 7) =>
    api.get<StressHistory>(`/records/stress/history?days=${days}`),
  // 오늘 운동 기록 조회
  getExerciseToday: () => api.get<ExerciseToday>("/records/exercise/today"),
  // 운동 기록 추가 (append)
  logExercise: (body: {
    exercise_type: ExerciseType;
    duration_min: number;
    fatigue_level: number;
    note?: string | null;
  }) => api.post<LogExerciseResponse>("/records/exercise", body),
  // 운동 기록 삭제 (개별)
  deleteExercise: (id: number) =>
    api.delete<ExerciseToday>(`/records/exercise/${id}`),
  // 최근 7일 일별 평균 피로도
  getExerciseHistory: (days = 7) =>
    api.get<ExerciseHistory>(`/records/exercise/history?days=${days}`),
};
