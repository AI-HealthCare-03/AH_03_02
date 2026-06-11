import { api } from "./client";

// 지표 정의 타입
export interface MetricDef {
  key: string;
  label: string;
  unit: string;
  decimals: number;
  range_low: number | null;
  range_high: number | null;
}

// 활성 지표 목록 응답
export interface MetricsResponse {
  active_keys: string[];
  active: MetricDef[];
  catalog: MetricDef[];
}

// 시계열 포인트
export interface LabPoint {
  date: string;
  value: number;
}

// 지표별 개요 (최근값·변화량·추세)
export interface MetricOverview {
  key: string;
  label: string;
  unit: string;
  decimals: number;
  latest: number | null;
  prev: number | null;
  delta: number | null;
  range_low: number | null;
  range_high: number | null;
  points: LabPoint[];
}

// 전체 개요 응답
export interface OverviewResponse {
  metrics: MetricOverview[];
  disclaimer: string;
}

// 저장 응답
export interface SaveLabResponse {
  measured_date: string;
  saved_keys: string[];
  auto_checkin: { performed: boolean; reason: string };
}

// 특정 날짜 기록 응답
export interface LabRecordResponse {
  measured_date: string | null;
  values: Record<string, number>;
  has_record: boolean;
}

// lab 검사 수치 API 클라이언트
export const labApi = {
  // 활성 지표 목록 조회
  getMetrics: () => api.get<MetricsResponse>("/records/lab/metrics"),

  // 활성 지표 목록 수정
  setMetrics: (metric_keys: string[]) =>
    api.put<MetricsResponse>("/records/lab/metrics", { metric_keys }),

  // 전체 지표 개요 조회 (최근값·추세·참고범위)
  getOverview: () => api.get<OverviewResponse>("/records/lab/overview"),

  // 특정 날짜 기록 조회
  getRecord: (date: string) =>
    api.get<LabRecordResponse>(`/records/lab?date=${date}`),

  // 검사 결과 저장 (날짜 + 지표값 맵)
  saveRecord: (measured_date: string, values: Record<string, number>) =>
    api.put<SaveLabResponse>("/records/lab", { measured_date, values }),

  // 특정 날짜 기록 삭제
  deleteRecord: (date: string) =>
    api.delete<LabRecordResponse>(`/records/lab?date=${date}`),
};
