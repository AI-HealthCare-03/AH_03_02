import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Coins, History, ShieldCheck, Zap, PawPrint, Lock, Info } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { gamificationApi, pointsApi, type InventoryResponse, type ItemCode, type MascotResponse } from "../api/gamification";

interface ShopItem {
  code: ItemCode;
  name: string;
  price: number;
  description: string;
  maxQty?: number;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  requiredStage?: number; // 동물 스킨 진화 게이팅 — 누적 최고 단계 >= 이 값이어야 구매 가능
}

const ITEMS: { [category: string]: ShopItem[] } = {
  실용: [
    {
      code: "PROTECT",
      name: "스트릭 보호권",
      price: 500,
      description: "체크인 못 한 날 1회 스트릭 유지. 최대 2개 보유.",
      maxQty: 2,
      icon: ShieldCheck,
    },
    {
      code: "MINI_BOOSTER",
      name: "회복 미니알 부스터",
      price: 200,
      description: "쉬어가기 모드 진입을 7→9일로 연장. 보유 1개만 (사용 후 재구매).",
      maxQty: 1,
      icon: Zap,
    },
  ],
  "동물 스킨 (1단계)": [
    { code: "SKIN_TURTLE_1", name: "거북이 (1단계)", price: 400, description: "느긋한 거북이로 변신.", maxQty: 1, icon: PawPrint, requiredStage: 1 },
    { code: "SKIN_PENGUIN_1", name: "펭귄 (1단계)", price: 400, description: "귀여운 펭귄으로 변신.", maxQty: 1, icon: PawPrint, requiredStage: 1 },
    { code: "SKIN_SQUIRREL_1", name: "다람쥐 (1단계)", price: 400, description: "활발한 다람쥐로 변신.", maxQty: 1, icon: PawPrint, requiredStage: 1 },
    { code: "SKIN_RABBIT_1", name: "토끼 (1단계)", price: 400, description: "발랄한 토끼로 변신.", maxQty: 1, icon: PawPrint, requiredStage: 1 },
    { code: "SKIN_PANDA_1", name: "판다 (1단계)", price: 400, description: "느긋한 판다로 변신.", maxQty: 1, icon: PawPrint, requiredStage: 1 },
  ],
  "동물 스킨 (2단계)": [
    { code: "SKIN_TURTLE_2", name: "거북이 (2단계)", price: 700, description: "성장한 거북이 모습. 2단계 진화 후 해제.", maxQty: 1, icon: PawPrint, requiredStage: 2 },
    { code: "SKIN_PENGUIN_2", name: "펭귄 (2단계)", price: 700, description: "성장한 펭귄 모습. 2단계 진화 후 해제.", maxQty: 1, icon: PawPrint, requiredStage: 2 },
    { code: "SKIN_SQUIRREL_2", name: "다람쥐 (2단계)", price: 700, description: "성장한 다람쥐 모습. 2단계 진화 후 해제.", maxQty: 1, icon: PawPrint, requiredStage: 2 },
    { code: "SKIN_RABBIT_2", name: "토끼 (2단계)", price: 700, description: "성장한 토끼 모습. 2단계 진화 후 해제.", maxQty: 1, icon: PawPrint, requiredStage: 2 },
    { code: "SKIN_PANDA_2", name: "판다 (2단계)", price: 700, description: "성장한 판다 모습. 2단계 진화 후 해제.", maxQty: 1, icon: PawPrint, requiredStage: 2 },
  ],
  "동물 스킨 (완전체)": [
    { code: "SKIN_TURTLE_3", name: "거북이 (완전체)", price: 1200, description: "완전체 거북이. 3단계 진화 후 해제.", maxQty: 1, icon: PawPrint, requiredStage: 3 },
    { code: "SKIN_PENGUIN_3", name: "펭귄 (완전체)", price: 1200, description: "완전체 펭귄. 3단계 진화 후 해제.", maxQty: 1, icon: PawPrint, requiredStage: 3 },
    { code: "SKIN_SQUIRREL_3", name: "다람쥐 (완전체)", price: 1200, description: "완전체 다람쥐. 3단계 진화 후 해제.", maxQty: 1, icon: PawPrint, requiredStage: 3 },
    { code: "SKIN_RABBIT_3", name: "토끼 (완전체)", price: 1200, description: "완전체 토끼. 3단계 진화 후 해제.", maxQty: 1, icon: PawPrint, requiredStage: 3 },
    { code: "SKIN_PANDA_3", name: "판다 (완전체)", price: 1200, description: "완전체 판다. 3단계 진화 후 해제.", maxQty: 1, icon: PawPrint, requiredStage: 3 },
  ],
};

