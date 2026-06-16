import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Copy, AlertTriangle, FileX, Sparkles } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { BtnPrimary } from "../components/BtnPrimary";
import { BtnSecondary } from "../components/BtnSecondary";
import type { OCRResponse, OCRMappedKey } from "../api/healthCheck";

const LOW_CONFIDENCE_THRESHOLD = 0.85;

// 매핑 필드 한국어 라벨 + 단위
const MAPPED_FIELD_LABEL: Record<OCRMappedKey, { label: string; unit: string }> = {
  height: { label: "신장", unit: "cm" },
  weight: { label: "체중", unit: "kg" },
  waist_circumference: { label: "허리둘레", unit: "cm" },
  systolic_bp: { label: "수축기 혈압", unit: "mmHg" },
  diastolic_bp: { label: "이완기 혈압", unit: "mmHg" },
  fasting_glucose: { label: "공복혈당", unit: "mg/dL" },
  creatinine: { label: "크레아티닌", unit: "mg/dL" },
  total_cholesterol: { label: "총콜레스테롤", unit: "mg/dL" },
  hdl_cholesterol: { label: "HDL 콜레스테롤", unit: "mg/dL" },
  triglycerides: { label: "중성지방", unit: "mg/dL" },
};

// 표시 순서 (검진 결과지 일반 순)
const MAPPED_FIELD_ORDER: OCRMappedKey[] = [
  "height", "weight", "waist_circumference",
  "systolic_bp", "diastolic_bp",
  "fasting_glucose", "creatinine",
  "total_cholesterol", "hdl_cholesterol", "triglycerides",
];

