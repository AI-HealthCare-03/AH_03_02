import { useEffect, useState } from "react";
import { Sparkles, Palette, Edit2, Check, X } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import {
  ANIMAL_SKIN_TO_SPECIES,
  ANIMAL_SKIN_TO_STAGE,
  gamificationApi,
  SKIN_LABEL,
  SPECIES_LABEL,
  type EggHistoryItem,
  type InventoryItem,
  type ItemCode,
  type MascotResponse,
} from "../api/gamification";
import { CharacterImage } from "../components/CharacterImage";

const SKIN_ITEM_CODES: ItemCode[] = [
  "SKIN_S_BLUE",
  "SKIN_S_GREEN",
  "SKIN_M_RED",
  "SKIN_M_PURPLE",
  "SKIN_L_GOLD",
  "SKIN_TURTLE_1", "SKIN_PENGUIN_1", "SKIN_SQUIRREL_1", "SKIN_RABBIT_1", "SKIN_PANDA_1",
  "SKIN_TURTLE_2", "SKIN_PENGUIN_2", "SKIN_SQUIRREL_2", "SKIN_RABBIT_2", "SKIN_PANDA_2",
  "SKIN_TURTLE_3", "SKIN_PENGUIN_3", "SKIN_SQUIRREL_3", "SKIN_RABBIT_3", "SKIN_PANDA_3",
];

