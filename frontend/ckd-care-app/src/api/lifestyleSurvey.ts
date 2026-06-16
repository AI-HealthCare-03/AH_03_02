import { api } from "./client";

export type SmokingStatus = "NEVER" | "PAST" | "CURRENT";
export type DrinkingFrequency = "NEVER" | "OCCASIONALLY" | "WEEKLY" | "DAILY";
export type StressLevel = "VERY_LOW" | "LOW" | "MODERATE" | "HIGH" | "VERY_HIGH";
export type MaritalStatus = "SINGLE" | "MARRIED" | "DIVORCED" | "WIDOWED" | "OTHER";
export type DialysisType = "none" | "hemodialysis" | "peritoneal" | "transplant";

export interface LifestyleSurveyCreateRequest {
  surveyed_date: string;
  smoking_status: SmokingStatus;
  drinking_frequency: DrinkingFrequency;
  exercise_days_per_week: number;
  sleep_hours_per_day?: number | null;
  daily_water_intake?: number | null;
  stress_level?: StressLevel | null;
  // REQ-DATA-006 신규
  vigorous_exercise_days?: number;
  vigorous_exercise_minutes?: number;
  moderate_exercise_days?: number;
  moderate_exercise_minutes?: number;
  sitting_hours_per_day?: number | null;
  marital_status?: MaritalStatus | null;
  family_history_diabetes?: boolean;
  family_history_hypertension?: boolean;
  family_history_heart_disease?: boolean;
  family_history_dyslipidemia?: boolean;
  family_history_stroke?: boolean;
  // 본인 진단력 (작업3)
  htn_diagnosed?: boolean;
  dm_diagnosed?: boolean;
  dyslipidemia_diagnosed?: boolean;
  ckd_diagnosed?: boolean;
  dialysis_type?: DialysisType | null;
  is_pregnant?: boolean;
}

export interface LifestyleSurveyResponse {
  id: number;
  user_id: number;
  surveyed_date: string;
  smoking_status: SmokingStatus;
  drinking_frequency: DrinkingFrequency;
  exercise_days_per_week: number;
  sleep_hours_per_day: number | null;
  daily_water_intake: number | null;
  stress_level: StressLevel | null;
  vigorous_exercise_days: number;
  vigorous_exercise_minutes: number;
  moderate_exercise_days: number;
  moderate_exercise_minutes: number;
  sitting_hours_per_day: number | null;
  marital_status: MaritalStatus | null;
  family_history_diabetes: boolean;
  family_history_hypertension: boolean;
  family_history_heart_disease: boolean;
  family_history_dyslipidemia: boolean;
  family_history_stroke: boolean;
  // 본인 진단력 (작업3)
  htn_diagnosed: boolean;
  dm_diagnosed: boolean;
  dyslipidemia_diagnosed: boolean;
  ckd_diagnosed: boolean;
  dialysis_type: DialysisType | null;
  is_pregnant: boolean;
  created_at: string;
}

export interface LifestyleSurveyListResponse {
  total: number;
  items: LifestyleSurveyResponse[];
}

export const lifestyleSurveyApi = {
  create: (body: LifestyleSurveyCreateRequest) =>
    api.post<LifestyleSurveyResponse>("/lifestyle-surveys", body),
  list: (limit = 20, offset = 0) =>
    api.get<LifestyleSurveyListResponse>(`/lifestyle-surveys?limit=${limit}&offset=${offset}`),
  delete: (id: number) =>
    api.delete<void>(`/lifestyle-surveys/${id}`),
};
