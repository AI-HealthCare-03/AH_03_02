import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CloudUpload, Clock, FileImage, X, ChevronLeft } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { BtnPrimary } from "../components/BtnPrimary";
import { healthCheckApi } from "../api/healthCheck";

const ACCEPTED_MIME = ["image/jpeg", "image/jpg", "image/png", "application/pdf"];
const MAX_BYTES = 10 * 1024 * 1024; // 10MB

export function OCRUploadPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function pickFile(picked: File | undefined | null) {
    setError("");
    if (!picked) return;
    if (!ACCEPTED_MIME.includes(picked.type)) {
      setError("JPG, PNG, PDF 형식만 지원합니다.");
      return;
    }
    if (picked.size > MAX_BYTES) {
      setError("파일 크기는 최대 10MB까지 지원합니다.");
      return;
    }
    setFile(picked);
    // 이미지면 미리보기 (PDF는 미리보기 생략)
    if (picked.type.startsWith("image/")) {
      const url = URL.createObjectURL(picked);
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }
  }

  function clearFile() {
    setFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setError("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleUpload() {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const result = await healthCheckApi.ocrExtract(file);
      // 결과 페이지로 응답 데이터 전달
      navigate("/ocr-result", { state: { ocr: result } });
    } catch (e) {
      setError(e instanceof Error ? e.message : "OCR 처리에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="05 · OCR 업로드 (REQ-DATA-01)" />
      <TopNav />
      <main className="flex flex-1 flex-col items-center p-[32px]">
        <div className="mb-[12px] flex w-full max-w-[640px] justify-start">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="flex items-center gap-[4px] rounded-md px-[10px] py-[6px] text-sm font-bold text-text-secondary hover:bg-bg"
          >
            <ChevronLeft size={18} />
            뒤로
          </button>
        </div>
        <h1 className="text-2xl font-bold text-text-primary">건강검진 결과지 업로드</h1>
        <p className="mt-[8px] text-sm text-text-secondary">
          건강검진 결과지를 업로드하면 AI가 텍스트를 추출합니다. 추출된 항목은 수동 입력 화면에서 옮겨 적습니다.
        </p>

        {/* 드롭존 / 미리보기 */}
        <div
          className={`mt-[32px] flex w-[720px] flex-col items-center justify-center gap-[16px] rounded-lg border-2 border-dashed p-[24px] ${
            file ? "border-accent bg-bg" : "border-border-strong bg-bg"
          }`}
          style={{ minHeight: 280 }}
          onDragOver={(e) => {
            e.preventDefault();
          }}
          onDrop={(e) => {
            e.preventDefault();
            pickFile(e.dataTransfer.files?.[0]);
          }}
        >
          {!file ? (
            <>
              <CloudUpload size={48} className="text-text-muted" />
              <p className="text-sm text-text-secondary">파일을 드래그하거나 버튼으로 선택하세요</p>
              <BtnPrimary label="파일 선택" onClick={() => fileInputRef.current?.click()} />
              <p className="text-xs text-text-muted">JPG, PNG, PDF · 최대 10MB</p>
            </>
          ) : (
            <>
              <div className="flex w-full items-center justify-between rounded-md bg-bg-alt px-[16px] py-[12px]">
                <div className="flex items-center gap-[12px]">
                  <FileImage size={24} className="text-accent" />
                  <div>
                    <p className="text-sm font-bold text-text-primary">{file.name}</p>
                    <p className="text-xs text-text-muted">
                      {(file.size / 1024).toFixed(1)} KB · {file.type}
                    </p>
                  </div>
                </div>
                <button
                  onClick={clearFile}
                  className="rounded-full p-[6px] text-text-muted hover:bg-bg hover:text-danger"
                  aria-label="파일 제거"
                  disabled={loading}
                >
                  <X size={18} />
                </button>
              </div>
              {previewUrl && (
                <img
                  src={previewUrl}
                  alt="미리보기"
                  className="max-h-[280px] max-w-full rounded-md border border-border object-contain"
                />
              )}
            </>
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_MIME.join(",")}
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0])}
        />

        {/* 업로드 버튼 */}
        {file && (
          <BtnPrimary
            label={loading ? "AI가 텍스트 추출 중... (5~30초)" : "OCR 분석 시작"}
            onClick={handleUpload}
            loading={loading}
            className="mt-[24px] w-[720px]"
            height={48}
          />
        )}

        {/* 에러 메시지 */}
        {error && (
          <div className="mt-[16px] w-[720px] rounded-lg border border-danger bg-danger/5 px-[16px] py-[12px] text-sm text-danger shadow-card">
            {error}
          </div>
        )}

        {/* 정보 박스 */}
        <div className="mt-[24px] flex w-[720px] flex-col gap-[12px]">
          <div className="flex items-center gap-[8px]">
            <Clock size={16} className="shrink-0 text-text-secondary" />
            <p className="text-sm text-text-secondary">처리 시간: 약 5~30초</p>
          </div>
        </div>

      </main>
    </div>
  );
}
