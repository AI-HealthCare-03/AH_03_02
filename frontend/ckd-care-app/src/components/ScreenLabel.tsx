interface ScreenLabelProps {
  label: string;
  variant?: "default" | "danger";
}

// 개발용 화면 라벨(요구사항 ID 표시) — 프로덕션 노출 제거.
// 사용처(<ScreenLabel label=... />) 호출은 그대로 두되 아무것도 렌더하지 않는다.
export function ScreenLabel(_props: ScreenLabelProps) {
  return null;
}
