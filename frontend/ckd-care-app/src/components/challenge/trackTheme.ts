import type { ChallengeTrack, ChallengeCategory } from "../../api/challenge";
import type { LucideIcon } from "lucide-react";
import {
  Droplets, UtensilsCrossed, Footprints, Moon, Brain,
  BookOpen, ClipboardList, Activity, HeartPulse,
} from "lucide-react";

export interface TrackTheme {
  label: string;        // 한글 트랙명 (백엔드 track_label 우선, fallback)
  emoji: string;        // 받은 디자인 아이콘
  color: string;        // 주색 토큰 클래스 조각 ("track-dialysis")
  bgClass: string;      // 배경 유틸
  textClass: string;    // 텍스트 유틸
  borderClass: string;  // 보더 유틸
  desc: string;         // 트랙 선택 카드 설명 (받은 디자인)
  badge: string;        // 배지 텍스트 (받은 디자인)
}

export const TRACK_THEME: Record<ChallengeTrack, TrackTheme> = {
  DIALYSIS: {
    label: "투석·이식 트랙", emoji: "💧", color: "track-dialysis",
    bgClass: "bg-track-dialysis-bg", textClass: "text-track-dialysis", borderClass: "border-track-dialysis",
    desc: "CKD 5단계 · eGFR < 15\n혈액투석 또는 복막투석 중", badge: "투석 중",
  },
  CKD: {
    label: "비투석 CKD 트랙", emoji: "🌿", color: "track-ckd",
    bgClass: "bg-track-ckd-bg", textClass: "text-track-ckd", borderClass: "border-track-ckd",
    desc: "CKD 진단, 투석 전 보존기\n진행을 늦추는 것이 목표", badge: "보존기 CKD",
  },
  INTENSIVE: {
    label: "집중케어 트랙", emoji: "🏥", color: "track-intensive",
    bgClass: "bg-track-intensive-bg", textClass: "text-track-intensive", borderClass: "border-track-intensive",
    desc: "신장 집중 관리군 (A그룹)\n스크리닝을 통해 배정된 분", badge: "A그룹",
  },
  DAILY: {
    label: "일상케어 트랙", emoji: "🌱", color: "track-daily",
    bgClass: "bg-track-daily-bg", textClass: "text-track-daily", borderClass: "border-track-daily",
    desc: "신장 위험·사전 관리군 (B·C그룹)\n생활 습관 개선 중심", badge: "B·C그룹",
  },
  WELLNESS: {
    label: "웰니스 트랙", emoji: "☀️", color: "track-wellness",
    bgClass: "bg-track-wellness-bg", textClass: "text-track-wellness", borderClass: "border-track-wellness",
    desc: "건강 습관 형성군 (D그룹)\n예방 중심 일반 건강 관리", badge: "D그룹",
  },
};

export const TRACK_ORDER: ChallengeTrack[] = ["DIALYSIS", "CKD", "INTENSIVE", "DAILY", "WELLNESS"];

// 스테이지 1~4 (백엔드 STAGE_LABEL과 일치)
export interface StageInfo { num: number; key: string; label: string; desc: string; }
export const STAGES: StageInfo[] = [
  { num: 1, key: "S1", label: "잔디 단계",   desc: "처음 시작하거나 기초를 다지는 단계" },
  { num: 2, key: "S2", label: "산스장 단계", desc: "기본 습관을 형성하고 강화하는 단계" },
  { num: 3, key: "S3", label: "헬스장 단계", desc: "목표를 높여 집중적으로 관리하는 단계" },
  { num: 4, key: "S4", label: "지옥도 단계", desc: "최고 강도의 자기 관리 도전 단계" },
];

// 카테고리 아이콘 (9종). 라벨은 백엔드 categories[].label 사용.
export const CATEGORY_ICON: Record<ChallengeCategory, LucideIcon> = {
  HYDRATION: Droplets, DIET: UtensilsCrossed, EXERCISE: Footprints, SLEEP: Moon, STRESS: Brain,
  EDUCATION: BookOpen, RECORD: ClipboardList, MONITORING: Activity, EMOTION: HeartPulse,
};

export const CATEGORY_LABEL_FALLBACK: Record<ChallengeCategory, string> = {
  HYDRATION: "수분", DIET: "식단", EXERCISE: "운동", SLEEP: "수면", STRESS: "스트레스",
  EDUCATION: "교육·이해", RECORD: "기록 습관", MONITORING: "검사·수치 관리", EMOTION: "정서",
};
