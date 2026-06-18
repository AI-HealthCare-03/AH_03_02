import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { AlertTriangle, ChevronLeft } from "lucide-react";
import type { HealthCheckResponse, UrineResult } from "../api/healthCheck";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { TextInput } from "../components/TextInput";
import { BtnPrimary } from "../components/BtnPrimary";
import { BtnSecondary } from "../components/BtnSecondary";
import { healthCheckApi } from "../api/healthCheck";
import { useAuth } from "../contexts/AuthContext";
import { bloodPressureStatus, glucoseStatus, anemiaStatus } from "../utils/healthClassify";

function toNum(v: string): number | null {
  const n = parseFloat(v);
  return isNaN(n) ? null : n;
}

// 분류 상태 → 배지 색상 (정상=success, 주의/경계=warning, 위험/높음/낮음/저혈당=danger)
function statusTone(status: string): string {
  if (status === "정상") return "border-success text-success";
  if (status === "위험" || status === "높음" || status === "낮음" || status === "저혈당") return "border-danger text-danger";
  return "border-warning text-warning"; // 주의, 경계
}

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return null;
  return (
    <span
      className={`mt-[6px] inline-flex w-fit items-center rounded-sm border px-[8px] py-[2px] text-xs font-bold ${statusTone(status)}`}
    >
      {status}
    </span>
  );
}

