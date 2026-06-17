import { api } from "./client";

// ── 신버전 타입: 5트랙·9카테고리·stage ──────────────────────────────────────
export type ChallengeCategory =
  | "HYDRATION"
  | "EXERCISE"
  | "DIET"
  | "SLEEP"
  | "STRESS"
  | "EDUCATION"
  | "RECORD"
  | "MONITORING"
  | "EMOTION";

export type ChallengeTrack =
  | "DIALYSIS"
  | "CKD"
  | "INTENSIVE"
  | "DAILY"
  | "WELLNESS";

// CKD 진단자 트랙 — 이 트랙이면 챌린지 화면을 진단자 전용(서브탭)으로 분기
export const CKD_TRACKS: ChallengeTrack[] = ["CKD", "DIALYSIS"];

export type UserChallengeStatus = "ACTIVE" | "COMPLETED" | "ABANDONED";

export interface Challenge {
  id: number;
  name: string;
  category: ChallengeCategory;
  description: string;
  duration_days: number;
  track: ChallengeTrack;
  stage: number; // 1~4
}

// ── 기존 유지 타입 ────────────────────────────────────────────────────────────
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

// ── 신규 타입: my-track·daily-checklist ──────────────────────────────────────
export interface TrackCategoryInfo {
  category: ChallengeCategory;
  label: string;
}

export interface MyTrack {
  track: ChallengeTrack;
  track_label: string;
  stage: number;
  stage_label: string;
  auto_assigned: boolean;
  categories: TrackCategoryInfo[];
}

export interface DailyChecklistItem {
  item_key: string;
  text: string;
  checked: boolean;
}

export interface DailyChecklistResponse {
  date: string;
  track: ChallengeTrack;
  items: DailyChecklistItem[];
}

export interface DailyChecklistToggleResult {
  item_key: string;
  text: string;
  checked: boolean;
  points_awarded: number;   // 이번 토글 순변동 (+5/+35/-5/-35/0)
  all_completed: boolean;
  full_bonus_awarded: number; // 0 또는 30
  egg: EggUpdate | null;
}

// ── 월별 달력 타입 ────────────────────────────────────────────────────────────
export type CalendarLevel = "none" | "basic" | "silver" | "gold";

export interface CalendarDay {
  date: string; // YYYY-MM-DD
  required: boolean;
  selected_count: number;
  level: CalendarLevel;
}

export interface MonthlyCalendarResponse {
  year_month: string;
  days: CalendarDay[];
  achieved_days: number;
  gold_days: number;
  max_streak: number;
}

// ── challengeApi ─────────────────────────────────────────────────────────────
export const challengeApi = {
  // ── 신버전 (트랙·스테이지·필수체크) ─────────────────────────────────────
  myTrack: () => api.get<MyTrack>("/challenges/my-track"),
  // 트랙은 자동배정되어 변경 불가 — 배지 단계(stage)만 변경한다.
  updateMyTrack: (stage: number) =>
    api.put<MyTrack>("/challenges/my-track", { stage }),
  dailyChecklist: () => api.get<DailyChecklistResponse>("/challenges/daily-checklist"),
  toggleChecklist: (itemKey: string) =>
    api.post<DailyChecklistToggleResult>(`/challenges/daily-checklist/${itemKey}`, {}),
  listByTrackStage: (track: ChallengeTrack, stage: number) =>
    api.get<ChallengeListResponse>(`/challenges?track=${track}&stage=${stage}`),
  // ── 기존 유지 (참여·체크인·게이미피케이션) ──────────────────────────────
  myList: (limit = 100, offset = 0) =>
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
  calendar: (yearMonth?: string) =>
    api.get<MonthlyCalendarResponse>(`/challenges/calendar${yearMonth ? `?year_month=${yearMonth}` : ""}`),
};

// ── 감정 이모지 (기존 유지) ────────────────────────────────────────────────
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
