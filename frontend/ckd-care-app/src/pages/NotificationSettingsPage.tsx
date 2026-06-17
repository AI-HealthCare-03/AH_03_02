import { useEffect, useState } from "react";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { BtnPrimary } from "../components/BtnPrimary";
import { notificationApi, type NotificationSetting } from "../api/notification";

function Toggle({ enabled, onChange }: { enabled: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      className={`flex h-[24px] w-[48px] items-center rounded-full p-[2px] transition-colors ${
        enabled ? "justify-end bg-success" : "justify-start bg-placeholder"
      }`}
    >
      <div className="h-[20px] w-[20px] rounded-full bg-bg" />
    </button>
  );
}

function ToggleItem({
  title,
  subtitle,
  enabled,
  onToggle,
  disabled = false,
}: {
  title: string;
  subtitle: string;
  enabled: boolean;
  onToggle: () => void;
  disabled?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between rounded-sm bg-bg-alt p-[12px] ${disabled ? "opacity-40" : ""}`}>
      <div className="flex flex-col gap-[2px]">
        <p className="text-sm font-bold text-text-primary">{title}</p>
        <p className="text-xs text-text-secondary">{subtitle}</p>
      </div>
      <Toggle enabled={enabled} onChange={disabled ? () => {} : onToggle} />
    </div>
  );
}

const DEFAULT_SETTINGS: NotificationSetting = {
  challenge_joined_enabled: true,
  checkin_done_enabled: true,
  challenge_completed_enabled: true,
  challenge_reminder_enabled: true,
};

export function NotificationSettingsPage() {
  const [settings, setSettings] = useState<NotificationSetting>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setLoading(true);
    notificationApi
      .getSettings()
      .then(setSettings)
      .catch(() => setError("설정을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  function toggle(key: keyof NotificationSetting) {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const updated = await notificationApi.updateSettings(settings);
      setSettings(updated);
      setSaved(true);
    } catch {
      setError("저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="16 · 알림 설정 (REQ-NOTI-003)" />
      <TopNav />

      <main className="flex flex-1 flex-col items-center p-[32px]">
        <div className="flex w-[600px] flex-col gap-[16px] rounded-lg border border-border bg-bg p-[32px] shadow-card">
          <h1 className="text-xl font-bold text-text-primary">알림 설정</h1>

          {loading && <p className="text-sm text-text-secondary">불러오는 중...</p>}

          {error && (
            <div className="rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>
          )}

          {saved && (
            <div className="rounded-sm bg-success/10 px-3 py-2 text-sm text-success">저장됐습니다.</div>
          )}

          {!loading && (
            <>
              <ToggleItem
                title="챌린지 참여 알림"
                subtitle="새 챌린지를 시작할 때 알림을 받습니다."
                enabled={settings.challenge_joined_enabled}
                onToggle={() => toggle("challenge_joined_enabled")}
              />
              <ToggleItem
                title="체크인 완료 알림"
                subtitle="챌린지 체크인 후 연속 달성 현황을 알립니다."
                enabled={settings.checkin_done_enabled}
                onToggle={() => toggle("checkin_done_enabled")}
              />
              <ToggleItem
                title="챌린지 완료 알림"
                subtitle="챌린지를 완주했을 때 알림을 받습니다."
                enabled={settings.challenge_completed_enabled}
                onToggle={() => toggle("challenge_completed_enabled")}
              />
              <ToggleItem
                title="챌린지 리마인더"
                subtitle="오늘 체크인을 하지 않은 경우 저녁에 알립니다."
                enabled={settings.challenge_reminder_enabled}
                onToggle={() => toggle("challenge_reminder_enabled")}
              />
              <ToggleItem
                title="일일 퀴즈 (P2)"
                subtitle="매일 아침 건강 O/X 퀴즈 1문항 — 추후 지원"
                enabled={false}
                onToggle={() => {}}
                disabled
              />
            </>
          )}

          <BtnPrimary
            label="저장"
            className="w-full"
            height={48}
            loading={saving}
            onClick={handleSave}
          />
        </div>
      </main>
    </div>
  );
}
