import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Coins, History, ShieldCheck, Zap, Palette, PawPrint } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { gamificationApi, pointsApi, type InventoryResponse, type ItemCode } from "../api/gamification";

interface ShopItem {
  code: ItemCode;
  name: string;
  price: number;
  description: string;
  maxQty?: number;
  icon: React.ComponentType<{ size?: number; className?: string }>;
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
  스킨소: [
    { code: "SKIN_S_BLUE", name: "블루 스킨 (소)", price: 300, description: "기본 파랑 색상", maxQty: 1, icon: Palette },
    { code: "SKIN_S_GREEN", name: "그린 스킨 (소)", price: 300, description: "기본 초록 색상", maxQty: 1, icon: Palette },
  ],
  스킨중: [
    { code: "SKIN_M_RED", name: "레드 스킨 (중)", price: 700, description: "빨강 + 이펙트", maxQty: 1, icon: Palette },
    { code: "SKIN_M_PURPLE", name: "퍼플 스킨 (중)", price: 700, description: "보라 + 이펙트", maxQty: 1, icon: Palette },
  ],
  스킨대: [{ code: "SKIN_L_GOLD", name: "골드 스킨 (대)", price: 1200, description: "시즌 한정", maxQty: 1, icon: Palette }],
  "동물 스킨 (1단계)": [
    { code: "SKIN_TURTLE_1", name: "거북이 (1단계)", price: 400, description: "느긋한 거북이로 변신. 장착 시 알이 거북이 1단계로 표시.", maxQty: 1, icon: PawPrint },
    { code: "SKIN_PENGUIN_1", name: "펭귄 (1단계)", price: 400, description: "귀여운 펭귄으로 변신. 장착 시 알이 펭귄 1단계로 표시.", maxQty: 1, icon: PawPrint },
    { code: "SKIN_SQUIRREL_1", name: "다람쥐 (1단계)", price: 400, description: "활발한 다람쥐로 변신. 장착 시 알이 다람쥐 1단계로 표시.", maxQty: 1, icon: PawPrint },
    { code: "SKIN_RABBIT_1", name: "토끼 (1단계)", price: 400, description: "발랄한 토끼로 변신. 장착 시 알이 토끼 1단계로 표시.", maxQty: 1, icon: PawPrint },
    { code: "SKIN_PANDA_1", name: "판다 (1단계)", price: 400, description: "느긋한 판다로 변신. 장착 시 알이 판다 1단계로 표시.", maxQty: 1, icon: PawPrint },
  ],
};

export function ShopPage() {
  const [balance, setBalance] = useState(0);
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState<ItemCode | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function reload() {
    const [bal, inv] = await Promise.all([pointsApi.getBalance(), gamificationApi.getInventory()]);
    setBalance(bal.balance);
    setInventory(inv);
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
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-text-primary">상점</h1>
          <div className="flex items-center gap-[12px]">
            <div className="flex items-center gap-[6px] rounded-md bg-amber-50 px-[12px] py-[6px]">
              <Coins size={18} className="text-amber-500" />
              <span className="text-lg font-bold text-amber-700">{balance.toLocaleString()}</span>
              <span className="text-xs text-amber-600">pt</span>
            </div>
            <Link
              to="/points/transactions"
              className="flex items-center gap-[4px] rounded-md border border-border px-[10px] py-[6px] text-sm text-text-secondary hover:bg-bg"
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

        {Object.entries(ITEMS).map(([category, items]) => (
          <section key={category} className="mt-[24px]">
            <h2 className="mb-[12px] text-lg font-bold text-text-primary">{category}</h2>
            <div className="grid grid-cols-2 gap-[12px]">
              {items.map((item) => {
                const owned = qtyOf(item.code);
                const isCapped = item.maxQty !== undefined && owned >= item.maxQty;
                const cantAfford = balance < item.price;
                const disabled = isCapped || cantAfford || purchasing === item.code;
                const Icon = item.icon;
                return (
                  <div key={item.code} className="flex items-start gap-[12px] rounded-md border border-border bg-bg p-[16px]">
                    <Icon size={28} className="shrink-0 text-text-secondary" />
                    <div className="flex-1">
                      <div className="flex items-start justify-between">
                        <p className="text-sm font-bold text-text-primary">{item.name}</p>
                        {owned > 0 && (
                          <span className="rounded-full bg-success/20 px-2 py-0.5 text-xs font-bold text-success">
                            보유 {owned}{item.maxQty ? `/${item.maxQty}` : ""}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-text-muted">{item.description}</p>
                      <button
                        onClick={() => handlePurchase(item.code)}
                        disabled={disabled}
                        className="mt-2 flex items-center gap-1 rounded-md border border-accent px-3 py-1.5 text-sm text-accent hover:bg-accent hover:text-bg disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-accent"
                      >
                        <Coins size={14} />
                        {isCapped ? "보유 최대" : cantAfford ? `${item.price}pt (부족)` : `${item.price}pt 구매`}
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
