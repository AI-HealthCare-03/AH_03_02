import { Bot, Send, ThumbsDown, ThumbsUp, User as UserIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { askStream, chatApi, type FeedbackRating } from "../api/chat";
import { Markdown } from "../components/Markdown";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string;
  messageId?: number; // 어시스턴트 답변의 서버 id (피드백 연결용)
  feedback?: FeedbackRating; // 사용자가 남긴 피드백 (없으면 미평가)
}

const QUESTION_MAX = 2000;

const SUGGESTED_QUESTIONS = [
  "만성콩팥병 초기에 피해야 할 음식은 무엇인가요?",
  "혈압을 낮추는 데 효과적인 생활습관을 알려주세요.",
  "수면 부족이 신장에 어떤 영향을 주나요?",
];

export function RAGChatbotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0); // 답변 생성 경과 시간(초)
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  // 생성 중 경과 초 카운트 (로딩 표시용)
  useEffect(() => {
    if (!loading) return;
    const timer = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(timer);
  }, [loading]);

  async function send(question: string) {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    if (trimmed.length > QUESTION_MAX) {
      setError(`질문은 ${QUESTION_MAX}자 이내로 입력해주세요.`);
      return;
    }
    setError(null);
    setInput("");

    // 사용자 메시지 추가 (어시스턴트는 최종 답변 도착 시에만 추가)
    const userMsg: ChatMessage = {
      role: "user",
      content: trimmed,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    setLoading(true);
    setElapsed(0);

    try {
      await askStream(trimmed, {
        // 생성 과정(중간 토큰·Self-RAG 재생성)은 화면에 노출하지 않는다 — 로딩만 표시하고
        // 최종 답변(onDone)만 출력해 재생성 시 리셋·깜빡임을 없앤다.
        onToken: () => {},
        onReset: () => {},
        onDone: (answer, messageId) => {
          setLoading(false);
          // 빈 어시스턴트 메시지를 추가하고 청크 단위로 누적(가짜 스트리밍 — 약 1초 내 완료).
          // 서버는 최종 답변만 보내므로 Self-RAG 재생성 리셋과 무관하다.
          let assistantIdx = -1;
          setMessages((prev) => {
            assistantIdx = prev.length;
            return [
              ...prev,
              { role: "assistant", content: "", created_at: new Date().toISOString(), messageId },
            ];
          });
          const step = Math.max(3, Math.ceil(answer.length / 60)); // 약 60프레임(≈1초)에 완료
          let shown = 0;
          const timer = setInterval(() => {
            shown = Math.min(shown + step, answer.length);
            const slice = answer.slice(0, shown);
            setMessages((prev) => {
              if (assistantIdx < 0 || assistantIdx >= prev.length) return prev;
              const updated = [...prev];
              updated[assistantIdx] = { ...updated[assistantIdx], content: slice };
              return updated;
            });
            if (shown >= answer.length) clearInterval(timer);
          }, 16);
        },
        onError: (msg) => {
          setLoading(false);
          setError(msg);
        },
      });
    } catch (e) {
      setLoading(false);
      const msg = e instanceof Error ? e.message : "답변 생성 중 오류가 발생했습니다.";
      setError(msg);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  // AI 답변 피드백 — 낙관적 반영 후 서버 전송, 실패 시 롤백
  async function handleFeedback(index: number, rating: FeedbackRating) {
    const target = messages[index];
    if (!target?.messageId || target.feedback !== undefined) return;
    setMessages((prev) => {
      if (index >= prev.length) return prev;
      const updated = [...prev];
      updated[index] = { ...updated[index], feedback: rating };
      return updated;
    });
    try {
      await chatApi.feedback(target.messageId, rating);
    } catch {
      setMessages((prev) => {
        if (index >= prev.length) return prev;
        const updated = [...prev];
        updated[index] = { ...updated[index], feedback: undefined };
        return updated;
      });
    }
  }

  const isEmpty = messages.length === 0 && !loading;

  return (
    <div className="flex h-screen flex-col bg-bg-alt">
      <ScreenLabel label="22 · RAG 챗봇 (REQ-RAG-004/005 — KDIGO + 신장학회)" />
      <TopNav />

      <main className="flex flex-1 flex-col items-center overflow-hidden p-[16px]">
        <div className="flex h-full w-full max-w-[760px] flex-col rounded-lg border border-border bg-bg shadow-card">
          {/* 헤더 */}
          <div className="flex items-center gap-[12px] border-b border-border bg-bg-alt p-[12px]">
            <Bot size={24} className="text-accent" />
            <div className="flex flex-col">
              <h2 className="text-md font-bold text-text-primary">KiniQ AI 어시스턴트</h2>
              <p className="text-xs text-text-muted">
                KDIGO 가이드라인·대한신장학회 자료 기반 일반 정보 제공 (의학적 진단·처방 아님)
              </p>
            </div>
          </div>

          {/* 채팅 영역 */}
          <div ref={scrollRef} className="flex flex-1 flex-col gap-[16px] overflow-y-auto p-[16px]">
            {isEmpty && (
              <div className="flex flex-1 flex-col items-center justify-center gap-[16px] text-center">
                <div className="flex h-[64px] w-[64px] items-center justify-center rounded-full bg-bg-alt">
                  <Bot size={32} className="text-accent" />
                </div>
                <div>
                  <p className="text-sm font-bold text-text-primary">무엇을 도와드릴까요?</p>
                  <p className="mt-[4px] text-xs text-text-secondary">
                    신장 건강·생활습관에 대해 궁금한 점을 물어보세요.
                  </p>
                </div>
                <div className="flex flex-col gap-[8px] pt-[8px]">
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => send(q)}
                      disabled={loading}
                      className="rounded-lg border border-border bg-bg px-[12px] py-[8px] text-left text-xs text-text-secondary shadow-card transition-all hover:border-accent hover:text-text-primary hover:shadow-card-hover disabled:opacity-50"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <MessageBubble key={i} message={m} onFeedback={(rating) => handleFeedback(i, rating)} />
            ))}

            {/* 타이핑 인디케이터: 첫 토큰 수신 전까지만 표시 */}
            {loading && (
              <div className="flex gap-[8px]">
                <div className="flex h-[32px] w-[32px] shrink-0 items-center justify-center rounded-full bg-accent">
                  <Bot size={18} className="text-bg" />
                </div>
                <div className="flex items-center gap-[6px] rounded-lg border border-border bg-bg p-[12px] shadow-card">
                  <span className="h-[6px] w-[6px] animate-pulse rounded-full bg-text-muted" />
                  <span className="h-[6px] w-[6px] animate-pulse rounded-full bg-text-muted [animation-delay:150ms]" />
                  <span className="h-[6px] w-[6px] animate-pulse rounded-full bg-text-muted [animation-delay:300ms]" />
                  <span className="ml-[6px] text-xs text-text-secondary">답변 생성 중 · {elapsed}초</span>
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-lg border border-danger bg-danger/5 p-[12px] text-xs text-danger">
                {error}
              </div>
            )}
          </div>

          {/* 입력 영역 */}
          <div className="flex items-end gap-[8px] border-t border-border bg-bg p-[12px]">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              disabled={loading}
              rows={1}
              maxLength={QUESTION_MAX}
              placeholder="신장 건강에 대해 궁금한 것을 물어보세요. (Enter 전송 · Shift+Enter 줄바꿈)"
              className="max-h-[120px] min-h-[40px] flex-1 resize-none rounded-sm bg-bg-alt px-[12px] py-[10px] text-sm text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => send(input)}
              disabled={loading || !input.trim()}
              className="flex h-[40px] items-center gap-[6px] rounded-lg bg-accent px-[16px] text-sm font-bold text-bg shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-40"
            >
              <Send size={16} />
              전송
            </button>
          </div>
          <div className="border-t border-border bg-bg px-[12px] py-[6px] text-right text-[10px] text-text-muted">
            {input.length} / {QUESTION_MAX}
          </div>
        </div>
      </main>
    </div>
  );
}

