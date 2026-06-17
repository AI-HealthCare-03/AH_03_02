import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "../api/dashboard";
import { useAuth } from "../contexts/AuthContext";

/**
 * CKD 진단 여부 훅.
 *
 * 대시보드 summary(queryKey: ["dashboard-summary"]) 캐시를 공유하므로,
 * 네비게이션·리포트 페이지에서 호출해도 추가 네트워크 요청이 발생하지 않는다.
 *
 * - diagnosed: 진단자 여부 (latest_lifestyle.ckd_diagnosed)
 *   진단자는 의료 영역으로 예측·리포트 비대상 → 리포트 탭/페이지 노출 제외.
 * - isLoading: summary 로딩 중 (분기 깜빡임·오판 방지용)
 */
export function useDiagnosed() {
  const { token } = useAuth();
  const { data: summary, isLoading } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: dashboardApi.getSummary,
    enabled: !!token,
  });
  return {
    diagnosed: !!summary?.latest_lifestyle?.ckd_diagnosed,
    isLoading,
  };
}
