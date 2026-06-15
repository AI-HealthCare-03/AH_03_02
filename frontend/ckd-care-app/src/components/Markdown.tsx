import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * 챗봇 답변·리포트 AI 가이드 공용 마크다운 렌더러.
 * 서버가 내려주는 마크다운(### 제목, **굵게**, - 리스트)을 디자인이 적용된 텍스트로 표시한다.
 * 프로젝트 Tailwind 토큰(text-text-primary 등)에 맞춘 컴포넌트 매핑.
 */
export function Markdown({ children }: { children: string }) {
  // 옛 답변·가이드의 box-drawing 구분선(─────/———)을 마크다운 hr로 정규화한다.
  // 서버는 신규 답변에 ---(hr)를 쓰지만, 이미 DB에 캐시된 답변은 ─ 문자라
  // 면책이 가로선과 한 줄로 붙어 보이던 문제를 프론트에서 함께 해결(기존·신규 호환).
  const normalized = children.replace(/\n*[─—]{3,}\n*/g, "\n\n---\n\n");
  return (
    <div className="text-sm leading-[1.7] text-text-primary">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h2 className="mt-4 mb-2 text-base font-bold text-text-primary">{children}</h2>,
          h2: ({ children }) => <h3 className="mt-4 mb-2 text-base font-bold text-text-primary">{children}</h3>,
          h3: ({ children }) => <h4 className="mt-3 mb-1.5 text-sm font-bold text-text-primary">{children}</h4>,
          h4: ({ children }) => <h5 className="mt-3 mb-1.5 text-sm font-bold text-text-secondary">{children}</h5>,
          p: ({ children }) => <p className="mb-2 leading-[1.7] text-text-primary">{children}</p>,
          ul: ({ children }) => <ul className="mb-2 flex list-disc flex-col gap-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="mb-2 flex list-decimal flex-col gap-1 pl-5">{children}</ol>,
          li: ({ children }) => <li className="leading-[1.6] text-text-primary">{children}</li>,
          strong: ({ children }) => <strong className="font-bold text-text-primary">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer" className="text-accent underline">
              {children}
            </a>
          ),
          hr: () => <hr className="my-3 border-border" />,
          code: ({ children }) => (
            <code className="rounded-sm bg-bg-alt px-1 py-0.5 text-[13px] text-text-primary">{children}</code>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-border pl-3 text-text-secondary">{children}</blockquote>
          ),
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