function MessageBubble({
  message,
  onFeedback,
}: {
  message: ChatMessage;
  onFeedback?: (rating: FeedbackRating) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex items-start justify-end gap-[8px]">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-lg bg-accent px-[12px] py-[10px] text-sm text-bg shadow-card">
          {message.content}
        </div>
        <div className="flex h-[32px] w-[32px] shrink-0 items-center justify-center rounded-full bg-bg-alt text-text-secondary">
          <UserIcon size={18} />
        </div>
      </div>
    );
  }
  // 답변 본문이 렌더되고 서버 id 가 있을 때만 피드백 노출 (가짜 스트리밍 첫 프레임 제외)
  const showFeedback = message.messageId !== undefined && message.content.length > 0;
  return (
    <div className="flex items-start gap-[8px]">
      <div className="flex h-[32px] w-[32px] shrink-0 items-center justify-center rounded-full bg-accent">
        <Bot size={18} className="text-bg" />
      </div>
      <div className="flex max-w-[80%] flex-col gap-[6px]">
        <div className="rounded-lg border border-border bg-bg px-[12px] py-[10px] shadow-card">
          <Markdown>{message.content}</Markdown>
        </div>
        {showFeedback && (
          <div className="flex items-center gap-[8px] pl-[2px]">
            {message.feedback === undefined ? (
              <>
                <span className="text-xs text-text-muted">이 답변이 도움이 되었나요?</span>
                <button
                  type="button"
                  aria-label="도움이 됐어요"
                  onClick={() => onFeedback?.(1)}
                  className="flex items-center gap-[4px] rounded-md border border-border bg-bg px-[8px] py-[4px] text-xs text-text-secondary transition-colors hover:border-accent hover:text-accent"
                >
                  <ThumbsUp size={14} />
                  도움돼요
                </button>
                <button
                  type="button"
                  aria-label="아쉬워요"
                  onClick={() => onFeedback?.(-1)}
                  className="flex items-center gap-[4px] rounded-md border border-border bg-bg px-[8px] py-[4px] text-xs text-text-secondary transition-colors hover:border-accent hover:text-accent"
                >
                  <ThumbsDown size={14} />
                  아쉬워요
                </button>
              </>
            ) : (
              <span className="flex items-center gap-[4px] text-xs text-text-muted">
                {message.feedback === 1 ? <ThumbsUp size={14} /> : <ThumbsDown size={14} />}
                의견 감사합니다
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