export function OCRResultPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const ocr: OCRResponse | undefined = (location.state as { ocr?: OCRResponse } | null)?.ocr;
  const [copied, setCopied] = useState(false);

  // OCR 응답 없이 직접 진입한 경우
  if (!ocr) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="06 · OCR 결과 (REQ-DATA-02)" />
        <TopNav />
        <main className="flex flex-1 flex-col items-center justify-center gap-[16px] p-[32px]">
          <FileX size={48} className="text-text-muted" />
          <p className="text-base font-bold text-text-primary">OCR 결과가 없습니다</p>
          <p className="text-sm text-text-secondary">먼저 검진 결과지를 업로드해주세요.</p>
          <BtnPrimary label="OCR 업로드로 이동" onClick={() => navigate("/ocr-upload")} />
        </main>
      </div>
    );
  }

  const fullText = ocr.fields.map((f) => f.text).join(" ");
  const mapped = ocr.mapped ?? {};
  const mappedKeys = MAPPED_FIELD_ORDER.filter((k) => mapped[k] != null);

  // ManualInputPage prefill 객체 구성 — value만 추출
  const prefill: Record<string, number> = {};
  for (const k of mappedKeys) {
    const f = mapped[k];
    if (f) prefill[k] = f.value;
  }

  async function copyAllToClipboard() {
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API 사용 불가
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="06 · OCR 결과 (REQ-DATA-02)" />
      <TopNav />
      <main className="flex flex-1 flex-col items-center p-[16px] md:p-[32px]">
        {/* 헤더 */}
        <div className="flex w-full max-w-[800px] flex-col gap-[8px] md:flex-row md:items-center md:justify-between md:gap-0">
          <h1 className="text-2xl font-bold text-text-primary">OCR 추출 결과</h1>
          <div className="flex flex-wrap items-center gap-[8px]">
            {mappedKeys.length > 0 && (
              <span className="flex items-center gap-[4px] rounded-sm bg-success/10 px-[10px] py-[4px] text-sm font-bold text-success">
                <Sparkles size={14} />
                자동 매핑 {mappedKeys.length}개
              </span>
            )}
            <span className="rounded-sm bg-info/10 px-[10px] py-[4px] text-sm font-bold text-info">
              항목 {ocr.fields.length}개
            </span>
            {ocr.low_confidence_count > 0 && (
              <span className="flex items-center gap-[4px] rounded-sm bg-warning/10 px-[10px] py-[4px] text-sm font-bold text-warning">
                <AlertTriangle size={14} />
                신뢰도 낮은 항목 {ocr.low_confidence_count}개
              </span>
            )}
          </div>
        </div>

        {/* 자동 매핑 카드 — 시연 핵심 */}
        {mappedKeys.length > 0 && (
          <div className="mt-[16px] w-full max-w-[800px] rounded-lg border border-accent bg-accent/5 p-[16px] shadow-card">
            <div className="mb-[10px] flex items-center gap-[6px]">
              <Sparkles size={16} className="text-accent" />
              <p className="text-sm font-bold text-text-primary">자동 매핑된 검진 수치</p>
              <span className="text-xs text-text-muted">— "검진 수치 직접 입력으로 이동" 시 자동 입력</span>
            </div>
            <div className="grid grid-cols-2 gap-[8px] md:grid-cols-3">
              {mappedKeys.map((k) => {
                const f = mapped[k]!;
                const meta = MAPPED_FIELD_LABEL[k];
                const low = f.confidence < LOW_CONFIDENCE_THRESHOLD;
                return (
                  <div key={k} className="rounded-sm bg-bg px-[10px] py-[8px]">
                    <p className="text-[11px] text-text-muted">{meta.label}</p>
                    <p className="mt-[2px] flex items-baseline gap-[4px]">
                      <span className="text-base font-bold text-text-primary">{f.value}</span>
                      <span className="text-[10px] text-text-muted">{meta.unit}</span>
                      <span className={`ml-auto text-[10px] font-bold ${low ? "text-warning" : "text-success"}`}>
                        {Math.round(f.confidence * 100)}%{low && " ⚠"}
                      </span>
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 안내 박스 */}
        <div className="mt-[16px] w-full max-w-[800px] rounded-sm border border-info bg-info/5 px-[16px] py-[12px] text-sm leading-[1.6] text-text-secondary">
          <p>
            아래 추출된 텍스트는 검진 수치 입력 화면에서 확인·보정할 수 있어요. 신뢰도 {(LOW_CONFIDENCE_THRESHOLD * 100).toFixed(0)}% 미만 항목은 ⚠ 표시로 강조됩니다.
          </p>
        </div>

        {ocr.fields.length === 0 ? (
          <div className="mt-[24px] flex w-full max-w-[800px] flex-col items-center gap-[8px] rounded-lg border border-dashed border-border bg-bg p-[40px] text-center shadow-card">
            <FileX size={32} className="text-text-muted" />
            <p className="text-sm text-text-secondary">
              이미지에서 텍스트를 추출하지 못했습니다. 더 선명한 이미지로 다시 시도해주세요.
            </p>
          </div>
        ) : (
          <>
            {/* 텍스트 표 */}
            <div className="mt-[16px] w-full max-w-[800px] overflow-hidden rounded-lg border border-border bg-bg shadow-card">
              <div className="grid grid-cols-[1fr_100px] gap-[12px] border-b border-border bg-bg-alt px-[16px] py-[10px]">
                <span className="text-xs font-bold text-text-secondary">추출된 텍스트</span>
                <span className="text-right text-xs font-bold text-text-secondary">신뢰도</span>
              </div>
              <div className="max-h-[360px] overflow-y-auto">
                {ocr.fields.map((f, idx) => {
                  const low = f.confidence < LOW_CONFIDENCE_THRESHOLD;
                  const pct = Math.round(f.confidence * 100);
                  return (
                    <div
                      key={idx}
                      className={`grid grid-cols-[1fr_100px] gap-[12px] border-b border-border px-[16px] py-[10px] last:border-b-0 ${
                        low ? "bg-warning/5" : ""
                      }`}
                    >
                      <span className="text-sm text-text-primary break-all">{f.text}</span>
                      <span className={`text-right text-sm font-bold ${low ? "text-warning" : "text-success"}`}>
                        {pct}%{low && " ⚠"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 전체 텍스트 복사 (보조 동작) */}
            <button
              onClick={copyAllToClipboard}
              className="mt-[12px] flex items-center gap-[6px] text-sm font-bold text-info hover:underline"
            >
              <Copy size={14} />
              {copied ? "복사 완료!" : "추출된 텍스트 전체 복사"}
            </button>
          </>
        )}

        {/* 하단 버튼 */}
        <div className="mt-[24px] flex w-full max-w-[800px] flex-col-reverse gap-[8px] md:flex-row md:justify-end">
          <BtnSecondary label="다시 업로드" onClick={() => navigate("/ocr-upload")} />
          <BtnPrimary
            label={mappedKeys.length > 0 ? `자동 입력 (${mappedKeys.length}개) + 직접 보정` : "검진 수치 직접 입력으로 이동"}
            onClick={() => navigate("/manual-input", { state: { ocrText: fullText, prefill } })}
          />
        </div>
      </main>
    </div>
  );
}
