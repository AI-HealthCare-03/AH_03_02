interface Props {
  onStart: () => void;
}

export function OnboardView({ onStart }: Props) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center">
      <div className="mb-6 flex h-[72px] w-[72px] items-center justify-center rounded-[24px] bg-track-wellness-bg text-[32px]">
        🫘
      </div>
      <h1 className="mb-2.5 text-[26px] font-semibold tracking-tight text-text-primary">콩팥 챌린지</h1>
      <p className="mb-10 text-[15px] leading-relaxed text-text-secondary">
        매일 작은 실천으로<br />신장 건강을 지켜보세요.
        <br /><br />본 서비스는 처방·진단을 대체하지 않으며<br />의료진의 지침을 우선으로 따르세요.
      </p>
      <button
        onClick={onStart}
        className="w-full max-w-[320px] rounded-lg bg-accent px-8 py-3.5 text-base font-medium text-bg shadow-sm transition-colors hover:bg-accent-hover"
      >
        시작하기
      </button>
    </div>
  );
}
