import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import type { HealthCheckResponse, DialysisType } from "../api/healthCheck";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { TextInput } from "../components/TextInput";
import { BtnPrimary } from "../components/BtnPrimary";
import { BtnSecondary } from "../components/BtnSecondary";
import { healthCheckApi } from "../api/healthCheck";

// 예/아니오 또는 선택 옵션 버튼 그룹 (LifestyleSurveyPage의 SelectGroup 패턴 동일)
function SelectGroup<T extends string>({
  label, options, value, onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T | "";
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-col gap-[4px]">
      <label className="text-sm font-normal text-text-secondary">{label}</label>
      <div className="flex gap-[8px]">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            className={`flex-1 rounded-sm border px-[12px] py-[8px] text-sm ${
              value === o.value
                ? "border-accent bg-accent font-bold text-bg"
                : "border-border-strong bg-bg font-normal text-text-primary"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function toNum(v: string): number | null {
  const n = parseFloat(v);
  return isNaN(n) ? null : n;
}

function calcBmi(height: string, weight: string): string {
  const h = parseFloat(height);
  const w = parseFloat(weight);
  if (!h || !w) return "";
  return (w / Math.pow(h / 100, 2)).toFixed(1);
}

export function ManualInputPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const prefill = (location.state as { prefill?: HealthCheckResponse } | null)?.prefill;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");

  // CKD 진단 게이트 및 투석 종류 (재입력 시 prefill 값으로 초기화)
  const [ckdDiagnosed, setCkdDiagnosed] = useState<"yes" | "no" | "">(
    prefill?.dialysis_type != null ? "yes" : ""
  );
  const [dialysisType, setDialysisType] = useState<DialysisType>(
    prefill?.dialysis_type ?? "none"
  );

  const [form, setForm] = useState({
    checked_date: prefill?.checked_date ?? new Date().toISOString().slice(0, 10),
    height: prefill?.height != null ? String(prefill.height) : "",
    weight: prefill?.weight != null ? String(prefill.weight) : "",
    waist: prefill?.waist_circumference != null ? String(prefill.waist_circumference) : "",
    systolic_bp: prefill?.systolic_bp != null ? String(prefill.systolic_bp) : "",
    diastolic_bp: prefill?.diastolic_bp != null ? String(prefill.diastolic_bp) : "",
    creatinine: prefill?.creatinine != null ? String(prefill.creatinine) : "",
    fasting_glucose: prefill?.fasting_glucose != null ? String(prefill.fasting_glucose) : "",
    triglycerides: prefill?.triglycerides != null ? String(prefill.triglycerides) : "",
    hdl: prefill?.hdl_cholesterol != null ? String(prefill.hdl_cholesterol) : "",
    total_cholesterol: prefill?.total_cholesterol != null ? String(prefill.total_cholesterol) : "",
  });

  function set(field: string) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
  }

  const bmi = calcBmi(form.height, form.weight);

  async function handleSave() {
    const required = ["checked_date", "height", "weight", "systolic_bp", "diastolic_bp", "fasting_glucose"];
    for (const f of required) {
      if (!form[f as keyof typeof form]) {
        setError("필수 항목(검진일·신장·체중·혈압·공복혈당)을 입력해주세요."); return;
      }
    }
    const h = parseFloat(form.height), w = parseFloat(form.weight);
    if (isNaN(h) || h < 100 || h > 250) { setError("신장은 100~250 cm 범위로 입력해주세요."); return; }
    if (isNaN(w) || w < 20 || w > 300) { setError("체중은 20~300 kg 범위로 입력해주세요."); return; }
    if (form.waist) {
      const wc = parseFloat(form.waist);
      if (isNaN(wc) || wc < 40 || wc > 200) { setError("허리둘레는 40~200 cm 범위로 입력해주세요."); return; }
    }
    const sbp = parseInt(form.systolic_bp), dbp = parseInt(form.diastolic_bp);
    if (isNaN(sbp) || sbp < 60 || sbp > 250) { setError("수축기 혈압은 60~250 mmHg 범위로 입력해주세요."); return; }
    if (isNaN(dbp) || dbp < 40 || dbp > 150) { setError("이완기 혈압은 40~150 mmHg 범위로 입력해주세요."); return; }
    const fg = parseFloat(form.fasting_glucose);
    if (isNaN(fg) || fg < 50 || fg > 700) { setError("공복혈당은 50~700 mg/dL 범위로 입력해주세요."); return; }
    if (form.creatinine) {
      const cr = parseFloat(form.creatinine);
      if (isNaN(cr) || cr < 0.1 || cr > 30) { setError("크레아티닌은 0.1~30 mg/dL 범위로 입력해주세요."); return; }
    }
    setError(""); setWarning("");
    setLoading(true);
    try {
      const res = await healthCheckApi.create({
        checked_date: form.checked_date,
        height: parseFloat(form.height),
        weight: parseFloat(form.weight),
        waist_circumference: toNum(form.waist),
        systolic_bp: parseInt(form.systolic_bp),
        diastolic_bp: parseInt(form.diastolic_bp),
        creatinine: toNum(form.creatinine),
        fasting_glucose: parseFloat(form.fasting_glucose),
        triglycerides: toNum(form.triglycerides),
        hdl_cholesterol: toNum(form.hdl),
        total_cholesterol: toNum(form.total_cholesterol),
        // CKD 진단 시에만 투석 종류 전송, 미진단이면 null
        dialysis_type: ckdDiagnosed === "yes" ? dialysisType : null,
      });
      if (res.safety_warning) {
        setWarning(res.safety_warning);
      } else {
        navigate("/dashboard");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="07 · 수동 입력 (REQ-DATA-03)" />
      <TopNav />
      <main className="flex flex-1 flex-col p-[32px]">

        {/* 안전 경고 (Safety Guard) */}
        {warning && (
          <div className="mb-4 rounded-md border-2 border-danger bg-danger/10 p-[16px]">
            <p className="text-sm font-bold text-danger">⚠ 주의</p>
            <p className="mt-1 text-sm text-danger">{warning}</p>
            <button
              onClick={() => navigate("/dashboard")}
              className="mt-3 text-sm font-bold text-info underline"
            >
              대시보드로 이동
            </button>
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>
        )}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="text-2xl font-bold text-text-primary">
            {prefill ? "건강검진 수치 재입력" : "건강검진 수치 입력"}
          </h1>
          <TextInput
            label="검진일"
            placeholder="YYYY-MM-DD"
            className="w-full sm:w-[200px]"
            value={form.checked_date}
            onChange={set("checked_date")}
          />
        </div>

        <div className="mt-[24px] grid grid-cols-1 md:grid-cols-2 gap-[32px]">
          {/* 좌측 */}
          <div className="flex flex-col gap-[24px]">
            <div className="rounded-md border border-border bg-bg p-[16px]">
              <p className="mb-[12px] text-md font-bold text-text-primary">신체계측 <span className="text-danger text-xs">* 필수</span></p>
              <div className="flex flex-col gap-[12px]">
                <TextInput label="신장 (cm)" placeholder="170.0" value={form.height} onChange={set("height")} />
                <TextInput label="체중 (kg)" placeholder="72.5" value={form.weight} onChange={set("weight")} />
                <div className="flex flex-col gap-[4px]">
                  <label className="text-sm font-normal text-text-secondary">BMI (kg/m²)</label>
                  <div className="flex h-[40px] items-center rounded-sm border border-border bg-bg-alt px-[12px]">
                    <span className="text-sm text-text-muted">{bmi || "신장·체중 입력 시 자동 계산"}</span>
                  </div>
                </div>
                <TextInput label="허리둘레 (cm)" placeholder="85.0" value={form.waist} onChange={set("waist")} />
              </div>
            </div>

            <div className="rounded-md border border-border bg-bg p-[16px]">
              <p className="mb-[12px] text-md font-bold text-text-primary">혈압 <span className="text-danger text-xs">* 필수</span></p>
              <div className="flex flex-col gap-[12px]">
                <TextInput label="수축기 혈압 SBP (mmHg)" placeholder="120" value={form.systolic_bp} onChange={set("systolic_bp")} />
                <TextInput label="이완기 혈압 DBP (mmHg)" placeholder="80" value={form.diastolic_bp} onChange={set("diastolic_bp")} />
              </div>
            </div>

            <div className="rounded-md border border-danger bg-bg p-[16px]">
              <p className="mb-[12px] text-md font-bold text-danger">CKD 마커</p>
              <div className="flex flex-col gap-[12px]">
                <TextInput label="크레아티닌 (mg/dL)" placeholder="1.0" value={form.creatinine} onChange={set("creatinine")} />
                <p className="text-xs text-text-muted">입력 시 CKD-EPI 공식으로 eGFR 자동 계산</p>
              </div>
            </div>

            {/* CKD 진단 여부 게이트 및 투석 종류 */}
            <div className="rounded-md border border-border bg-bg p-[16px]">
              <p className="mb-[12px] text-md font-bold text-text-primary">CKD 진단 여부</p>
              <div className="flex flex-col gap-[16px]">
                <SelectGroup<"yes" | "no">
                  label="CKD 진단을 받으셨나요?"
                  value={ckdDiagnosed}
                  onChange={setCkdDiagnosed}
                  options={[
                    { value: "yes", label: "예" },
                    { value: "no", label: "아니오" },
                  ]}
                />
                {ckdDiagnosed === "yes" && (
                  <SelectGroup<DialysisType>
                    label="투석 종류"
                    value={dialysisType}
                    onChange={setDialysisType}
                    options={[
                      { value: "none", label: "투석 안 함" },
                      { value: "hemodialysis", label: "혈액투석" },
                      { value: "peritoneal", label: "복막투석" },
                      { value: "transplant", label: "이식" },
                    ]}
                  />
                )}
                {ckdDiagnosed === "yes" && (
                  <p className="text-xs text-danger">진단받으셨다면 주치의 지시를 우선하세요.</p>
                )}
              </div>
            </div>
          </div>

          {/* 우측 */}
          <div className="flex flex-col gap-[24px]">
            <div className="rounded-md border border-border bg-bg p-[16px]">
              <p className="mb-[12px] text-md font-bold text-text-primary">혈액검사 <span className="text-danger text-xs">* 공복혈당 필수</span></p>
              <div className="flex flex-col gap-[12px]">
                <TextInput label="공복혈당 (mg/dL)" placeholder="100" value={form.fasting_glucose} onChange={set("fasting_glucose")} />
                <TextInput label="중성지방 (mg/dL)" placeholder="150" value={form.triglycerides} onChange={set("triglycerides")} />
                <TextInput label="HDL 콜레스테롤 (mg/dL)" placeholder="60" value={form.hdl} onChange={set("hdl")} />
                <TextInput label="총 콜레스테롤 (mg/dL)" placeholder="180" value={form.total_cholesterol} onChange={set("total_cholesterol")} />
              </div>
            </div>

            <div className="rounded-sm bg-bg-alt p-[12px]">
              <p className="text-xs text-text-secondary">
                입력하신 수치는 CKD 위험도 예측 모델에 활용됩니다. 가능한 최근 건강검진 결과를 정확히 입력해주세요.
              </p>
            </div>
          </div>
        </div>

        <div className="mt-[32px] flex justify-end gap-[12px]">
          <BtnSecondary label="취소" onClick={() => navigate(-1)} />
          <BtnPrimary label="저장" loading={loading} onClick={handleSave} />
        </div>
      </main>
    </div>
  );
}
