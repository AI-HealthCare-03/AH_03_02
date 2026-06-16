import { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Shield, AlertCircle, CheckCircle2 } from "lucide-react";
import { adminApi, type AdminUserDetail } from "../../api/admin";
import { useAuth } from "../../contexts/AuthContext";

export function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const userId = Number(id);
  const { startImpersonation } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<AdminUserDetail | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [confirming, setConfirming] = useState<null | "activate" | "deactivate" | "verify">(null);
  const [reason, setReason] = useState("");

  async function reload() {
    if (!userId) return;
    try {
      const d = await adminApi.getUser(userId);
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "상세 로딩 실패");
    }
  }

  useEffect(() => { reload(); }, [userId]);

  async function performAction(act: "activate" | "deactivate" | "verify") {
    setError(""); setInfo("");
    try {
      if (act === "activate") await adminApi.activateUser(userId, reason || undefined);
      else if (act === "deactivate") {
        if (!reason.trim()) { setError("정지 사유를 입력해주세요."); return; }
        await adminApi.deactivateUser(userId, reason);
      }
      else await adminApi.forceVerifyEmail(userId, reason || undefined);
      setInfo(
        act === "activate" ? "계정을 활성화했습니다."
        : act === "deactivate" ? "계정을 정지했습니다."
        : "이메일을 강제 인증 처리했습니다."
      );
      setReason("");
      setConfirming(null);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리 실패");
    }
  }

  return (
    <div className="flex flex-col gap-[16px] p-[24px]">
      <Link to="/admin/users" className="flex w-fit items-center gap-[6px] text-xs text-slate-400 hover:text-slate-200">
        <ArrowLeft size={12} /> 목록으로
      </Link>

      <header>
        <h1 className="text-xl font-bold text-slate-100">사용자 상세</h1>
        <p className="mt-[2px] text-xs text-slate-400">검진 수치는 범주만 표시됩니다 (CLAUDE.md §5).</p>
      </header>

      {info && (
        <div className="flex items-center gap-[6px] rounded-md bg-emerald-900/30 px-[12px] py-[8px] text-xs text-emerald-300">
          <CheckCircle2 size={14} /> {info}
        </div>
      )}
      {error && (
        <div className="flex items-center gap-[6px] rounded-md bg-rose-900/30 px-[12px] py-[8px] text-xs text-rose-300">
          <AlertCircle size={14} /> {error}
        </div>
      )}

      {data && (
        <>
          <section className="rounded-md border border-slate-700 bg-slate-800/50 p-[16px]">
            <h2 className="text-sm font-bold text-slate-200">계정 정보 (마스킹)</h2>
            <div className="mt-[12px] grid grid-cols-2 gap-[8px] text-xs">
              <Field label="ID" value={data.id} />
              <Field label="이메일" value={data.email_masked} mono />
              <Field label="이름" value={data.name_masked} />
              <Field label="전화" value={data.phone_masked} mono />
              <Field label="성별" value={data.gender === "MALE" ? "남" : "여"} />
              <Field label="나이" value={`만 ${data.age}세`} />
              <Field label="활성 상태" value={data.is_active ? "활성" : "정지"} />
              <Field label="관리자" value={data.is_admin ? "Y" : "N"} />
              <Field label="이메일 인증" value={data.email_verified ? "완료" : "미인증"} />
              <Field label="비번 실패 누적" value={data.failed_login_count} />
              <Field label="잠금 해제 시각" value={data.locked_until ?? "-"} />
              <Field label="마지막 로그인" value={data.last_login ?? "-"} />
              <Field label="가입일" value={data.created_at} />
            </div>
          </section>

          <section className="rounded-md border border-slate-700 bg-slate-800/50 p-[16px]">
            <h2 className="text-sm font-bold text-slate-200">최신 검진 요약 (범주만)</h2>
            <p className="mt-[2px] text-[10px] text-slate-400">CLAUDE.md §5: 원본 수치 노출 금지</p>
            {data.latest_health_summary ? (
              <div className="mt-[12px] grid grid-cols-2 gap-[8px] text-xs">
                <Field label="검진일" value={data.latest_health_summary.checked_date} />
                <Field label="CKD 단계" value={data.latest_health_summary.ckd_stage ?? "-"} />
                <Field label="혈압" value={data.latest_health_summary.systolic_bp_category} />
                <Field label="공복혈당" value={data.latest_health_summary.fasting_glucose_category} />
                <Field label="eGFR" value={data.latest_health_summary.egfr_category} />
              </div>
            ) : (
              <p className="mt-[12px] text-xs text-slate-500">검진 데이터 없음</p>
            )}
          </section>

          <section className="rounded-md border border-amber-700 bg-amber-900/10 p-[16px]">
            <div className="flex items-center gap-[6px]">
              <Shield size={14} className="text-amber-400" />
              <h2 className="text-sm font-bold text-amber-300">관리자 액션</h2>
            </div>
            <p className="mt-[2px] text-[10px] text-slate-400">모든 액션은 감사 로그에 영구 기록됩니다.</p>

            <div className="mt-[12px] flex flex-wrap gap-[8px]">
              {data.is_active ? (
                <ActionBtn label="계정 정지" warn onClick={() => setConfirming("deactivate")} />
              ) : (
                <ActionBtn label="계정 활성화" onClick={() => setConfirming("activate")} />
              )}
              {!data.email_verified && (
                <ActionBtn label="이메일 인증 강제" onClick={() => setConfirming("verify")} />
              )}
              <button
                type="button"
                onClick={async () => {
                  setError(""); setInfo("");
                  try {
                    const res = await adminApi.impersonate(userId);
                    await startImpersonation(res.access_token, res.target);
                    navigate("/dashboard");
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "임퍼소네이션 실패");
                  }
                }}
                className="rounded-md bg-indigo-500 px-[12px] py-[6px] text-xs font-bold text-white hover:bg-indigo-400"
              >
                이 사용자로 보기 (읽기전용)
              </button>
            </div>

            {confirming && (
              <div className="mt-[12px] flex flex-col gap-[10px] rounded-md bg-slate-900 p-[12px]">
                <p className="text-xs text-slate-200">
                  {confirming === "deactivate" ? "계정 정지 사유를 입력해주세요 (감사 로그에 영구 기록)." :
                    confirming === "verify" ? "이메일 인증 강제 처리 사유 (선택, 감사 로그에 기록)." :
                    "활성화 사유 (선택)."}
                </p>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={2}
                  maxLength={500}
                  placeholder={confirming === "deactivate" ? "예: 약관 위반 누적 (필수)" : "선택 사항"}
                  className="rounded-md border border-slate-700 bg-slate-800 px-[10px] py-[6px] text-xs text-slate-100 outline-none"
                />
                <div className="flex justify-end gap-[8px]">
                  <button
                    type="button"
                    onClick={() => { setConfirming(null); setReason(""); }}
                    className="rounded-md border border-slate-700 px-[12px] py-[6px] text-xs text-slate-300 hover:bg-slate-800"
                  >
                    취소
                  </button>
                  <button
                    type="button"
                    onClick={() => performAction(confirming)}
                    className="rounded-md bg-amber-400 px-[12px] py-[6px] text-xs font-bold text-slate-900 hover:bg-amber-300"
                  >
                    확인
                  </button>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string | number; mono?: boolean }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-[2px] text-slate-200 ${mono ? "font-mono" : ""}`}>{value}</p>
    </div>
  );
}

function ActionBtn({ label, warn, onClick }: { label: string; warn?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-[12px] py-[8px] text-xs font-bold ${
        warn
          ? "bg-rose-500/20 text-rose-300 hover:bg-rose-500/30"
          : "bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30"
      }`}
    >
      {label}
    </button>
  );
}
