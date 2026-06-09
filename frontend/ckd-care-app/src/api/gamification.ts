import { api } from "./client";

export type ItemCode =
  | "PROTECT"
  | "MINI_BOOSTER"
  | "SKIN_S_BLUE"
  | "SKIN_S_GREEN"
  | "SKIN_M_RED"
  | "SKIN_M_PURPLE"
  | "SKIN_L_GOLD"
  | "SKIN_TURTLE_1"
  | "SKIN_PENGUIN_1"
  | "SKIN_SQUIRREL_1"
  | "SKIN_RABBIT_1"
  | "SKIN_PANDA_1"
  | "SKIN_TURTLE_2"
  | "SKIN_PENGUIN_2"
  | "SKIN_SQUIRREL_2"
  | "SKIN_RABBIT_2"
  | "SKIN_PANDA_2"
  | "SKIN_TURTLE_3"
  | "SKIN_PENGUIN_3"
  | "SKIN_SQUIRREL_3"
  | "SKIN_RABBIT_3"
  | "SKIN_PANDA_3";

export type CharacterSpecies = "TURTLE" | "PENGUIN" | "SQUIRREL" | "RABBIT" | "PANDA";

// 동물 스킨 → 표시 종 매핑. 장착 시 EggWidget이 해당 종 일러스트로 override
export const ANIMAL_SKIN_TO_SPECIES: Partial<Record<ItemCode, CharacterSpecies>> = {
  SKIN_TURTLE_1: "TURTLE", SKIN_TURTLE_2: "TURTLE", SKIN_TURTLE_3: "TURTLE",
  SKIN_PENGUIN_1: "PENGUIN", SKIN_PENGUIN_2: "PENGUIN", SKIN_PENGUIN_3: "PENGUIN",
  SKIN_SQUIRREL_1: "SQUIRREL", SKIN_SQUIRREL_2: "SQUIRREL", SKIN_SQUIRREL_3: "SQUIRREL",
  SKIN_RABBIT_1: "RABBIT", SKIN_RABBIT_2: "RABBIT", SKIN_RABBIT_3: "RABBIT",
  SKIN_PANDA_1: "PANDA", SKIN_PANDA_2: "PANDA", SKIN_PANDA_3: "PANDA",
};

// 동물 스킨 → 표시 stage (1·2·3). 장착 시 EggWidget이 이 stage 일러스트 사용
export const ANIMAL_SKIN_TO_STAGE: Partial<Record<ItemCode, 1 | 2 | 3>> = {
  SKIN_TURTLE_1: 1, SKIN_PENGUIN_1: 1, SKIN_SQUIRREL_1: 1, SKIN_RABBIT_1: 1, SKIN_PANDA_1: 1,
  SKIN_TURTLE_2: 2, SKIN_PENGUIN_2: 2, SKIN_SQUIRREL_2: 2, SKIN_RABBIT_2: 2, SKIN_PANDA_2: 2,
  SKIN_TURTLE_3: 3, SKIN_PENGUIN_3: 3, SKIN_SQUIRREL_3: 3, SKIN_RABBIT_3: 3, SKIN_PANDA_3: 3,
};

export const SPECIES_EMOJI: Record<CharacterSpecies, string> = {
  TURTLE: "🐢",
  PENGUIN: "🐧",
  SQUIRREL: "🐿️",
  RABBIT: "🐰",
  PANDA: "🐼",
};

export const SPECIES_LABEL: Record<CharacterSpecies, string> = {
  TURTLE: "거북이",
  PENGUIN: "펭귄",
  SQUIRREL: "다람쥐",
  RABBIT: "토끼",
  PANDA: "판다",
};

// 일러스트 경로 매퍼 — public/characters/{종}_stage{1~3}.png 우선
// PNG가 없으면 img onError에서 SVG fallback, 그것도 없으면 이모지 fallback (CharacterImage.tsx)
export function characterImagePath(species: CharacterSpecies | null, stage: number): string | null {
  if (!species) {
    return stage === 0 ? "/characters/egg.png" : null;
  }
  const safeStage = Math.max(1, Math.min(stage, 3));
  const slug = species.toLowerCase();
  return `/characters/${slug}_stage${safeStage}.png`;
}

export type PointReason =
  | "LOGIN"
  | "CHECKIN"
  | "LUCKY"
  | "STREAK_BONUS"
  | "STAGE_BONUS"
  | "FULL_PARTICIPATION"
  | "PURCHASE"
  | "PROTECT_CONSUME"
  | "REFUND";

export interface EggResponse {
  egg_no: number;
  progress_checkins: number;
  current_stage: number;
  progress_percent: number;
  goal_70_alerted: boolean;
  goal_90_alerted: boolean;
  is_legendary: boolean | null;
  species: CharacterSpecies | null;
  character_name: string | null;
  started_at: string;
}

export interface EggHistoryItem {
  egg_no: number;
  is_legendary: boolean | null;
  species: CharacterSpecies | null;
  character_name: string | null;
  started_at: string;
  hatched_at: string;
}

export interface EggHistoryResponse {
  total: number;
  legendary_count: number;
  items: EggHistoryItem[];
}

export interface ChargeModeResponse {
  is_active: boolean;
  entered_at: string | null;
  exited_at: string | null;
  days_since_last_checkin: number | null;
  warning_4d_alerted: boolean;
  warning_5d_alerted: boolean;
  warning_6d_alerted: boolean;
}