// 요검사 양성/음성 토글
function UrineToggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: UrineResult | "";
  onChange: (v: UrineResult) => void;
}) {
  const opts: { value: UrineResult; label: string }[] = [
    { value: "NEGATIVE", label: "음성(정상)" },
    { value: "POSITIVE", label: "양성(의심)" },
  ];
  return (
    <div className="flex flex-col gap-[4px]">
      <label className="text-sm font-normal text-text-secondary">{label}</label>
      <div className="flex gap-[8px]">
        {opts.map((o) => (
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

function calcBmi(height: string, weight: string): string {
  const h = parseFloat(height);
  const w = parseFloat(weight);
  if (!h || !w) return "";
  return (w / Math.pow(h / 100, 2)).toFixed(1);
}

export function ManualInputPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  // prefill에 isEdit=true 플래그가 있으면 update 모드 (CheckupHistoryPage 수정 진입)
  const navState = location.state as { prefill?: HealthCheckResponse; isEdit?: boolean } | null;
  const prefill = navState?.prefill;
  const isEditMode = Boolean(navState?.isEdit && prefill?.id);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");

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
    // 신규 검진 수치 항목
    ldl: prefill?.ldl_cholesterol != null ? String(prefill.ldl_cholesterol) : "",
    hemoglobin: prefill?.hemoglobin != null ? String(prefill.hemoglobin) : "",
    ast: prefill?.ast != null ? String(prefill.ast) : "",
    alt: prefill?.alt != null ? String(prefill.alt) : "",
  });
  // 요검사(양성/음성)는 별도 state
  const [urineProtein, setUrineProtein] = useState<UrineResult | "">(prefill?.urine_protein ?? "");
  const [urineGlucose, setUrineGlucose] = useState<UrineResult | "">(prefill?.urine_glucose ?? "");

  function set(field: string) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
  }

  const bmi = calcBmi(form.height, form.weight);

  // 실시간 분류 (저장 안 함 — 입력값으로 즉시 계산)
  const bpStatus = bloodPressureStatus(toNum(form.systolic_bp), toNum(form.diastolic_bp));
  const fgStatus = glucoseStatus(toNum(form.fasting_glucose));
  const hbStatus = anemiaStatus(toNum(form.hemoglobin), user?.gender ?? null);

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
    if (form.triglycerides) {
      const tg = parseFloat(form.triglycerides);
      if (isNaN(tg) || tg < 10 || tg > 5000) { setError("중성지방은 10~5000 mg/dL 범위로 입력해주세요."); return; }
    }
    if (form.hdl) {
      const hdl = parseFloat(form.hdl);
      if (isNaN(hdl) || hdl < 5 || hdl > 150) { setError("HDL은 5~150 mg/dL 범위로 입력해주세요."); return; }
    }
    if (form.ldl) {
      const ldl = parseFloat(form.ldl);
      if (isNaN(ldl) || ldl < 10 || ldl > 500) { setError("LDL은 10~500 mg/dL 범위로 입력해주세요."); return; }
    }
    if (form.total_cholesterol) {
      const tc = parseFloat(form.total_cholesterol);
      if (isNaN(tc) || tc < 50 || tc > 800) { setError("총 콜레스테롤은 50~800 mg/dL 범위로 입력해주세요."); return; }
    }
    if (form.hemoglobin) {
      const hb = parseFloat(form.hemoglobin);
      if (isNaN(hb) || hb < 3 || hb > 25) { setError("헤모글로빈은 3~25 g/dL 범위로 입력해주세요."); return; }
    }
    if (form.ast) {
      const ast = parseFloat(form.ast);
      if (isNaN(ast) || ast < 1 || ast > 5000) { setError("AST는 1~5000 U/L 범위로 입력해주세요."); return; }
    }
    if (form.alt) {
      const alt = parseFloat(form.alt);
      if (isNaN(alt) || alt < 1 || alt > 5000) { setError("ALT는 1~5000 U/L 범위로 입력해주세요."); return; }
    }
    setError(""); setWarning("");
    setLoading(true);
    try {
      const payload = {
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
        ldl_cholesterol: toNum(form.ldl),
        hemoglobin: toNum(form.hemoglobin),
        ast: toNum(form.ast),
        alt: toNum(form.alt),
        urine_protein: urineProtein || null,
        urine_glucose: urineGlucose || null,
      };
      const res = isEditMode && prefill?.id
        ? await healthCheckApi.update(prefill.id, payload)
        : await healthCheckApi.create(payload);
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
          <div className="mb-4 rounded-lg border-2 border-danger bg-danger/10 p-[16px] shadow-card">
            <p className="flex items-center gap-[6px] text-sm font-bold text-danger">
              <AlertTriangle size={16} />
              주의
            </p>
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

        <button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-[12px] flex w-fit items-center gap-[4px] rounded-md px-[10px] py-[6px] text-sm font-bold text-text-secondary hover:bg-bg"
        >
          <ChevronLeft size={18} />
          뒤로
        </button>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="text-2xl font-bold text-text-primary">
            {isEditMode ? "건강검진 수치 수정" : prefill ? "건강검진 수치 재입력" : "건강검진 수치 입력"}
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
            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
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

            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">혈압 <span className="text-danger text-xs">* 필수</span></p>
              <div className="flex flex-col gap-[12px]">
                <TextInput label="수축기 혈압 SBP (mmHg)" placeholder="120" value={form.systolic_bp} onChange={set("systolic_bp")} />
                <TextInput label="이완기 혈압 DBP (mmHg)" placeholder="80" value={form.diastolic_bp} onChange={set("diastolic_bp")} />
                {bpStatus && (
                  <div className="flex flex-col">
                    <span className="text-xs text-text-muted">혈압 상태</span>
                    <StatusBadge status={bpStatus} />
                    {bpStatus === "위험" && (
                      <p className="mt-[4px] text-xs text-text-muted">고혈압 범위 · 확진 아님 · 의료기관 상담</p>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-danger bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-danger">CKD 마커</p>
              <div className="flex flex-col gap-[12px]">
                <TextInput label="크레아티닌 (mg/dL)" placeholder="1.0" value={form.creatinine} onChange={set("creatinine")} />
                <p className="text-xs text-text-muted">입력 시 CKD-EPI 공식으로 eGFR 자동 계산</p>
              </div>
            </div>

          </div>

          {/* 우측 */}
          <div className="flex flex-col gap-[24px]">
            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">혈액검사 <span className="text-danger text-xs">* 공복혈당 필수</span></p>
              <div className="flex flex-col gap-[12px]">
                <TextInput label="공복혈당 (mg/dL)" placeholder="100" value={form.fasting_glucose} onChange={set("fasting_glucose")} />
                {fgStatus && (
                  <div className="flex flex-col">
                    <span className="text-xs text-text-muted">혈당 상태</span>
                    <StatusBadge status={fgStatus} />
                    {fgStatus === "높음" && (
                      <p className="mt-[4px] text-xs text-text-muted">당뇨 범위 · 확진 아님 · 의료기관 상담 권장</p>
                    )}
                    {fgStatus === "저혈당" && (
                      <p className="mt-[4px] text-xs text-text-muted">저혈당 의심 · 즉시 의료기관 상담 권장</p>
                    )}
                  </div>
                )}
                <TextInput label="중성지방 (mg/dL)" placeholder="150" value={form.triglycerides} onChange={set("triglycerides")} />
                <TextInput label="HDL 콜레스테롤 (mg/dL)" placeholder="60" value={form.hdl} onChange={set("hdl")} />
                <TextInput label="LDL 콜레스테롤 (mg/dL)" placeholder="100" value={form.ldl} onChange={set("ldl")} />
                <TextInput label="총 콜레스테롤 (mg/dL)" placeholder="180" value={form.total_cholesterol} onChange={set("total_cholesterol")} />
                <TextInput label="헤모글로빈 (g/dL)" placeholder="14" value={form.hemoglobin} onChange={set("hemoglobin")} />
                {hbStatus && (
                  <div className="flex flex-col">
                    <span className="text-xs text-text-muted">헤모글로빈 상태</span>
                    <StatusBadge status={hbStatus} />
                    {hbStatus === "낮음" && (
                      <p className="mt-[4px] text-xs text-text-muted">빈혈 의심 · 의료기관 상담</p>
                    )}
                    {hbStatus === "높음" && (
                      <p className="mt-[4px] text-xs text-text-muted">헤모글로빈 높음 · 의료기관 상담</p>
                    )}
                  </div>
                )}
                <TextInput label="AST (U/L)" placeholder="25" value={form.ast} onChange={set("ast")} />
                <TextInput label="ALT (U/L)" placeholder="22" value={form.alt} onChange={set("alt")} />
              </div>
            </div>

            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">요검사</p>
              <p className="mb-[8px] text-xs text-text-muted">요단백·요당은 양성/음성으로 입력하세요.</p>
              <div className="flex flex-col gap-[16px]">
                <UrineToggle label="요단백" value={urineProtein} onChange={setUrineProtein} />
                <UrineToggle label="요당" value={urineGlucose} onChange={setUrineGlucose} />
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
