import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Copy, AlertTriangle, FileX } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { BtnPrimary } from "../components/BtnPrimary";
import { BtnSecondary } from "../components/BtnSecondary";
import type { OCRResponse } from "../api/healthCheck";

const LOW_CONFIDENCE_THRESHOLD = 0.85;

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

  async function copyAllToClipboard() {
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API 사용 불가 (insecure context 등)
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

        {/* 안내 박스 */}
        <div className="mt-[16px] w-full max-w-[800px] rounded-sm border border-info bg-info/5 px-[16px] py-[12px] text-sm leading-[1.6] text-text-secondary">
          <p>
            추출된 텍스트를 보고 <span className="font-bold text-text-primary">검진 수치 직접 입력</span> 화면에 옮겨 적으세요.
            신뢰도 {(LOW_CONFIDENCE_THRESHOLD * 100).toFixed(0)}% 미만 항목은 ⚠ 표시로 강조됩니다.
          </p>
        </div>

        {ocr.fields.length === 0 ? (
          <div className="mt-[24px] flex w-full max-w-[800px] flex-col items-center gap-[8px] rounded-md border border-dashed border-border bg-bg p-[40px] text-center">
            <FileX size={32} className="text-text-muted" />
            <p className="text-sm text-text-secondary">
              이미지에서 텍스트를 추출하지 못했습니다. 더 선명한 이미지로 다시 시도해주세요.
            </p>
          </div>
        ) : (
          <>
            {/* 텍스트 표 */}
            <div className="mt-[16px] w-full max-w-[800px] overflow-hidden rounded-md border border-border bg-bg">
              <div className="grid grid-cols-[1fr_100px] gap-[12px] border-b border-border bg-bg-alt px-[16px] py-[10px]">
                <span className="text-xs font-bold text-text-secondary">추출된 텍스트</span>
                <span className="text-right text-xs font-bold text-text-secondary">신뢰도</span>
              </div>
              <div className="max-h-[480px] overflow-y-auto">
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
            label="검진 수치 직접 입력으로 이동"
            onClick={() => navigate("/manual-input", { state: { ocrText: fullText } })}
          />
        </div>
      </main>
    </div>
  );
}
