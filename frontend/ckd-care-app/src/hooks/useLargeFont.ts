import { useEffect, useState } from "react";

/**
 * 돋보기(큰글씨) 모드 — 60-70대 타겟 가독성 보조.
 *
 * localStorage에 토글 상태를 영구 저장. body class `large-font` 직접 부착해
 * index.css의 `body.large-font *` 선택자가 활성화되도록 한다.
 */
const STORAGE_KEY = "kiniq.large-font";

function getInitial(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(STORAGE_KEY) === "1";
}

export function useLargeFont() {
  const [enabled, setEnabled] = useState<boolean>(getInitial);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.body.classList.toggle("large-font", enabled);
    window.localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
  }, [enabled]);

  return { enabled, toggle: () => setEnabled((v) => !v) };
}
