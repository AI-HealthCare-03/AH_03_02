import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ScreenLabel } from "../components/ScreenLabel";
import { TextInput } from "../components/TextInput";
import { Checkbox } from "../components/Checkbox";
import { BtnPrimary } from "../components/BtnPrimary";
import { authApi } from "../api/auth";

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
  const [agreed, setAgreed] = useState({ sensitive: false, privacy: false, terms: false, marketing: false });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function set(field: string) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
  }

  async function handleSignup() {
    if (!form.name || !form.email || !form.password || !form.birth_date || !form.phone_number || !form.gender) {
      setError("모든 항목을 입력해주세요."); return;
    }
    if (form.password.length < 8) {
      setError("비밀번호는 8자 이상이어야 합니다."); return;
    }
    if (!/[a-zA-Z]/.test(form.password) || !/[0-9]/.test(form.password) || !/[^a-zA-Z0-9]/.test(form.password)) {
      setError("비밀번호는 영문, 숫자, 특수문자를 각 1개 이상 포함해야 합니다."); return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.birth_date)) {
      setError("생년월일은 YYYY-MM-DD 형식으로 입력해주세요."); return;
    }
    if (!/^\d{10,11}$/.test(form.phone_number.replace(/-/g, ""))) {
      setError("전화번호는 숫자 10~11자리로 입력해주세요 (예: 01012345678)."); return;
    }
    if (!agreed.sensitive || !agreed.privacy || !agreed.terms) {
      setError("필수 동의 항목을 모두 체크해주세요."); return;
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
      });
      // REQ-AUTH-003: 회원가입 직후 이메일 인증 페이지로. demo 모드면 코드 함께 전달
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
        <div className="flex w-[520px] flex-col gap-[24px] rounded-lg border border-border bg-bg p-[40px]">
          <h1 className="text-2xl font-bold text-text-primary">회원가입</h1>

          <div className="flex flex-col gap-[16px]">
            <TextInput label="이름" placeholder="홍길동" value={form.name} onChange={set("name")} />
            <TextInput label="이메일" placeholder="email@example.com" type="email" value={form.email} onChange={set("email")} />
            <div className="flex flex-col gap-[4px]">
              <TextInput label="비밀번호" placeholder="비밀번호를 입력하세요" type="password" value={form.password} onChange={set("password")} />
              <p className="text-xs text-text-muted">8자 이상, 영문·숫자·특수문자 각 1개 이상</p>
            </div>
            <TextInput label="생년월일" placeholder="YYYY-MM-DD" value={form.birth_date} onChange={set("birth_date")} />
            <TextInput label="전화번호" placeholder="01011112222" value={form.phone_number} onChange={set("phone_number")} />
          </div>

          <div className="flex flex-col gap-[8px]">
            <label className="text-sm font-normal text-text-secondary">성별</label>
            <div className="flex gap-[12px]">
              {(["MALE", "FEMALE"] as const).map((g) => (
                <button
                  key={g}
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

          <div className="flex flex-col gap-[12px] rounded-sm border border-border bg-bg-alt p-[12px]">
            <p className="text-sm font-bold text-text-primary">필수 동의 (개인정보보호법 §23)</p>
            <div className="flex flex-col gap-[10px]">
              <Checkbox
                label="[필수] 민감의료정보 수집·이용 동의"
                checked={agreed.sensitive}
                onChange={(v) => setAgreed((p) => ({ ...p, sensitive: v }))}
              />
              <Checkbox
                label="[필수] 개인정보 처리방침 동의"
                checked={agreed.privacy}
                onChange={(v) => setAgreed((p) => ({ ...p, privacy: v }))}
              />
              <Checkbox
                label="[필수] 서비스 이용약관 동의"
                checked={agreed.terms}
                onChange={(v) => setAgreed((p) => ({ ...p, terms: v }))}
              />
              <Checkbox
                label="[선택] 마케팅 수신 동의"
                checked={agreed.marketing}
                onChange={(v) => setAgreed((p) => ({ ...p, marketing: v }))}
              />
            </div>
          </div>

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
