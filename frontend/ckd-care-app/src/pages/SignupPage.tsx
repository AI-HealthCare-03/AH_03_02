import { useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TextInput } from "../components/TextInput";
import { BtnPrimary } from "../components/BtnPrimary";
import { ConsentAccordion, type ConsentMap } from "../components/ConsentAccordion";
import { CONSENTS } from "../data/consents";
import { authApi } from "../api/auth";

// 숫자만 추출 → YYYY-MM-DD 자동 포맷팅 (최대 8자리)
function formatBirthDate(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 4) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 4)}-${digits.slice(4)}`;
  return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6)}`;
}

// 숫자만 추출 → 010-1234-5678 자동 포맷팅 (10~11자리)
function formatPhoneNumber(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 11);
  if (digits.length < 4) return digits;
  if (digits.length < 8) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  if (digits.length < 11) return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
  return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
}

export function SignupPage() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    birth_date: "",
    phone_number: "",
    gender: "" as "MALE" | "FEMALE" | "",
  });
  const initialConsents = useMemo<ConsentMap>(
    () =>
      ({
        TERMS_OF_SERVICE: false,
        PRIVACY_INFO: false,
        SENSITIVE_HEALTH: false,
        MARKETING: false,
      }) as ConsentMap,
    [],
  );
  const [consents, setConsents] = useState<ConsentMap>(initialConsents);
  const [showPassword, setShowPassword] = useState(false);
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [showPasswordConfirm, setShowPasswordConfirm] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // 이메일 중복 확인 상태 (팀원 피드백 #5)
  type EmailCheckState = "idle" | "checking" | "available" | "taken" | "invalid";
  const [emailCheckState, setEmailCheckState] = useState<EmailCheckState>("idle");

  function setText(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
  }

  function onEmailChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm((prev) => ({ ...prev, email: e.target.value }));
    // 입력 변경 시 이전 확인 결과 무효화 — 사용자가 다시 확인하도록 유도
    if (emailCheckState !== "idle") setEmailCheckState("idle");
  }

  async function handleCheckEmail() {
    if (!form.email) {
      setEmailCheckState("invalid");
      return;
    }
    setEmailCheckState("checking");
    try {
      const res = await authApi.checkEmail(form.email);
      setEmailCheckState(res.available ? "available" : "taken");
    } catch (e) {
      const raw = e instanceof Error ? e.message : "";
      // 백엔드가 400 + "올바르지 않습니다" 반환 시 형식 오류로 분류
      setEmailCheckState(raw.includes("올바르지") || raw.includes("형식") ? "invalid" : "taken");
    }
  }

  function onBirthDateChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm((prev) => ({ ...prev, birth_date: formatBirthDate(e.target.value) }));
  }

  function onPhoneChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm((prev) => ({ ...prev, phone_number: formatPhoneNumber(e.target.value) }));
  }

  async function handleSignup() {
    if (!form.name || !form.email || !form.password || !form.birth_date || !form.phone_number || !form.gender) {
      setError("모든 항목을 입력해주세요."); return;
    }
    if (emailCheckState !== "available") {
      setError("이메일 중복 확인을 먼저 진행해주세요.");
      return;
    }
    if (form.password.length < 8) {
      setError("비밀번호는 8자 이상이어야 합니다."); return;
    }
    if (!/[A-Z]/.test(form.password) || !/[a-z]/.test(form.password) || !/[0-9]/.test(form.password) || !/[^a-zA-Z0-9]/.test(form.password)) {
      setError("비밀번호는 영문 대소문자·숫자·특수문자를 각 1개 이상 포함해야 합니다."); return;
    }
    if (form.password !== passwordConfirm) {
      setError("비밀번호 확인이 일치하지 않습니다."); return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.birth_date)) {
      setError("생년월일은 8자리 숫자로 입력해주세요 (예: 19990101)."); return;
    }
    if (!/^\d{10,11}$/.test(form.phone_number.replace(/-/g, ""))) {
      setError("전화번호는 숫자 10~11자리로 입력해주세요 (예: 01012345678)."); return;
    }
    if (!consents.TERMS_OF_SERVICE || !consents.PRIVACY_INFO || !consents.SENSITIVE_HEALTH) {
      setError("필수 약관에 모두 동의해야 가입할 수 있습니다."); return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await authApi.signup({
        name: form.name,
        email: form.email,
        password: form.password,
        birth_date: form.birth_date,
        phone_number: form.phone_number,
        gender: form.gender as "MALE" | "FEMALE",
        consents: CONSENTS.map((c) => ({
          consent_type: c.type,
          version: c.version,
          agreed: consents[c.type],
        })),
      });
      navigate("/email-verify", {
        state: {
          email: res.email,
          demoCode: res.email_verification.demo_code,
          mode: res.email_verification.mode,
          expiresInHours: res.email_verification.expires_in_hours,
        },
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "회원가입에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="02 · 회원가입 (REQ-AUTH-02)" />
      <main className="flex flex-1 items-center justify-center p-[32px]">
        <div className="flex w-[520px] flex-col gap-[24px] rounded-lg border border-border bg-bg shadow-card p-[40px]">
          <h1 className="text-2xl font-bold text-text-primary">회원가입</h1>

          <div className="flex flex-col gap-[16px]">
            <TextInput
              label="이름"
              placeholder="홍길동"
              value={form.name}
              onChange={setText("name")}
              autoComplete="name"
            />
            <div className="flex flex-col gap-[4px]">
              <TextInput
                label="이메일"
                placeholder="email@example.com"
                type="email"
                value={form.email}
                onChange={onEmailChange}
                autoComplete="email"
                rightSlot={
                  <button
                    type="button"
                    onClick={handleCheckEmail}
                    disabled={!form.email || emailCheckState === "checking"}
                    className="rounded-sm bg-info px-[10px] py-[4px] text-xs font-bold text-bg disabled:opacity-50"
                  >
                    {emailCheckState === "checking" ? "확인중" : "중복확인"}
                  </button>
                }
              />
              {emailCheckState === "available" && (
                <p className="text-xs text-success">사용 가능한 이메일입니다.</p>
              )}
              {emailCheckState === "taken" && (
                <p className="text-xs text-danger">이미 사용 중인 이메일입니다.</p>
              )}
              {emailCheckState === "invalid" && (
                <p className="text-xs text-danger">입력하신 이메일 형식이 올바르지 않습니다.</p>
              )}
            </div>
            <div className="flex flex-col gap-[4px]">
              <TextInput
                label="비밀번호"
                placeholder="비밀번호를 입력하세요"
                type={showPassword ? "text" : "password"}
                value={form.password}
                onChange={setText("password")}
                autoComplete="new-password"
                rightSlot={
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    aria-label={showPassword ? "비밀번호 숨기기" : "비밀번호 보기"}
                    className="text-text-muted hover:text-text-primary"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                }
              />
              <p className="text-xs text-text-muted">8자 이상, 영문 대소문자·숫자·특수문자 각 1개 이상</p>
            </div>
            <div className="flex flex-col gap-[4px]">
              <TextInput
                label="비밀번호 확인"
                placeholder="비밀번호를 한 번 더 입력하세요"
                type={showPasswordConfirm ? "text" : "password"}
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                autoComplete="new-password"
                rightSlot={
                  <button
                    type="button"
                    onClick={() => setShowPasswordConfirm((s) => !s)}
                    aria-label={showPasswordConfirm ? "비밀번호 숨기기" : "비밀번호 보기"}
                    className="text-text-muted hover:text-text-primary"
                  >
                    {showPasswordConfirm ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                }
              />
              {passwordConfirm.length > 0 && form.password !== passwordConfirm && (
                <p className="text-xs text-danger">비밀번호가 일치하지 않습니다.</p>
              )}
              {passwordConfirm.length > 0 && form.password === passwordConfirm && (
                <p className="text-xs text-success">비밀번호가 일치합니다.</p>
              )}
            </div>
            <TextInput
              label="생년월일"
              placeholder="YYYY-MM-DD"
              value={form.birth_date}
              onChange={onBirthDateChange}
              inputMode="numeric"
              maxLength={10}
              autoComplete="bday"
            />
            <TextInput
              label="전화번호"
              placeholder="010-1234-5678"
              value={form.phone_number}
              onChange={onPhoneChange}
              inputMode="tel"
              maxLength={13}
              autoComplete="tel"
            />
          </div>

          <div className="flex flex-col gap-[8px]">
            <label className="text-sm font-normal text-text-secondary">성별</label>
            <div className="flex gap-[12px]">
              {(["MALE", "FEMALE"] as const).map((g) => (
                <button
                  key={g}
                  type="button"
                  onClick={() => setForm((prev) => ({ ...prev, gender: g }))}
                  className={`flex-1 rounded-md border px-[16px] py-[10px] text-sm font-normal ${
                    form.gender === g
                      ? "border-accent bg-accent text-bg"
                      : "border-border-strong bg-bg text-text-primary"
                  }`}
                >
                  {g === "MALE" ? "남성" : "여성"}
                </button>
              ))}
            </div>
          </div>

          <ConsentAccordion value={consents} onChange={setConsents} />

          {error && (
            <p className="rounded-sm bg-danger/10 px-[12px] py-[8px] text-sm text-danger">
              {error}
            </p>
          )}

          <BtnPrimary label="가입하기" height={48} className="w-full" onClick={handleSignup} loading={loading} />

          <p className="text-center text-sm text-text-secondary">
            이미 계정이 있으신가요?{" "}
            <Link to="/" className="font-bold text-info">로그인</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
