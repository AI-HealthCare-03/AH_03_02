import { api } from "./client";

export type MicroChallengeCode =
  | "HYDRATION_CUP"
  | "EXERCISE_STRETCH"
  | "DIET_VEGGIE"
  | "SLEEP_EARLY"
  | "STRESS_BREATH";

export interface MicroChallenge {
  code: MicroChallengeCode;
  category: string;
  title: string;
  icon: string;
  minutes: number;
  hint: string;
}

export interface SlumpStatusResponse {
  is_slump: boolean;
  days_since_last_checkin: number;
  threshold_days: number;
  micro: MicroChallenge;
  already_checked_in_today: boolean;
}

export interface SlumpMicroCheckinResponse {
  recovered: boolean;
  micro_code: MicroChallengeCode;
  checked_at: string;
  message: string;
}

export const slumpApi = {
  status: () => api.get<SlumpStatusResponse>("/challenges/slump-micro"),
  checkin: (micro_code: MicroChallengeCode) =>
    api.post<SlumpMicroCheckinResponse>("/challenges/slump-micro/checkin", { micro_code }),
};
