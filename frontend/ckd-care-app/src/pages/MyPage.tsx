import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Heart, ClipboardList, Bell, Settings, Headphones, LogOut, KeyRound, UserX, UserCog } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { Tag } from "../components/Tag";
import { ListItem } from "../components/ListItem";
import { TextInput } from "../components/TextInput";
import { BtnPrimary } from "../components/BtnPrimary";
import { useAuth } from "../contexts/AuthContext";
import { authApi } from "../api/auth";

type Panel = "logout" | "account";

export function MyPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [panel, setPanel] = useState<Panel>("logout");

  // 비밀번호 변경 폼 상태
  const [pwForm, setPwForm] = useState({ current: "", next: "", confirm: "" });
  const [pwError, setPwError] = useState("");
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwLoading, setPwLoading] = useState(false);

  // 회원탈퇴 상태
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);

  // 회원정보 수정 상태 (팀원 피드백 #2 — 이름·생년월일·전화번호)
  const [profileForm, setProfileForm] = useState({ name: "", birthday: "", phone_number: "" });
  const [profileError, setProfileError] = useState("");
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);

  // user 정보 로드 후 폼 초기값 세팅
  useEffect(() => {
    if (user) {
      setProfileForm({
        name: user.name ?? "",
        birthday: user.birthday ?? "",
        phone_number: user.phone_number ?? "",
      });
    }
  }, [user]);

  // 숫자만 → 010-1234-5678 자동 포맷팅
  function formatPhone(raw: string): string {
    const d = raw.replace(/\D/g, "").slice(0, 11);
    if (d.length < 4) return d;
    if (d.length < 8) return `${d.slice(0, 3)}-${d.slice(3)}`;
    return `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`;
  }

  // 숫자만 → YYYY-MM-DD 자동 포맷팅
  function formatBirth(raw: string): string {
    const d = raw.replace(/\D/g, "").slice(0, 8);
    if (d.length <= 4) return d;
    if (d.length <= 6) return `${d.slice(0, 4)}-${d.slice(4)}`;
    return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6)}`;
  }

  async function handleProfileSave() {
    if (!profileForm.name || !profileForm.birthday || !profileForm.phone_number) {
      setProfileError("모든 항목을 입력해주세요."); return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(profileForm.birthday)) {
      setProfileError("생년월일은 YYYY-MM-DD 형식이어야 합니다 (예: 19990101)."); return;
    }
    if (!/^\d{10,11}$/.test(profileForm.phone_number.replace(/-/g, ""))) {
      setProfileError("전화번호는 숫자 10~11자리로 입력해주세요."); return;
    }
    setProfileError("");
    setProfileLoading(true);
    try {
      await authApi.updateMe({
        name: profileForm.name,
        birthday: profileForm.birthday,
        phone_number: profileForm.phone_number,
      });
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (e) {
      setProfileError(e instanceof Error ? e.message : "회원정보 수정에 실패했습니다.");
    } finally {
      setProfileLoading(false);
    }
  }

  async function handleLogout() {
    try { await authApi.logout(); } catch { /* 서버 오류여도 클라이언트 로그아웃 진행 */ }
    logout();
    navigate("/");
  }

  async function handlePasswordChange() {
    const { current, next, confirm } = pwForm;
    if (!current || !next || !confirm) { setPwError("모든 항목을 입력해주세요."); return; }
    if (next.length < 8) { setPwError("새 비밀번호는 8자 이상이어야 합니다."); return; }
    if (next !== confirm) { setPwError("새 비밀번호가 일치하지 않습니다."); return; }
    setPwError("");
    setPwLoading(true);
    try {
      await authApi.changePassword({ current_password: current, new_password: next });
      setPwSuccess(true);
      setPwForm({ current: "", next: "", confirm: "" });
      setTimeout(() => setPwSuccess(false), 3000);
    } catch (e) {
      setPwError(e instanceof Error ? e.message : "비밀번호 변경에 실패했습니다.");
    } finally {
      setPwLoading(false);
    }
  }

  async function handleDeleteAccount() {
    if (!deletePassword) { setDeleteError("비밀번호를 입력해주세요."); return; }
    setDeleteLoading(true);
    try {
      await authApi.deleteAccount();
      logout();
      navigate("/");
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "회원 탈퇴에 실패했습니다.");
    } finally {
      setDeleteLoading(false);
    }
  }

  // 아바타 이니셜
  const initial = user?.name ? user.name.charAt(0).toUpperCase() : "?";

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="04 · 마이페이지 (REQ-USR-01)" />
      <TopNav />
      <main className="flex flex-1 flex-col items-start gap-[32px] p-[32px] md:flex-row md:justify-center">
        {/* 왼쪽: 프로필 + 메뉴 */}
        <div className="flex w-full flex-col gap-[16px] md:w-[360px]">
          {/* 프로필 카드 */}
          <div className="flex flex-col items-center gap-[12px] rounded-lg border border-border bg-bg shadow-card p-[24px]">
            <div className="flex h-[80px] w-[80px] items-center justify-center rounded-full bg-accent/20">
              <span className="text-2xl font-bold text-accent">{initial}</span>
            </div>
            <p className="text-lg font-bold text-text-primary">{user?.name ?? "—"}</p>
            <p className="text-sm text-text-secondary">{user?.email ?? "—"}</p>
            <Tag label="KiniQ" />
          </div>

          {/* 메뉴 리스트 */}
          <div className="flex flex-col gap-[8px]">
            <ListItem
              icon={Heart}
              title="내 건강 데이터"
              subtitle="건강검진 결과 및 추이 확인"
              onClick={() => navigate("/health-check-history")}
            />
            <ListItem
              icon={ClipboardList}
              title="생활습관 문진"
              subtitle="흡연·음주·운동·가족력 등 문진 이력 확인"
              onClick={() => navigate("/lifestyle-survey-history")}
            />
            <ListItem
              icon={Bell}
              title="알림 설정"
              subtitle="푸시 알림 및 리마인더 관리"
              onClick={() => navigate("/notifications")}
            />
            <ListItem
              icon={Settings}
              title="계정 관리"
              subtitle="비밀번호 변경 및 계정 설정"
              onClick={() => setPanel("account")}
              className={panel === "account" ? "border-accent bg-accent/5" : ""}
            />
            <ListItem
              icon={Headphones}
              title="고객센터"
              subtitle="문의 및 FAQ"
              onClick={() => navigate("/faq")}
            />
          </div>
        </div>

        {/* 오른쪽: 패널 */}
        <div className="flex w-full flex-col gap-[16px] md:w-[480px]">
          {panel === "logout" && (
            <div className="flex flex-col items-center gap-[24px] rounded-lg border border-border bg-bg shadow-card p-[40px]">
              <LogOut size={48} className="text-text-muted" />
              <div className="text-center">
                <p className="text-lg font-bold text-text-primary">로그아웃</p>
                <p className="mt-[8px] text-sm text-text-secondary">
                  계정에서 로그아웃하시겠습니까?
                </p>
              </div>
              <button
                onClick={handleLogout}
                className="flex h-[44px] w-full items-center justify-center rounded-md border border-border bg-bg px-[16px] text-sm font-bold text-text-primary hover:bg-bg-alt"
              >
                로그아웃
              </button>
              <p className="text-xs text-text-muted text-center">
                좌측 메뉴에서 계정 관리를 눌러 비밀번호 변경 또는 회원 탈퇴를 할 수 있습니다.
              </p>
            </div>
          )}

          {panel === "account" && (
            <div className="flex flex-col gap-[16px]">
              {/* 회원정보 수정 (팀원 피드백 #2) */}
              <div className="rounded-lg border border-border bg-bg shadow-card p-[24px]">
                <h2 className="mb-[16px] flex items-center gap-[8px] text-lg font-bold text-text-primary">
                  <UserCog size={20} />
                  회원정보 수정
                </h2>
                <div className="flex flex-col gap-[12px]">
                  <TextInput
                    label="이름"
                    placeholder="홍길동"
                    value={profileForm.name}
                    onChange={(e) => setProfileForm((p) => ({ ...p, name: e.target.value }))}
                  />
                  <TextInput
                    label="생년월일"
                    placeholder="YYYY-MM-DD"
                    value={profileForm.birthday}
                    onChange={(e) => setProfileForm((p) => ({ ...p, birthday: formatBirth(e.target.value) }))}
                    inputMode="numeric"
                    maxLength={10}
                  />
                  <TextInput
                    label="전화번호"
                    placeholder="010-1234-5678"
                    value={profileForm.phone_number}
                    onChange={(e) => setProfileForm((p) => ({ ...p, phone_number: formatPhone(e.target.value) }))}
                    inputMode="tel"
                    maxLength={13}
                  />
                  {profileError && (
                    <p className="rounded-sm bg-danger/10 px-[12px] py-[8px] text-sm text-danger">{profileError}</p>
                  )}
                  {profileSuccess && (
                    <p className="rounded-sm bg-success/10 px-[12px] py-[8px] text-sm text-success">회원정보가 수정되었습니다.</p>
                  )}
                  <BtnPrimary label="회원정보 수정" loading={profileLoading} onClick={handleProfileSave} />
                </div>
              </div>

              {/* 비밀번호 변경 */}
              <div className="rounded-lg border border-border bg-bg shadow-card p-[24px]">
                <h2 className="mb-[16px] flex items-center gap-[8px] text-lg font-bold text-text-primary">
                  <KeyRound size={20} />
                  비밀번호 변경
                </h2>
                <div className="flex flex-col gap-[12px]">
                  <TextInput
                    label="현재 비밀번호"
                    placeholder="현재 비밀번호"
                    type="password"
                    value={pwForm.current}
                    onChange={(e) => setPwForm((p) => ({ ...p, current: e.target.value }))}
                  />
                  <TextInput
                    label="새 비밀번호"
                    placeholder="8자 이상, 영문·숫자·특수문자 포함"
                    type="password"
                    value={pwForm.next}
                    onChange={(e) => setPwForm((p) => ({ ...p, next: e.target.value }))}
                  />
                  <TextInput
                    label="새 비밀번호 확인"
                    placeholder="새 비밀번호 재입력"
                    type="password"
                    value={pwForm.confirm}
                    onChange={(e) => setPwForm((p) => ({ ...p, confirm: e.target.value }))}
                  />
                  {pwError && (
                    <p className="rounded-sm bg-danger/10 px-[12px] py-[8px] text-sm text-danger">{pwError}</p>
                  )}
                  {pwSuccess && (
                    <p className="rounded-sm bg-success/10 px-[12px] py-[8px] text-sm text-success">비밀번호가 변경되었습니다.</p>
                  )}
                  <BtnPrimary label="비밀번호 변경" loading={pwLoading} onClick={handlePasswordChange} />
                </div>
              </div>

              {/* 회원 탈퇴 */}
              <div className="rounded-lg border border-danger bg-bg shadow-card p-[24px]">
                <h2 className="mb-[8px] flex items-center gap-[8px] text-lg font-bold text-danger">
                  <UserX size={20} />
                  회원 탈퇴
                </h2>
                <p className="mb-[16px] text-sm text-text-secondary">
                  탈퇴 시 모든 건강 데이터와 챌린지 기록이 영구 삭제되며 복구할 수 없습니다. 신중하게 결정해주세요.
                </p>
                <TextInput
                  label="비밀번호 확인"
                  placeholder="현재 비밀번호를 입력하세요"
                  type="password"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                />
                {deleteError && (
                  <p className="mt-[8px] rounded-sm bg-danger/10 px-[12px] py-[8px] text-sm text-danger">{deleteError}</p>
                )}
                <button
                  onClick={handleDeleteAccount}
                  disabled={deleteLoading}
                  className="mt-[12px] flex h-[44px] w-full items-center justify-center rounded-md bg-danger px-[16px] py-[12px] text-sm font-bold text-bg disabled:opacity-50"
                >
                  {deleteLoading ? "처리 중..." : "회원 탈퇴"}
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
