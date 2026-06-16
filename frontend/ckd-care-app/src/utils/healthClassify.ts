// 검진 수치 → 상태 분류 순수 함수 (저장 안 함, 프론트 실시간 표시 전용)
// 기준: 혈압 JNC7, 혈당 공복혈당, 빈혈 헤모글로빈(성별)

// 혈압상태 (수축기 sbp / 이완기 dbp)
export function bloodPressureStatus(sbp: number | null, dbp: number | null): string | null {
  if (sbp == null || dbp == null) return null;
  if (sbp >= 140 || dbp >= 90) return "고혈압";
  if (sbp >= 120 || dbp >= 80) return "고혈압 전단계";
  return "정상";
}

// 혈당상태 (공복혈당)
export function glucoseStatus(glucose: number | null): string | null {
  if (glucose == null) return null;
  if (glucose >= 126) return "당뇨";
  if (glucose >= 100) return "공복혈당장애";
  return "정상";
}

// 빈혈여부 (헤모글로빈 + 성별: 남 <13, 여 <12)
export function anemiaStatus(
  hb: number | null,
  gender: "MALE" | "FEMALE" | string | null,
): string | null {
  if (hb == null || gender == null) return null;
  const threshold = gender === "MALE" ? 13 : 12;
  return hb < threshold ? "빈혈" : "정상";
}
