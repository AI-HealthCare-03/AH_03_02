import { api } from "./client";

export type ChallengeCategory = "HYDRATION" | "EXERCISE" | "DIET" | "SLEEP" | "STRESS";
export type ChallengeTrack = "A" | "B";
export type UserChallengeStatus = "ACTIVE" | "COMPLETED" | "ABANDONED";

export interface Challenge {
  id: number;
  name: string;
  category: ChallengeCategory;
  description: string;
  duration_days: number;
  track: ChallengeTrack;
}

export interface ChallengeListResponse {
  total: number;
  items: Challenge[];
}

export interface UserChallenge {
  id: number;
  challenge_id: number;
  started_at: string;
  status: UserChallengeStatus;
  streak_count: number;
  total_checkins: number;
  last_checkin_date: string | null;
  created_at: string;
}

export interface UserChallengeListResponse {
  total: number;
  items: UserChallenge[];
}

export interface CheckinAward {
  base: number;
  lucky: boolean;
  lucky_extra: number;
  streak_bonus: number;
  streak_milestone: number;
  full_participation: boolean;
  full_participation_bonus: number;
  total: number;
}

export interface EggUpdate {
  progress_checkins: number;
  current_stage: number;  // 0=알, 1=부화, 2/3/4=진화 단계
  goal_70_just_alerted: boolean;
  goal_90_just_alerted: boolean;
  stage_bonus: number;
  stage_milestone: number;  // 도달한 임계 (10/40/100/200)
  hatched: boolean;  // 1단계 부화 (종 추첨)
  evolved_to: number | null;  // 진화한 단계 (2/3/4)
  is_legendary: boolean | null;
  species: string | null;
  character_name: string | null;
  new_egg_no: number | null;
}

export interface CheckInResponse {
  id: number;
  streak_count: number;
  total_checkins: number;
  last_checkin_date: string;
  status: UserChallengeStatus;
  message: string;
  award: CheckinAward | null;
  egg: EggUpdate | null;
}

export interface HeatmapDay {
  date: string;
  count: number;
}

export interface HeatmapResponse {
  weeks: number;
  today: string;
  days: HeatmapDay[];
  max_count: number;
}

export interface CategoryProgress {
  category: ChallengeCategory;
  percent: number;
  active_count: number;
  total_checkins: number;
  total_duration: number;
}

export interface CategoryProgressResponse {
  items: CategoryProgress[];
}

export interface CancelCheckinResponse {
  message: string;
  points_revoked: number;
}

export const challengeApi = {
  list: () => api.get<ChallengeListResponse>("/challenges"),
  myList: (limit = 20, offset = 0) =>
    api.get<UserChallengeListResponse>(`/user-challenges?limit=${limit}&offset=${offset}`),
  join: (challenge_id: number, started_at: string) =>
    api.post<UserChallenge>("/user-challenges", { challenge_id, started_at }),
  checkin: (userChallengeId: number) =>
    api.post<CheckInResponse>(`/user-challenges/${userChallengeId}/checkin`, {}),
  cancelCheckin: (userChallengeId: number) =>
    api.delete<CancelCheckinResponse>(`/user-challenges/${userChallengeId}/checkin`),
  abandon: (userChallengeId: number) =>
    api.delete<{ message: string }>(`/user-challenges/${userChallengeId}`),
  heatmap: (weeks = 26) => api.get<HeatmapResponse>(`/challenges/heatmap?weeks=${weeks}`),
  categoryProgress: () => api.get<CategoryProgressResponse>("/challenges/category-progress"),
  weeklyEmotion: () => api.get<WeeklyEmotionResponse>("/challenges/weekly-emotion"),
};

export type CheckinEmotion =
  | "VERY_HAPPY"
  | "HAPPY"
  | "NEUTRAL"
  | "ANXIOUS"
  | "SAD"
  | "ANGRY"
  | "TIRED";

export const EMOTION_EMOJI: Record<CheckinEmotion, string> = {
  VERY_HAPPY: "😄",
  HAPPY: "🙂",
  NEUTRAL: "😐",
  ANXIOUS: "😟",
  SAD: "😢",
  ANGRY: "😠",
  TIRED: "😴",
};

export interface EmotionDay {
  date: string;
  emotion: CheckinEmotion | null;
}

export interface WeeklyEmotionResponse {
  days: EmotionDay[];
}
