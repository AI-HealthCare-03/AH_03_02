import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Soup, Coffee, Pizza, Leaf, Apple, Beef } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { Tag } from "../components/Tag";
import { BtnPrimary } from "../components/BtnPrimary";
import { dietSurveyApi, type DietSurveyCreateRequest } from "../api/dietSurvey";
import { dashboardApi } from "../api/dashboard";

function StepperInput({ label, value, onChange, min = 0, max = 30 }: {
  label: string; value: number; onChange: (v: number) => void; min?: number; max?: number;
}) {
  return (
    <div className="flex items-center gap-[12px]">
      <button
        onClick={() => onChange(Math.max(min, value - 1))}
        className="flex h-[36px] w-[36px] items-center justify-center rounded-sm border border-border-strong bg-bg text-lg"
      >−</button>
      <span className="w-[40px] text-center text-lg font-bold text-text-primary">{value}</span>
      <button
        onClick={() => onChange(Math.min(max, value + 1))}
        className="flex h-[36px] w-[36px] items-center justify-center rounded-sm border border-border-strong bg-bg text-lg"
      >+</button>
      <span className="text-sm text-text-secondary">{label}</span>
    </div>
  );
}

// 적음/보통/많음 3지선다 (음식군 섭취 빈도 → 0/1/2). 칼륨·단백질 문항용.
function ChoiceButtons({ value, onChange, options }: {
  value: number | null; onChange: (v: number) => void; options: string[];
}) {
  return (
    <div className="flex gap-[12px]">
      {options.map((opt, i) => (
        <button
          key={i}
          onClick={() => onChange(i)}
          className={`flex-1 rounded-md border px-[16px] py-[10px] text-sm ${
            value === i
              ? "border-accent bg-accent font-bold text-bg"
              : "border-border-strong bg-bg text-text-primary"
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

export function DietSurveyPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [soupStew, setSoupStew] = useState(2);
  const [sweetDrink, setSweetDrink] = useState(1);
  const [friedFood, setFriedFood] = useState(2);
  const [vegetables, setVegetables] = useState<boolean | null>(null);
  const [potassium, setPotassium] = useState<number | null>(null);
  const [protein, setProtein] = useState<number | null>(null);

  // 칼륨·단백질 문항은 A(eGFR<60=G1)·B(위험인자=G2)·CKD 진단자만 노출.
  // (미해당자에겐 무의미하고, 혈중 칼륨 미확인 상태에서 과일·채소 기피를 유발할 수 있어 묻지 않음)
  const { data: summary } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: dashboardApi.getSummary,
  });
  const appGroup = summary?.latest_health?.app_group ?? null;
  const ckdDiagnosed = summary?.latest_lifestyle?.ckd_diagnosed ?? false;
  const showKP = ckdDiagnosed || appGroup === "G1" || appGroup === "G2";

  async function handleSubmit() {
    if (vegetables === null) {
      setError("채소 섭취 여부를 선택해주세요."); return;
    }
    setError("");
    setLoading(true);
    try {
      const body: DietSurveyCreateRequest = {
        surveyed_date: new Date().toISOString().slice(0, 10),
        soup_stew_per_day: soupStew,
        sweet_drink_per_day: sweetDrink,
        fried_food_per_week: friedFood,
        vegetables_every_meal: vegetables,
      };
      // 해당자만 칼륨·단백질 전송. 미선택은 null(백엔드 nullable, 플래그 미생성).
      if (showKP) {
        body.potassium_food_freq = potassium;
        body.protein_food_freq = protein;
      }
      await dietSurveyApi.create(body);
      navigate("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="09 · 식이 설문 (REQ-DATA-05)" />
      <TopNav />
      <main className="flex flex-1 flex-col items-center p-[32px]">
        <h1 className="text-2xl font-bold text-text-primary">간단 식이 설문</h1>

        <div className="mt-[16px] w-[640px] rounded-sm bg-bg-alt border border-border p-[12px]">
          <p className="text-xs text-text-secondary">
            이 설문은 LLM 컨텍스트 전용이며 예측 모델에는 직접 사용되지 않습니다.
            식이 패턴을 파악해 맞춤 챌린지 생성에 활용합니다.
          </p>
        </div>

        {error && (
          <div className="mt-4 w-[640px] rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>
        )}

        <div className="mt-[24px] flex w-[640px] flex-col gap-[16px]">
          {/* Q1: 국·찌개 */}
          <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
            <div className="flex items-center gap-[12px]">
              <Soup size={24} className="text-text-secondary" />
              <p className="flex-1 text-sm font-bold text-text-primary">
                하루 국·찌개·탕류를 몇 번 드시나요?
              </p>
              <Tag label="나트륨" />
            </div>
            <StepperInput label="회" value={soupStew} onChange={setSoupStew} min={0} max={20} />
          </div>

          {/* Q2: 단 음료 */}
          <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
            <div className="flex items-center gap-[12px]">
              <Coffee size={24} className="text-text-secondary" />
              <p className="flex-1 text-sm font-bold text-text-primary">
                하루 단 음료 (커피 포함)를 몇 잔 드시나요?
              </p>
              <Tag label="당류" />
            </div>
            <StepperInput label="잔" value={sweetDrink} onChange={setSweetDrink} min={0} max={30} />
          </div>

          {/* Q3: 튀긴 음식 */}
          <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
            <div className="flex items-center gap-[12px]">
              <Pizza size={24} className="text-text-secondary" />
              <p className="flex-1 text-sm font-bold text-text-primary">
                주 몇 회 튀긴 음식을 드시나요?
              </p>
              <Tag label="지방" />
            </div>
            <StepperInput label="회" value={friedFood} onChange={setFriedFood} min={0} max={21} />
          </div>

          {/* Q4: 채소 */}
          <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
            <div className="flex items-center gap-[12px]">
              <Leaf size={24} className="text-text-secondary" />
              <p className="flex-1 text-sm font-bold text-text-primary">
                매 끼 채소 반찬을 드시나요?
              </p>
              <Tag label="식이섬유" />
            </div>
            <div className="flex gap-[12px]">
              <button
                onClick={() => setVegetables(true)}
                className={`flex-1 rounded-md border px-[16px] py-[10px] text-sm ${
                  vegetables === true
                    ? "border-accent bg-accent font-bold text-bg"
                    : "border-border-strong bg-bg text-text-primary"
                }`}
              >
                예
              </button>
              <button
                onClick={() => setVegetables(false)}
                className={`flex-1 rounded-md border px-[16px] py-[10px] text-sm ${
                  vegetables === false
                    ? "border-accent bg-accent font-bold text-bg"
                    : "border-border-strong bg-bg text-text-primary"
                }`}
              >
                아니오
              </button>
            </div>
          </div>

          {/* Q5·Q6: 칼륨·단백질 — 신장 위험군(A·B)·CKD 진단자만 노출 */}
          {showKP && (
            <>
              {/* Q5: 칼륨 (과일·채소·콩류 빈도) */}
              <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
                <div className="flex items-center gap-[12px]">
                  <Apple size={24} className="text-text-secondary" />
                  <p className="flex-1 text-sm font-bold text-text-primary">
                    과일·채소·콩류를 하루 몇 번 드시나요?
                  </p>
                  <Tag label="칼륨" />
                </div>
                <ChoiceButtons value={potassium} onChange={setPotassium} options={["적음", "보통", "많음"]} />
              </div>

              {/* Q6: 단백질 (고기·생선·계란 빈도) */}
              <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
                <div className="flex items-center gap-[12px]">
                  <Beef size={24} className="text-text-secondary" />
                  <p className="flex-1 text-sm font-bold text-text-primary">
                    고기·생선·계란을 하루 몇 번 드시나요?
                  </p>
                  <Tag label="단백질" />
                </div>
                <ChoiceButtons value={protein} onChange={setProtein} options={["적음", "보통", "많음"]} />
              </div>
            </>
          )}
        </div>

        <div className="mt-[24px] w-[640px]">
          <BtnPrimary label="완료" loading={loading} onClick={handleSubmit} height={48} className="w-full" />
        </div>
      </main>
    </div>
  );
}
