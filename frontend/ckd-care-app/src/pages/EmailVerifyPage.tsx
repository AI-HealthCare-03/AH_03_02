import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { MailCheck, RefreshCw } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { authApi } from "../api/auth";

interface NavState {
  email?: string;
  demoCode?: string | null;
  mode?: "demo" | "production";
  expiresInHours?: number;
}

export function EmailVerifyPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = (location.state ?? {}) as NavState;

  const [email, setEmail] = useState(state.email ?? "");
  const [code, setCode] = useState("");
  const [demoCode, setDemoCode] = useState<string | null>(state.demoCode ?? null);
  const [mode, setMode] = useState<"demo" | "production">(state.mode ?? "demo");
  const [expiresHours, setExpiresHours] = useState<number>(state.expiresInHours ?? 24);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const codeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    codeRef.current?.focus();
  }, []);

  async function handleVerify() {
    if (!email) { setError("이메일을 입력해주세요."); return; }
    if (!/^\d{6}$/.test(code)) { setError("6자리 숫자 코드를 입력해주세요."); return; }
    setError(""); setInfo("");
    setLoading(true);
    try {
      await authApi.verifyEmail(email, code);
      navigate("/", { state: { verifiedEmail: email } });
    } catch (e) {
      setError(e instanceof Error ? e.message : "인증에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    if (!email) { setError("이메일을 입력해주세요."); return; }
    setError(""); setInfo("");
    setResending(true);
    try {
      const res = await authApi.requestEmailVerification(email);
      setDemoCode(res.demo_code);
      setMode(res.mode);
      setExpiresHours(res.expires_in_hours);
      setCode("");
      setInfo(
        res.mode === "demo"
          ? "인증 메일을 재발송했습니다. (시연 모드 — 코드가 아래에 표시됩니다)"
          : "인증 메일을 재발송했습니다. 메일함을 확인해주세요."
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "재발송에 실패했습니다.");
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="03 · 이메일 인증 (REQ-AUTH-003)" />
      <main className="flex flex-1 items-center justify-center p-[32px]">
        <div className="flex w-[480px] flex-col gap-[20px] rounded-lg border border-border bg-bg shadow-card p-[32px]">
          <div className="flex flex-col items-center gap-[10px]">
            <span className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
              <MailCheck size={22} />
            </span>
            <h1 className="text-xl font-bold text-text-primary">이메일을 인증해주세요</h1>
            <p className="text-center text-sm text-text-secondary">
              {email ? <span className="font-bold">{email}</span> : "가입한 이메일"} 로 6자리 인증 코드를 보냈습니다.
              <br />
              코드는 {expiresHours}시간 동안 유효합니다.
            </p>
          </div>

          {!state.email && (
            <FormField label="이메일">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@example.com"
                className="w-full bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"
              />
            </FormField>
          )}

          <FormField label="인증 코드 (6자리)">
            <input
              ref={codeRef}
              type="text"
              inputMode="numeric"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="000000"
              className="w-full bg-transparent text-center font-mono text-lg tracking-[8px] text-text-primary outline-none placeholder:text-text-muted"
            />
          </FormField>

          {/* 시연 모드 — 코드 인라인 노출 */}
          {mode === "demo" && demoCode && (
            <div className="rounded-lg border border-amber-300 bg-amber-50 p-[12px]">
              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-700">시연 모드 (EMAIL_MODE=demo)</p>
              <div className="mt-[6px] flex items-center justify-between gap-[8px]">
                <p className="font-mono text-xl font-bold tracking-[8px] text-amber-900">{demoCode}</p>
                <button
                  type="button"
                  onClick={() => setCode(demoCode)}
                  className="rounded-md border border-amber-400 bg-bg px-[10px] py-[4px] text-xs font-bold text-amber-700 hover:bg-amber-100"
                >
                  자동 입력
                </button>
              </div>
              <p className="mt-[6px] text-[10px] text-amber-700">
                production 환경에서는 실제 이메일로만 전송됩니다.
              </p>
            </div>
          )}

          {info && (
            <div className="rounded-sm bg-success/10 px-[12px] py-[8px] text-xs text-success">{info}</div>
          )}
          {error && (
            <div className="rounded-sm bg-danger/10 px-[12px] py-[8px] text-xs text-danger">{error}</div>
          )}

          <button
            type="button"
            onClick={handleVerify}
            disabled={loading}
            className="flex h-[44px] items-center justify-center rounded-lg bg-accent text-sm font-bold text-bg shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {loading ? "인증 중..." : "인증 완료"}
          </button>

          <div className="flex items-center gap-[8px]">
            <button
              type="button"
              onClick={handleResend}
              disabled={resending}
              className="flex h-[40px] flex-1 items-center justify-center gap-[6px] rounded-md border border-border-strong bg-bg text-sm font-normal text-text-primary disabled:opacity-50"
            >
              <RefreshCw size={14} />
              {resending ? "재발송 중..." : "코드 재발송"}
            </button>
            <button
              type="button"
              onClick={() => navigate("/")}
              className="flex h-[40px] flex-1 items-center justify-center rounded-md border border-border-strong bg-bg text-sm font-normal text-text-primary"
            >
              로그인 화면
            </button>
          </div>

          <p className="text-center text-[10px] text-text-muted">
            메일이 도착하지 않았다면 스팸함을 확인해주세요. 재발송은 1시간에 3회까지만 가능합니다.
          </p>
        </div>
      </main>
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-[4px]">
      <label className="text-sm font-normal text-text-secondary">{label}</label>
      <div className="flex h-[44px] items-center rounded-sm border border-border-strong bg-bg px-[12px]">
        {children}
      </div>
    </div>
  );
}
