import { Coins } from "lucide-react";

interface Props {
  amount: number | null; // null이면 미표시
  onClose: () => void;
}

/**
 * 필수 체크리스트 항목 1개 완료(+5pt) 시 뜨는 가벼운 중앙 모달.
 * 컨페티·적립표 없이 포인트만 보여주고 탭/확인으로 닫는다(자동 닫힘 없음).
 */
export function PointPopModal({ amount, onClose }: Props) {
  if (amount === null) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="relative rounded-xl bg-bg p-6 text-center shadow-2xl"
        style={{ width: "min(320px, calc(100vw - 32px))" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary-soft">
          <Coins size={32} className="text-primary" />
        </div>
        <p className="mt-3 text-lg font-bold text-text-primary">+{amount}pt 적립</p>
        <p className="mt-1 text-sm text-text-secondary">매일 필수 체크 완료!</p>
        <button
          onClick={onClose}
          className="mt-4 w-full rounded-md bg-accent py-2.5 text-sm font-bold text-bg hover:bg-accent/90"
        >
          확인
        </button>
      </div>
    </div>
  );
}
