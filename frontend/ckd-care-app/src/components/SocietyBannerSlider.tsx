import { useEffect, useRef, useState } from "react";

// 학회 유튜브 배너 — 4초 자동 전환·순환(loop). 공식 채널 URL.
const SOCIETY_BANNERS: { title: string; url: string }[] = [
  { title: "대한신장학회 유튜브 채널", url: "https://www.youtube.com/@kidney_KSN" },
  { title: "대한고혈압학회 유튜브 채널", url: "https://www.youtube.com/@ksh1609" },
  { title: "대한당뇨학회 유튜브 채널", url: "https://www.youtube.com/@korean_diabetes_association" },
];
const INTERVAL_MS = 4000;

export function SocietyBannerSlider() {
  const [idx, setIdx] = useState(0);
  const paused = useRef(false);
  const n = SOCIETY_BANNERS.length;

  useEffect(() => {
    const t = setInterval(() => {
      if (!paused.current) setIdx((i) => (i + 1) % n);
    }, INTERVAL_MS);
    return () => clearInterval(t);
  }, [n]);

  const go = (d: number) => setIdx((i) => (i + d + n) % n);
  const cur = SOCIETY_BANNERS[idx];

  return (
    <div
      className="relative flex items-center gap-2 rounded-md border border-border bg-bg p-4"
      onMouseEnter={() => {
        paused.current = true;
      }}
      onMouseLeave={() => {
        paused.current = false;
      }}
    >
      <button
        type="button"
        onClick={() => go(-1)}
        aria-label="이전 배너"
        className="shrink-0 rounded px-2 py-1 text-lg text-text-muted hover:bg-bg-alt"
      >
        ‹
      </button>
      <a
        href={cur.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex flex-1 flex-col items-center gap-1 py-1 text-center transition-colors hover:text-accent"
      >
        <span className="text-sm font-bold text-text-primary">{cur.title}</span>
        <span className="text-xs text-text-muted">유튜브에서 보기 ↗</span>
      </a>
      <button
        type="button"
        onClick={() => go(1)}
        aria-label="다음 배너"
        className="shrink-0 rounded px-2 py-1 text-lg text-text-muted hover:bg-bg-alt"
      >
        ›
      </button>
      <div className="absolute bottom-2 left-1/2 flex -translate-x-1/2 gap-1">
        {SOCIETY_BANNERS.map((b, i) => (
          <button
            key={b.title}
            type="button"
            aria-label={`배너 ${i + 1}`}
            onClick={() => setIdx(i)}
            className={`h-1.5 w-1.5 rounded-full ${i === idx ? "bg-accent" : "bg-border"}`}
          />
        ))}
      </div>
    </div>
  );
}
