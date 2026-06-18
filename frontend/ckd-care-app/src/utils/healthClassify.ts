// 검진 수치 → 상태 분류 순수 함수 (저장 안 함, 프론트 실시간 표시 전용)
// 기준: 혈압 JNC7, 혈당 공복혈당, 헤모글로빈(성별) — 진단명 미사용, 서술어 반환

// 혈압상태 (수축기 sbp / 이완기 dbp)
export function bloodPressureStatus(sbp: number | null, dbp: number | null): string | null {
  if (sbp == null || dbp == null) return null;
  if (sbp >= 140 || dbp >= 90) return "위험";
  if (sbp >= 120 || dbp >= 80) return "주의";
  return "정상";
}

// 혈당상태 (공복혈당) — 정상 범위 70~99 mg/dL
export function glucoseStatus(glucose: number | null): string | null {
  if (glucose == null) return null;
  if (glucose >= 126) return "높음";
  if (glucose >= 100) return "경계";
  if (glucose < 70) return "저혈당";
  return "정상";
}

// 헤모글로빈 상태 (성별 — M1_STAGES 기준: 남 <13 낮음 / 13~16.5 정상 / ≥16.5 높음, 여 <12 / 12~16 / ≥16)
export function anemiaStatus(
  hb: number | null,
  gender: "MALE" | "FEMALE" | string | null,
): string | null {
  if (hb == null || gender == null) return null;
  const isMale = gender === "MALE";
  const lo = isMale ? 13 : 12;
  const hi = isMale ? 16.5 : 16;
  if (hb < lo) return "낮음";
  if (hb >= hi) return "높음";
  return "정상";
}
