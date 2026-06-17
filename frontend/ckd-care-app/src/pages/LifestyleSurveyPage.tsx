import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { BtnPrimary } from "../components/BtnPrimary";
import {
  lifestyleSurveyApi,
  type SmokingStatus,
  type DrinkingFrequency,
  type StressLevel,
  type MaritalStatus,
  type DialysisType,
  type LifestyleSurveyResponse,
} from "../api/lifestyleSurvey";

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

// 운동 분처럼 범위가 넓은 값은 숫자 직접 입력
function NumberInput({ label, value, onChange, min = 0, max = 1440 }: {
  label: string; value: number; onChange: (v: number) => void; min?: number; max?: number;
}) {
  return (
    <div className="flex flex-col gap-[4px]">
      <label className="text-sm font-normal text-text-secondary">{label}</label>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") {
            onChange(min);
            return;
          }
          const n = Math.min(max, Math.max(min, Math.floor(parseFloat(raw))));
          onChange(isNaN(n) ? min : n);
        }}
        className="h-[40px] rounded-sm border border-border-strong bg-bg px-[12px] text-sm text-text-primary outline-none"
      />
    </div>
  );
}

function StepperInput({ label, value, onChange, min = 0, max = 7 }: {
  label: string; value: number; onChange: (v: number) => void; min?: number; max?: number;
}) {
  return (
    <div className="flex flex-col gap-[4px]">
      <label className="text-sm font-normal text-text-secondary">{label}</label>
      <div className="flex items-center gap-[12px]">
        <button
          type="button"
          onClick={() => onChange(Math.max(min, value - 1))}
          className="flex h-[36px] w-[36px] items-center justify-center rounded-sm border border-border-strong bg-bg text-lg"
        >−</button>
        <span className="w-[40px] text-center text-lg font-bold text-text-primary">{value}</span>
        <button
          type="button"
          onClick={() => onChange(Math.min(max, value + 1))}
          className="flex h-[36px] w-[36px] items-center justify-center rounded-sm border border-border-strong bg-bg text-lg"
        >+</button>
      </div>
    </div>
  );
}

