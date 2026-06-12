import { api } from "./client";

export interface DietSurveyCreateRequest {
  surveyed_date: string;
  soup_stew_per_day: number;
  sweet_drink_per_day: number;
  fried_food_per_week: number;
  vegetables_every_meal: boolean;
  // 칼륨·단백질: A(G1)·B(G2)·진단자만 응답 (음식군 빈도 0적음/1보통/2많음). 미해당·미응답은 null.
  potassium_food_freq?: number | null;
  protein_food_freq?: number | null;
}

export interface DietSurveyResponse {
  id: number;
  user_id: number;
  surveyed_date: string;
  soup_stew_per_day: number;
  sweet_drink_per_day: number;
  fried_food_per_week: number;
  vegetables_every_meal: boolean;
  created_at: string;
}

export interface DietSurveyListResponse {
  total: number;
  items: DietSurveyResponse[];
}

export interface SurveyStatusResponse {
  lifestyle_survey: boolean;
  diet_survey: boolean;
}

export const dietSurveyApi = {
  create: (body: DietSurveyCreateRequest) =>
    api.post<DietSurveyResponse>("/diet-surveys", body),
  list: (limit = 20, offset = 0) =>
    api.get<DietSurveyListResponse>(`/diet-surveys?limit=${limit}&offset=${offset}`),
  getSurveyStatus: () =>
    api.get<SurveyStatusResponse>("/surveys/status"),
};