export function CollectionPage() {
  const [characters, setCharacters] = useState<EggHistoryItem[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [mascot, setMascot] = useState<MascotResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // 캐릭터 이름 변경 상태
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");

  // 메시지
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function reload() {
    const [hist, inv, m] = await Promise.all([
      gamificationApi.getEggHistory(),
      gamificationApi.getInventory(),
      gamificationApi.getMascot(),
    ]);
    setCharacters(hist.items);
    setInventory(inv.items);
    setMascot(m);
  }

  useEffect(() => {
    reload()
      .catch((e) => setError(e instanceof Error ? e.message : "데이터를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  function startEdit(item: EggHistoryItem) {
    setEditingId(item.egg_no);
    setEditName(item.character_name ?? "");
  }

  function cancelEdit() {
    setEditingId(null);
    setEditName("");
  }

  async function saveEdit(eggId: number) {
    if (!editName.trim()) return;
    try {
      await gamificationApi.renameCharacter(eggId, editName.trim());
      await reload();
      setEditingId(null);
      setMessage({ kind: "ok", text: "이름이 변경됐어요." });
    } catch (e) {
      setMessage({ kind: "err", text: e instanceof Error ? e.message : "이름 변경 실패" });
    }
  }

  async function handleEquip(code: ItemCode | null) {
    try {
      await gamificationApi.equipSkin(code);
      await reload();
      setMessage({
        kind: "ok",
        text: code ? `${SKIN_LABEL[code as keyof typeof SKIN_LABEL]?.name} 장착됨` : "스킨 해제됨",
      });
    } catch (e) {
      setMessage({ kind: "err", text: e instanceof Error ? e.message : "스킨 변경 실패" });
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="컬렉션 (REQ-CHAL-004)" />
        <TopNav />
        <main className="flex flex-1 items-center justify-center text-text-secondary">로딩 중...</main>
      </div>
    );
  }

  const ownedSkins = inventory.filter(
    (i) => SKIN_ITEM_CODES.includes(i.item_code) && i.quantity > 0
  );
  const activeSkinCode = mascot?.skin_active ?? null;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="컬렉션 (REQ-CHAL-004)" />
      <TopNav />
      <main className="flex flex-1 flex-col p-[32px]">
        <h1 className="text-2xl font-bold text-text-primary">컬렉션</h1>
        <p className="mt-1 text-sm text-text-secondary">
          부화한 캐릭터들과 보유 스킨을 확인하고 장착할 수 있어요.
        </p>

        {error && <div className="mt-4 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>}
        {message && (
          <div
            className={`mt-4 rounded-sm px-3 py-2 text-sm ${
              message.kind === "ok" ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
            }`}
          >
            {message.text}
          </div>
        )}

        {/* 캐릭터 컬렉션 */}
        <section className="mt-[24px]">
          <h2 className="mb-[12px] text-lg font-bold text-text-primary">
            🎉 부화한 캐릭터 ({characters.length})
          </h2>
          {characters.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-bg px-[16px] py-[24px] text-center">
              <p className="text-sm text-text-muted">
                아직 부화한 캐릭터가 없어요. 체크인을 꾸준히 해서 알을 부화시켜보세요!
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-[16px]">
              {characters.map((c) => {
                const speciesName = c.species ? SPECIES_LABEL[c.species] : "알";
                const isEditing = editingId === c.egg_no;
                return (
                  <div
                    key={c.egg_no}
                    className="flex flex-col items-center gap-[8px] rounded-lg border border-border bg-bg shadow-card p-[16px]"
                  >
                    <div className="flex h-[100px] w-[100px] items-center justify-center rounded-full bg-amber-50">
                      <CharacterImage species={c.species} stage={1} size={88} emojiClass="text-5xl" />
                    </div>
                    <p className="text-xs text-text-muted">
                      {c.egg_no}번째 알 · {speciesName}
                    </p>
                    {isEditing ? (
                      <div className="flex w-full items-center gap-1">
                        <input
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          maxLength={30}
                          className="flex-1 rounded-sm border border-border px-2 py-1 text-sm"
                          autoFocus
                        />
                        <button
                          onClick={() => saveEdit(c.egg_no)}
                          className="rounded-sm bg-success p-1 text-bg"
                          aria-label="저장"
                        >
                          <Check size={14} />
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="rounded-sm bg-text-muted p-1 text-bg"
                          aria-label="취소"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1">
                        <p className="text-sm font-bold text-text-primary">{c.character_name}</p>
                        <button
                          onClick={() => startEdit(c)}
                          className="text-text-muted hover:text-text-secondary"
                          aria-label="이름 변경"
                        >
                          <Edit2 size={12} />
                        </button>
                      </div>
                    )}
                    <p className="text-xs text-text-muted">
                      {new Date(c.hatched_at).toLocaleDateString("ko-KR")} 부화
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* 스킨 컬렉션 */}
        <section className="mt-[32px]">
          <h2 className="mb-[12px] flex items-center gap-2 text-lg font-bold text-text-primary">
            <Palette size={18} />
            보유 스킨 ({ownedSkins.length})
          </h2>
          {ownedSkins.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-bg px-[16px] py-[24px] text-center">
              <p className="text-sm text-text-muted">아직 보유한 스킨이 없어요.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-[12px]">
              {/* 기본 외형 (스킨 해제) 옵션 */}
              <SkinCard
                code={null}
                label="기본 외형"
                color="bg-gray-100"
                active={activeSkinCode === null}
                onEquip={() => handleEquip(null)}
              />
              {ownedSkins.map((s) => {
                const info = SKIN_LABEL[s.item_code as keyof typeof SKIN_LABEL];
                if (!info) return null;
                return (
                  <SkinCard
                    key={s.item_code}
                    code={s.item_code}
                    label={info.name}
                    color={info.color}
                    active={activeSkinCode === s.item_code}
                    onEquip={() => handleEquip(s.item_code)}
                  />
                );
              })}
            </div>
          )}
        </section>

        {/* 상점 배너 — 항상 하단 고정 */}
        <section className="mt-[32px] mb-[16px]">
          <a
            href="/shop"
            className="flex items-center justify-between rounded-2xl bg-accent px-[24px] py-[28px] shadow-card active:opacity-90"
          >
            <div className="flex flex-col gap-[6px]">
              <span className="text-2xl font-bold text-white">🏬 상점 바로가기</span>
              <span className="text-base text-white/80">다양한 스킨을 구경해보세요!</span>
            </div>
            <span className="text-4xl text-white">›</span>
          </a>
        </section>
      </main>
    </div>
  );
}

function SkinCard({
  code,
  label,
  color,
  active,
  onEquip,
}: {
  code: ItemCode | null;
  label: string;
  color: string;
  active: boolean;
  onEquip: () => void;
}) {
  const animalSpecies = code ? ANIMAL_SKIN_TO_SPECIES[code] : null;
  const animalStage = code ? ANIMAL_SKIN_TO_STAGE[code] ?? 1 : 1;
  return (
    <div
      className={`flex flex-col items-center gap-[8px] rounded-lg border-2 p-[12px] ${
        active ? "border-accent bg-accent/5 shadow-card" : "border-border bg-bg shadow-card"
      }`}
    >
      <div className={`flex h-[60px] w-[60px] items-center justify-center overflow-hidden rounded-full ${color}`}>
        {animalSpecies ? (
          <CharacterImage species={animalSpecies} stage={animalStage} size={52} emojiClass="text-3xl" />
        ) : (
          <Sparkles size={24} className="text-text-secondary" />
        )}
      </div>
      <p className="text-xs font-bold text-text-primary text-center">{label}</p>
      {active ? (
        <span className="rounded-md bg-accent px-2 py-0.5 text-xs font-bold text-bg">장착 중</span>
      ) : (
        <button
          onClick={onEquip}
          className="rounded-sm border border-accent px-3 py-1 text-xs text-accent hover:bg-accent hover:text-bg"
        >
          장착
        </button>
      )}
      {code === null && <span className="text-xs text-text-muted">기본</span>}
    </div>
  );
}