export function LifestyleSurveyPage() {
  const navigate = useNavigate();
  const location = useLocation();
  // 문진 이력 "수정" 진입 시 기존 레코드(API 응답, snake_case)를 prefill로 전달받음 (Task 7)
  const prefill = (location.state as { prefill?: LifestyleSurveyResponse } | null)?.prefill;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [smoking, setSmoking] = useState<SmokingStatus | "">(prefill?.smoking_status ?? "");
  const [drinking, setDrinking] = useState<DrinkingFrequency | "">(prefill?.drinking_frequency ?? "");
  const [stress, setStress] = useState<StressLevel | "">(prefill?.stress_level ?? "");
  const [exerciseDays, setExerciseDays] = useState(prefill?.exercise_days_per_week ?? 0);
  const [sleepHours, setSleepHours] = useState(prefill?.sleep_hours_per_day ?? 7);
  const [waterIntake, setWaterIntake] = useState(prefill?.daily_water_intake ?? 1.5);
  // REQ-DATA-006 신규
  const [vigorousDays, setVigorousDays] = useState(prefill?.vigorous_exercise_days ?? 0);
  const [vigorousMinutes, setVigorousMinutes] = useState(prefill?.vigorous_exercise_minutes ?? 0);
  const [moderateDays, setModerateDays] = useState(prefill?.moderate_exercise_days ?? 0);
  const [moderateMinutes, setModerateMinutes] = useState(prefill?.moderate_exercise_minutes ?? 0);
  const [sittingHours, setSittingHours] = useState(prefill?.sitting_hours_per_day ?? 8);
  const [marital, setMarital] = useState<MaritalStatus | "">(prefill?.marital_status ?? "");
  const [famDiabetes, setFamDiabetes] = useState(prefill?.family_history_diabetes ?? false);
  const [famHypertension, setFamHypertension] = useState(prefill?.family_history_hypertension ?? false);
  const [famHeart, setFamHeart] = useState(prefill?.family_history_heart_disease ?? false);
  const [famDyslipidemia, setFamDyslipidemia] = useState(prefill?.family_history_dyslipidemia ?? false);
  const [famStroke, setFamStroke] = useState(prefill?.family_history_stroke ?? false);
  // 본인 진단력 (작업3)
  const [htnDiagnosed, setHtnDiagnosed] = useState(prefill?.htn_diagnosed ?? false);
  const [dmDiagnosed, setDmDiagnosed] = useState(prefill?.dm_diagnosed ?? false);
  const [dyslipidemiadiagnosed, setDyslipidemiadiagnosed] = useState(prefill?.dyslipidemia_diagnosed ?? false);
  const [ckdDiagnosed, setCkdDiagnosed] = useState(prefill?.ckd_diagnosed ?? false);
  const [dialysisType, setDialysisType] = useState<DialysisType>(prefill?.dialysis_type ?? "none");
  const [isPregnant, setIsPregnant] = useState(prefill?.is_pregnant ?? false);

  async function handleSubmit() {
    if (!smoking || !drinking) {
      setError("흡연 상태와 음주 빈도는 필수 항목입니다.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await lifestyleSurveyApi.create({
        surveyed_date: new Date().toISOString().slice(0, 10),
        smoking_status: smoking,
        drinking_frequency: drinking,
        exercise_days_per_week: exerciseDays,
        sleep_hours_per_day: sleepHours,
        daily_water_intake: waterIntake,
        stress_level: stress || null,
        vigorous_exercise_days: vigorousDays,
        vigorous_exercise_minutes: vigorousMinutes,
        moderate_exercise_days: moderateDays,
        moderate_exercise_minutes: moderateMinutes,
        sitting_hours_per_day: sittingHours,
        marital_status: marital || null,
        family_history_diabetes: famDiabetes,
        family_history_hypertension: famHypertension,
        family_history_heart_disease: famHeart,
        family_history_dyslipidemia: famDyslipidemia,
        family_history_stroke: famStroke,
        htn_diagnosed: htnDiagnosed,
        dm_diagnosed: dmDiagnosed,
        dyslipidemia_diagnosed: dyslipidemiadiagnosed,
        ckd_diagnosed: ckdDiagnosed,
        dialysis_type: ckdDiagnosed ? dialysisType : null,
        is_pregnant: isPregnant,
      });
      navigate("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="08 · 생활습관 설문 (REQ-DATA-04)" />
      <TopNav />
      <main className="flex flex-1 flex-col p-[32px]">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-[12px] flex w-fit items-center gap-[4px] rounded-md px-[10px] py-[6px] text-sm font-bold text-text-secondary hover:bg-bg"
        >
          <ChevronLeft size={18} />
          뒤로
        </button>
        <h1 className="text-2xl font-bold text-text-primary">생활습관 설문</h1>
        <p className="mt-[4px] text-sm text-text-secondary">오늘 기준 생활습관을 솔직하게 입력해주세요.</p>

        {error && (
          <div className="mt-4 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>
        )}

        <div className="mt-[24px] grid grid-cols-1 md:grid-cols-2 gap-[32px]">
          {/* 좌측 */}
          <div className="flex flex-col gap-[24px]">
            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">
                흡연·음주 <span className="text-danger text-xs">* 필수</span>
              </p>
              <div className="flex flex-col gap-[16px]">
                <SelectGroup<SmokingStatus>
                  label="흡연 상태"
                  value={smoking}
                  onChange={setSmoking}
                  options={[
                    { value: "NEVER", label: "비흡연" },
                    { value: "PAST", label: "과거 흡연" },
                    { value: "CURRENT", label: "현재 흡연" },
                  ]}
                />
                <SelectGroup<DrinkingFrequency>
                  label="음주 빈도"
                  value={drinking}
                  onChange={setDrinking}
                  options={[
                    { value: "NEVER", label: "안 마심" },
                    { value: "OCCASIONALLY", label: "가끔" },
                    { value: "WEEKLY", label: "주 1~2회" },
                    { value: "DAILY", label: "매일" },
                  ]}
                />
              </div>
            </div>

            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">스트레스</p>
              <SelectGroup<StressLevel>
                label="스트레스 수준"
                value={stress}
                onChange={setStress}
                options={[
                  { value: "VERY_LOW", label: "매우 낮음" },
                  { value: "LOW", label: "낮음" },
                  { value: "MODERATE", label: "보통" },
                  { value: "HIGH", label: "높음" },
                  { value: "VERY_HIGH", label: "매우 높음" },
                ]}
              />
            </div>
          </div>

          {/* 우측 */}
          <div className="flex flex-col gap-[24px]">
            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">신체활동</p>
              <div className="flex flex-col gap-[16px]">
                <StepperInput
                  label="주간 총 운동 일수 (일)"
                  value={exerciseDays}
                  onChange={setExerciseDays}
                  min={0}
                  max={7}
                />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-[12px]">
                  <StepperInput
                    label="고강도 운동 일수"
                    value={vigorousDays}
                    onChange={setVigorousDays}
                    min={0}
                    max={7}
                  />
                  <NumberInput
                    label="하루 평균 분"
                    value={vigorousMinutes}
                    onChange={setVigorousMinutes}
                    min={0}
                    max={1440}
                  />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-[12px]">
                  <StepperInput
                    label="중강도 운동 일수"
                    value={moderateDays}
                    onChange={setModerateDays}
                    min={0}
                    max={7}
                  />
                  <NumberInput
                    label="하루 평균 분"
                    value={moderateMinutes}
                    onChange={setModerateMinutes}
                    min={0}
                    max={1440}
                  />
                </div>
                <StepperInput
                  label="하루 좌식 시간 (시간)"
                  value={sittingHours}
                  onChange={setSittingHours}
                  min={0}
                  max={24}
                />
              </div>
            </div>

            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">결혼 여부</p>
              <SelectGroup<MaritalStatus>
                label="결혼 상태"
                value={marital}
                onChange={setMarital}
                options={[
                  { value: "SINGLE", label: "미혼" },
                  { value: "MARRIED", label: "기혼" },
                  { value: "DIVORCED", label: "이혼" },
                  { value: "WIDOWED", label: "사별" },
                  { value: "OTHER", label: "기타" },
                ]}
              />
            </div>

            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">가족력</p>
              <p className="mb-[8px] text-xs text-text-muted">
                직계가족 중 진단받은 적 있는 질환을 선택하세요.
                <br />
                <span className="text-info">선택하지 않을 경우 '없음'으로 자동 반영됩니다.</span>
              </p>
              <div className="flex flex-col gap-[8px]">
                <label className="flex items-center gap-[8px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={famDiabetes}
                    onChange={(e) => setFamDiabetes(e.target.checked)}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="text-sm text-text-primary">당뇨</span>
                </label>
                <label className="flex items-center gap-[8px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={famHypertension}
                    onChange={(e) => setFamHypertension(e.target.checked)}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="text-sm text-text-primary">고혈압</span>
                </label>
                <label className="flex items-center gap-[8px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={famHeart}
                    onChange={(e) => setFamHeart(e.target.checked)}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="text-sm text-text-primary">심장질환</span>
                </label>
                <label className="flex items-center gap-[8px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={famDyslipidemia}
                    onChange={(e) => setFamDyslipidemia(e.target.checked)}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="text-sm text-text-primary">이상지질혈증</span>
                </label>
                <label className="flex items-center gap-[8px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={famStroke}
                    onChange={(e) => setFamStroke(e.target.checked)}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="text-sm text-text-primary">뇌졸중</span>
                </label>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">본인 진단력</p>
              <p className="mb-[8px] text-xs text-text-muted">
                본인이 직접 진단받은 적 있는 질환을 선택하세요.
                <br />
                <span className="text-info">선택하지 않을 경우 '없음'으로 자동 반영됩니다.</span>
              </p>
              <div className="flex flex-col gap-[8px]">
                <label className="flex items-center gap-[8px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={htnDiagnosed}
                    onChange={(e) => setHtnDiagnosed(e.target.checked)}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="text-sm text-text-primary">고혈압 진단</span>
                </label>
                <label className="flex items-center gap-[8px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={dmDiagnosed}
                    onChange={(e) => setDmDiagnosed(e.target.checked)}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="text-sm text-text-primary">당뇨 진단</span>
                </label>
                <label className="flex items-center gap-[8px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={dyslipidemiadiagnosed}
                    onChange={(e) => setDyslipidemiadiagnosed(e.target.checked)}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="text-sm text-text-primary">이상지질혈증 진단</span>
                </label>
                <label className="flex items-center gap-[8px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={ckdDiagnosed}
                    onChange={(e) => setCkdDiagnosed(e.target.checked)}
                    className="h-4 w-4 accent-accent"
                  />
                  <span className="text-sm text-text-primary">만성콩팥병(CKD) 진단</span>
                </label>
                {ckdDiagnosed && (
                  <div className="mt-[8px] flex flex-col gap-[8px]">
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
                    <p className="text-xs text-danger">진단받으셨다면 주치의 지시를 우선하세요.</p>
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">임신 여부</p>
              <p className="mb-[8px] text-xs text-text-muted">
                임신 중에는 신장 수치 해석이 달라 별도 안전 안내가 표시됩니다. 해당될 때만 체크하세요.
              </p>
              <label className="flex items-center gap-[8px] cursor-pointer">
                <input
                  type="checkbox"
                  checked={isPregnant}
                  onChange={(e) => setIsPregnant(e.target.checked)}
                  className="h-4 w-4 accent-accent"
                />
                <span className="text-sm text-text-primary">현재 임신 중입니다</span>
              </label>
            </div>

            <div className="rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <p className="mb-[12px] text-md font-bold text-text-primary">수면·수분</p>
              <div className="flex flex-col gap-[16px]">
                <StepperInput
                  label={`하루 평균 수면 (${sleepHours}시간)`}
                  value={sleepHours}
                  onChange={setSleepHours}
                  min={0} max={24}
                />
                <div className="flex flex-col gap-[4px]">
                  <label className="text-sm font-normal text-text-secondary">
                    하루 수분 섭취량 ({waterIntake.toFixed(1)}L)
                  </label>
                  <input
                    type="range"
                    min={0} max={5} step={0.5}
                    value={waterIntake}
                    onChange={(e) => setWaterIntake(parseFloat(e.target.value))}
                    className="w-full accent-accent"
                    list="water-intake-ticks"
                  />
                  <datalist id="water-intake-ticks">
                    <option value="0" />
                    <option value="1" />
                    <option value="2" />
                    <option value="3" />
                    <option value="4" />
                    <option value="5" />
                  </datalist>
                  <div className="flex justify-between text-xs text-text-muted">
                    <span>0L</span><span>1L</span><span>2L</span><span>3L</span><span>4L</span><span>5L</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-[32px] flex justify-end">
          <BtnPrimary label="설문 완료" loading={loading} onClick={handleSubmit} />
        </div>
      </main>
    </div>
  );
}
