import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ScreenLabel } from "../components/ScreenLabel";
import { TextInput } from "../components/TextInput";
import { Checkbox } from "../components/Checkbox";
import { BtnPrimary } from "../components/BtnPrimary";
import { authApi } from "../api/auth";
import { useAuth } from "../contexts/AuthContext";
import { Activity, ListChecks, Sparkles, MessageCircle } from "lucide-react";

// 로그인 화면 좌측 서비스 소개 항목
const LOGIN_FEATURES = [
  {
    icon: Activity,
    title: "검진 기반 신장 건강 분석",
    desc: "eGFR 추정과 위험도 등급으로 내 신장 상태를 한눈에 확인해요.",
  },
  {
    icon: ListChecks,
    title: "맞춤 데일리 챌린지",
    desc: "트랙별 필수 체크와 생활습관 기록으로 꾸준한 관리를 돕습니다.",
  },
  {
    icon: Sparkles,
    title: "캐릭터와 함께 성장",
    desc: "체크인할수록 알이 부화하고 포인트가 쌓이는 즐거운 동기부여.",
  },
  {
    icon: MessageCircle,
    title: "AI 신장 건강 챗봇",
    desc: "식이·생활습관 궁금증을 신뢰할 수 있는 근거로 답해드려요.",
  },
];

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // 비밀번호 찾기 상태 (2단계 흐름)
  const [showForgot, setShowForgot] = useState(false);
  const [forgotStep, setForgotStep] = useState<"email" | "code" | "done">("email");
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotCode, setForgotCode] = useState("");
  const [demoCode, setDemoCode] = useState<string | null>(null);
  const [emailMode, setEmailMode] = useState<"demo" | "production">("demo");
  const [forgotLoading, setForgotLoading] = useState(false);
  const [tempPassword, setTempPassword] = useState("");
  const [forgotError, setForgotError] = useState("");

  function resetForgot() {
    setShowForgot(false);
    setForgotStep("email");
    setForgotEmail("");
    setForgotCode("");
    setDemoCode(null);
    setTempPassword("");
    setForgotError("");
  }

  async function handleLogin() {
    if (!email || !password) { setError("이메일과 비밀번호를 입력하세요."); return; }
    setError("");
    setLoading(true);
    try {
      const res = await authApi.login({ email, password });
      await login(res.access_token, rememberMe);
      navigate("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "로그인에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRequestCode() {
    if (!forgotEmail) {
      setForgotError("이메일을 입력해주세요.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(forgotEmail)) {
      setForgotError("올바른 이메일 형식이 아닙니다.");
      return;
    }
    setForgotError("");
    setForgotLoading(true);
    try {
      const res = await authApi.requestPasswordReset(forgotEmail);
      setEmailMode(res.mode);
      setDemoCode(res.demo_code);
      setForgotStep("code");
    } catch (e) {
      const raw = e instanceof Error ? e.message : "";
      let msg = "인증 코드 발송에 실패했습니다.";
      if (raw.includes("등록된 이메일")) msg = "등록된 이메일이 없습니다.";
      else if (raw.includes("소셜 로그인")) msg = "소셜 로그인 계정은 비밀번호 재설정을 사용할 수 없습니다.";
      else if (raw.toLowerCase().includes("email")) msg = "올바른 이메일 형식이 아닙니다.";
      else if (raw) msg = raw;
      setForgotError(msg);
    } finally {
      setForgotLoading(false);
    }
  }

  async function handleVerifyCode() {
    if (!/^\d{6}$/.test(forgotCode)) {
      setForgotError("6자리 숫자 코드를 입력해주세요.");
      return;
    }
    setForgotError("");
    setForgotLoading(true);
    try {
      const res = await authApi.verifyPasswordReset(forgotEmail, forgotCode);
      setTempPassword(res.temp_password);
      setForgotStep("done");
    } catch (e) {
      const raw = e instanceof Error ? e.message : "";
      let msg = "인증에 실패했습니다.";
      if (raw.includes("일치하지 않습니다")) msg = raw;
      else if (raw.includes("만료") || raw.includes("발급된 인증 코드")) msg = raw;
      else if (raw.includes("초과")) msg = raw;
      else if (raw) msg = raw;
      setForgotError(msg);
    } finally {
      setForgotLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="01 · 로그인 (REQ-AUTH-01)" />
      <main className="flex flex-1 items-center justify-center p-[24px] sm:p-[32px]">
        <div className="grid w-full max-w-[1080px] grid-cols-1 items-center gap-[32px] lg:grid-cols-2 lg:gap-[48px]">
          {/* 좌: 서비스 소개 (모바일=폼 위 1열, 넓은 화면=좌측) */}
          <section className="flex flex-col gap-[28px]">
            <div>
              <h2 className="text-3xl font-bold leading-snug text-text-primary">
                콩팥 건강,
                <br />
                매일의 작은 습관으로
              </h2>
              <p className="mt-4 text-sm leading-relaxed text-text-secondary">
                만성콩팥병(CKD)은 초기에 증상 없이 조용히 진행됩니다. KiniQ는 검진 결과를 쉽게 이해하도록 돕고,
                매일의 챌린지로 신장 건강을 꾸준히 관리할 수 있게 합니다.
              </p>
            </div>
            <ul className="flex flex-col gap-[18px]">
              {LOGIN_FEATURES.map((f) => (
                <li key={f.title} className="flex items-start gap-[14px]">
                  <span className="flex h-[40px] w-[40px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                    <f.icon size={20} />
                  </span>
                  <div>
                    <p className="text-sm font-bold text-text-primary">{f.title}</p>
                    <p className="mt-0.5 text-sm leading-relaxed text-text-secondary">{f.desc}</p>
                  </div>
                </li>
              ))}
            </ul>
            <p className="text-xs leading-relaxed text-text-muted">
              ※ 본 서비스는 의료 진단·처방을 대체하지 않습니다. 표시된 수치·예측은 일반 생활습관 정보이며,
              정확한 진단·치료는 의사 상담을 받으세요.
            </p>
          </section>

          {/* 우: 로그인 폼 */}
          <div className="mx-auto flex w-full max-w-[440px] flex-col gap-[24px] rounded-lg border border-border bg-bg shadow-card p-[24px] sm:p-[40px]">
          <div className="flex flex-col items-center gap-[8px]">
            <img
              src="/logo/kiniq-vertical-color.svg"
              alt="KiniQ"
              className="h-[72px] w-auto"
            />
            <p className="text-sm text-text-secondary text-center">
              만성콩팥병 환자 생활습관 관리 챌린지에 오신 것을 환영합니다
            </p>
          </div>

          {/* 비밀번호 찾기 패널 (2단계 흐름) */}
          {showForgot ? (
            <div className="flex flex-col gap-[16px] rounded-lg border border-border bg-bg-alt p-[16px]">
              <div className="flex items-center justify-between">
                <p className="text-sm font-bold text-text-primary">
                  비밀번호 찾기 {forgotStep === "email" ? "(1/2)" : forgotStep === "code" ? "(2/2)" : ""}
                </p>
                <button className="text-xs text-text-muted hover:text-text-secondary" onClick={resetForgot}>
                  닫기
                </button>
              </div>

              {forgotError && (
                <div className="rounded-sm bg-danger/10 px-[12px] py-[8px] text-sm text-danger">
                  {forgotError}
                </div>
              )}

              {forgotStep === "email" && (
                <>
                  <TextInput
                    label="가입 시 등록한 이메일"
                    placeholder="email@example.com"
                    type="email"
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                  />
                  <BtnPrimary label="인증 코드 받기" loading={forgotLoading} onClick={handleRequestCode} />
                  <p className="text-xs text-text-muted">
                    입력하신 이메일로 6자리 인증 코드를 발송합니다. 코드는 5분간 유효합니다.
                  </p>
                </>
              )}

              {forgotStep === "code" && (
                <>
                  <div className="rounded-sm bg-info/10 px-[12px] py-[10px] text-sm text-info">
                    {emailMode === "demo" && demoCode ? (
                      <>
                        🧪 <strong>시연 모드</strong> · 발송 대신 코드가 노출됩니다:{" "}
                        <span className="font-mono font-bold text-lg">{demoCode}</span>
                      </>
                    ) : (
                      <><strong>{forgotEmail}</strong> 로 인증 코드를 발송했어요. 메일함을 확인해주세요.</>
                    )}
                  </div>
                  <TextInput
                    label="6자리 인증 코드"
                    placeholder="000000"
                    type="text"
                    value={forgotCode}
                    onChange={(e) => setForgotCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  />
                  <BtnPrimary label="코드 확인 + 임시 비밀번호 받기" loading={forgotLoading} onClick={handleVerifyCode} />
                  <button
                    className="text-xs text-text-muted hover:text-text-secondary self-start"
                    onClick={() => { setForgotStep("email"); setForgotCode(""); setForgotError(""); setDemoCode(null); }}
                  >
                    ← 이메일 다시 입력
                  </button>
                </>
              )}

              {forgotStep === "done" && (
                <div className="flex flex-col gap-[8px] rounded-sm bg-success/10 px-[12px] py-[10px]">
                  <p className="text-sm text-success font-bold">임시 비밀번호가 발급됐습니다.</p>
                  <p className="text-sm text-success">
                    임시 비밀번호: <span className="font-mono font-bold">{tempPassword}</span>
                  </p>
                  <p className="text-xs text-text-secondary">로그인 후 마이페이지에서 비밀번호를 변경해주세요.</p>
                </div>
              )}
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-[16px]">
                <TextInput
                  label="이메일"
                  placeholder="email@example.com"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <TextInput
                  label="비밀번호"
                  placeholder="비밀번호를 입력하세요"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              {error && (
                <p className="rounded-sm bg-danger/10 px-[12px] py-[8px] text-sm text-danger">
                  {error}
                </p>
              )}

              <div className="flex items-center justify-between">
                <Checkbox
                  label="로그인 유지"
                  checked={rememberMe}
                  onChange={setRememberMe}
                />
                <button
                  className="text-sm text-info hover:underline"
                  onClick={() => setShowForgot(true)}
                >
                  비밀번호 찾기
                </button>
              </div>

              <BtnPrimary
                label="로그인"
                height={48}
                className="w-full"
                onClick={handleLogin}
                loading={loading}
              />
            </>
          )}

          <p className="text-center text-sm text-text-secondary">
            계정이 없으신가요?{" "}
            <Link to="/signup" className="font-bold text-info">회원가입</Link>
          </p>

          <p className="text-center text-xs text-text-muted">
            본 서비스는 의료 진단·처방을 대체하지 않습니다.
          </p>
          </div>
        </div>
      </main>
    </div>
  );
}