export function ShopPage() {
  const [balance, setBalance] = useState(0);
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [mascot, setMascot] = useState<MascotResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState<ItemCode | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function reload() {
    const [bal, inv, m] = await Promise.all([
      pointsApi.getBalance(),
      gamificationApi.getInventory(),
      gamificationApi.getMascot(),
    ]);
    setBalance(bal.balance);
    setInventory(inv);
    setMascot(m);
  }

  useEffect(() => {
    reload()
      .catch(() => setMessage({ kind: "err", text: "데이터를 불러오지 못했습니다." }))
      .finally(() => setLoading(false));
  }, []);

  async function handlePurchase(code: ItemCode) {
    setPurchasing(code);
    setMessage(null);
    try {
      const result = await pointsApi.purchase(code);
      setBalance(result.new_balance);
      setMessage({ kind: "ok", text: `구매 완료! ${result.spent}pt 차감 (잔액 ${result.new_balance}pt)` });
      await reload();
    } catch (e) {
      setMessage({ kind: "err", text: e instanceof Error ? e.message : "구매에 실패했습니다." });
    } finally {
      setPurchasing(null);
    }
  }

  function qtyOf(code: ItemCode): number {
    return inventory?.items.find((i) => i.item_code === code)?.quantity ?? 0;
  }

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="상점 (REQ-CHAL-004)" />
        <TopNav />
        <main className="flex flex-1 items-center justify-center text-text-secondary">로딩 중...</main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="상점 (REQ-CHAL-004)" />
      <TopNav />
      <main className="flex flex-1 flex-col p-[32px]">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="text-2xl font-bold text-text-primary">상점</h1>
          <div className="flex items-center gap-[12px]">
            <div className="flex items-center gap-[6px] rounded-md bg-amber-50 px-[12px] py-[6px]">
              <Coins size={18} className="text-amber-500" />
              <span className="text-lg font-bold text-amber-700">{balance.toLocaleString()}</span>
              <span className="text-xs text-amber-600">pt</span>
            </div>
            <Link
              to="/points/transactions"
              className="flex items-center gap-[4px] rounded-md border border-border px-[10px] py-[6px] text-sm text-text-secondary transition-colors hover:border-accent hover:text-accent"
            >
              <History size={14} />
              거래 이력
            </Link>
          </div>
        </div>

        {message && (
          <div
            className={`mt-4 rounded-sm px-3 py-2 text-sm ${
              message.kind === "ok" ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
            }`}
          >
            {message.text}
          </div>
        )}

        {Object.entries(ITEMS).map(([category, items], idx) => (
          <section key={category} className="mt-[24px]">
            <h2 className="mb-[12px] text-lg font-bold text-text-primary">{category}</h2>
            {/* 동물 스킨 카테고리 첫 등장 직후에만 안내 박스 */}
            {idx > 0 && category.startsWith("동물 스킨 (1") && (
              <div className="mb-[12px] flex items-start gap-[8px] rounded-md border border-info bg-info/5 px-[12px] py-[10px] text-xs leading-[1.5] text-text-secondary">
                <Info size={14} className="mt-[2px] shrink-0 text-info" />
                <div>
                  <span className="font-bold text-text-primary">동물 스킨은 외형 고정입니다.</span>{" "}
                  체크인으로 진화하는 건 <b>본래 캐릭터</b>(부화 시 추첨된 종)뿐이에요. 스킨을 장착해도 본래 캐릭터는 계속 자라요 — <b>스킨을 해제하면 진화된 모습</b>을 볼 수 있어요. 더 높은 단계 외형을 원하면 그 단계 스킨을 따로 구매하세요.
                </div>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-[12px]">
              {items.map((item) => {
                const owned = qtyOf(item.code);
                const isCapped = item.maxQty !== undefined && owned >= item.maxQty;
                const cantAfford = balance < item.price;
                const maxStage = mascot?.max_stage_ever ?? 0;
                const isLocked = item.requiredStage !== undefined && maxStage < item.requiredStage;
                const disabled = isCapped || cantAfford || isLocked || purchasing === item.code;
                const Icon = item.icon;
                return (
                  <div
                    key={item.code}
                    className={`flex items-start gap-[12px] rounded-lg border p-[16px] ${
                      isLocked ? "border-border bg-bg-alt opacity-70" : "border-border bg-bg shadow-card"
                    }`}
                  >
                    <Icon size={28} className="shrink-0 text-text-secondary" />
                    <div className="flex-1">
                      <div className="flex items-start justify-between">
                        <p className="text-sm font-bold text-text-primary">{item.name}</p>
                        {owned > 0 && (
                          <span className="rounded-md bg-success/20 px-2 py-0.5 text-xs font-bold text-success">
                            보유 {owned}{item.maxQty ? `/${item.maxQty}` : ""}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-text-muted">{item.description}</p>
                      {isLocked && (
                        <p className="mt-1 flex items-center gap-1 text-xs font-bold text-warning">
                          <Lock size={12} />
                          {item.requiredStage}단계 진화 시 잠금 해제 (현재 누적 최고 {maxStage}단계)
                        </p>
                      )}
                      <button
                        onClick={() => handlePurchase(item.code)}
                        disabled={disabled}
                        title={isLocked ? `${item.requiredStage}단계 진화 후 구매 가능` : undefined}
                        className="mt-2 flex items-center gap-1 rounded-lg bg-accent px-3 py-1.5 text-sm font-bold text-bg shadow-sm transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-accent"
                      >
                        {isLocked ? <Lock size={14} /> : <Coins size={14} />}
                        {isLocked
                          ? `잠김 (${item.requiredStage}단계 필요)`
                          : isCapped
                          ? "보유 최대"
                          : cantAfford
                          ? `${item.price}pt (부족)`
                          : `${item.price}pt 구매`}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </main>
    </div>
  );
}