export interface MascotResponse {
  current_egg: EggResponse;
  charge_mode: ChargeModeResponse;
  legendary_unlocked: boolean;
  skin_active: ItemCode | null;
  proficiency: number; // 1=입문, 2=초보, 3=중급, 4=숙련 — EggWidget 배경 결정
  max_stage_ever: number; // 누적 최고 진화 단계 (0~3) — 동물 스킨 잠금 판단
}

// 숙련도 배경 SVG 경로 (PNG 우선, 없으면 SVG fallback)
export function backgroundImagePath(proficiency: number): string {
  const safe = Math.max(1, Math.min(proficiency, 4));
  return `/backgrounds/bg_proficiency${safe}.svg`;
}

export const PROFICIENCY_LABEL: Record<number, string> = {
  1: "입문",
  2: "초보",
  3: "중급",
  4: "숙련",
};

export interface InventoryItem {
  item_code: ItemCode;
  quantity: number;
  acquired_at: string;
}

export interface InventoryResponse {
  total: number;
  items: InventoryItem[];
}

export interface PointBalanceResponse {
  balance: number;
  lifetime_earned: number;
  lifetime_spent: number;
}

export interface PointTransactionItem {
  id: number;
  amount: number;
  reason: PointReason;
  extra: Record<string, unknown>;
  created_at: string;
}

export interface PointTransactionListResponse {
  total: number;
  items: PointTransactionItem[];
}

export interface PurchaseResponse {
  item_code: ItemCode;
  new_quantity: number;
  spent: number;
  new_balance: number;
}

export const gamificationApi = {
  getCurrentEgg: () => api.get<EggResponse>("/gamification/eggs"),
  getEggHistory: () => api.get<EggHistoryResponse>("/gamification/eggs/history"),
  getMascot: () => api.get<MascotResponse>("/gamification/mascot"),
  getChargeMode: () => api.get<ChargeModeResponse>("/gamification/charge-mode"),
  exitChargeMode: () => api.post<ChargeModeResponse>("/gamification/charge-mode/exit", {}),
  getInventory: () => api.get<InventoryResponse>("/inventory"),
  renameCharacter: (eggId: number, name: string) =>
    api.patch<EggHistoryItem>(`/gamification/eggs/${eggId}/name`, { name }),
  equipSkin: (item_code: ItemCode | null) =>
    api.post<{ active_skin_code: ItemCode | null }>("/gamification/skin/equip", { item_code }),
};

export const SKIN_LABEL: Record<Exclude<ItemCode, "PROTECT" | "MINI_BOOSTER">, { name: string; color: string }> = {
  SKIN_S_BLUE: { name: "블루 스킨 (소)", color: "bg-blue-200" },
  SKIN_S_GREEN: { name: "그린 스킨 (소)", color: "bg-green-200" },
  SKIN_M_RED: { name: "레드 스킨 (중)", color: "bg-red-200" },
  SKIN_M_PURPLE: { name: "퍼플 스킨 (중)", color: "bg-purple-200" },
  SKIN_L_GOLD: { name: "골드 스킨 (대)", color: "bg-yellow-200" },
  SKIN_TURTLE_1: { name: "거북이 (1단계)", color: "bg-emerald-100" },
  SKIN_PENGUIN_1: { name: "펭귄 (1단계)", color: "bg-sky-100" },
  SKIN_SQUIRREL_1: { name: "다람쥐 (1단계)", color: "bg-orange-100" },
  SKIN_RABBIT_1: { name: "토끼 (1단계)", color: "bg-pink-100" },
  SKIN_PANDA_1: { name: "판다 (1단계)", color: "bg-slate-200" },
  SKIN_TURTLE_2: { name: "거북이 (2단계)", color: "bg-emerald-200" },
  SKIN_PENGUIN_2: { name: "펭귄 (2단계)", color: "bg-sky-200" },
  SKIN_SQUIRREL_2: { name: "다람쥐 (2단계)", color: "bg-orange-200" },
  SKIN_RABBIT_2: { name: "토끼 (2단계)", color: "bg-pink-200" },
  SKIN_PANDA_2: { name: "판다 (2단계)", color: "bg-slate-300" },
  SKIN_TURTLE_3: { name: "거북이 (완전체)", color: "bg-emerald-300" },
  SKIN_PENGUIN_3: { name: "펭귄 (완전체)", color: "bg-sky-300" },
  SKIN_SQUIRREL_3: { name: "다람쥐 (완전체)", color: "bg-orange-300" },
  SKIN_RABBIT_3: { name: "토끼 (완전체)", color: "bg-pink-300" },
  SKIN_PANDA_3: { name: "판다 (완전체)", color: "bg-slate-400" },
};

export interface AttendanceResponse {
  awarded: boolean;
  awarded_points: number;
  balance: number;
  message: string;
}

export const pointsApi = {
  getBalance: () => api.get<PointBalanceResponse>("/points/balance"),
  getTransactions: (limit = 20, offset = 0) =>
    api.get<PointTransactionListResponse>(`/points/transactions?limit=${limit}&offset=${offset}`),
  purchase: (item_code: ItemCode) =>
    api.post<PurchaseResponse>("/points/purchase", { item_code }),
  attendance: () => api.post<AttendanceResponse>("/attendance/check-in", {}),
};
