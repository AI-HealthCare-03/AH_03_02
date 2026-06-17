import { api, BASE, getToken } from "./client";

export interface ChatMessageCreateRequest {
  question: string;
}

export interface ChatMessageResponse {
  message_id: number;
  answer: string;
  created_at: string;
}

export type FeedbackRating = 1 | -1;

export interface MessageFeedbackResponse {
  message_id: number;
  rating: number;
  created_at: string;
}

export const chatApi = {
  ask: (question: string) =>
    api.post<ChatMessageResponse>("/chat/messages", { question } satisfies ChatMessageCreateRequest),
  // AI 답변에 대한 도움됨(+1)/안됨(-1) 피드백 — 같은 답변에 재전송 시 서버가 upsert 갱신
  feedback: (messageId: number, rating: FeedbackRating, comment?: string) =>
    api.post<MessageFeedbackResponse>(`/chat/messages/${messageId}/feedback`, { rating, comment }),
};

// SSE 스트리밍 이벤트 핸들러 인터페이스
export interface ChatStreamHandlers {
  onToken: (text: string) => void;
  onReset: () => void;
  onDone: (answer: string, messageId: number) => void;
  onError: (message: string) => void;
}

// SSE 프레임 타입 정의
type StreamEvent =
  | { type: "token"; text: string }
  | { type: "reset" }
  | { type: "done"; answer: string; message_id: number }
  | { type: "error"; error: string };

/**
 * SSE 스트리밍 방식으로 챗봇 답변을 수신한다.
 * POST /api/v1/chat/messages/stream (text/event-stream)
 * - EventSource 대신 fetch를 사용 (POST + 인증 헤더 필요)
 * - client.ts의 BASE 경로 및 getToken() 과 동일한 방식으로 인증 토큰을 주입한다.
 */
export async function askStream(
  question: string,
  handlers: ChatStreamHandlers
): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  let res: Response;
  try {
    res = await fetch(`${BASE}/chat/messages/stream`, {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify({ question } satisfies ChatMessageCreateRequest),
    });
  } catch {
    handlers.onError("네트워크 연결을 확인해주세요.");
    return;
  }

  if (!res.ok || !res.body) {
    handlers.onError("스트리밍 연결에 실패했습니다.");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE 프레임은 "\n\n" 으로 구분된다
    const frames = buffer.split("\n\n");
    // 마지막 불완전한 프레임은 다음 청크까지 보관
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!dataLine) continue;

      let ev: StreamEvent;
      try {
        ev = JSON.parse(dataLine.slice(5).trim()) as StreamEvent;
      } catch {
        continue;
      }

      if (ev.type === "token") {
        handlers.onToken(ev.text ?? "");
      } else if (ev.type === "reset") {
        handlers.onReset();
      } else if (ev.type === "done") {
        // done 이벤트: 스트리밍 토큰과 다른 최종본(면책 문구 등 포함)으로 교체 + 피드백 연결용 message_id
        handlers.onDone(ev.answer ?? "", ev.message_id);
        return;
      } else if (ev.type === "error") {
        handlers.onError(ev.error ?? "오류가 발생했습니다.");
        return;
      }
    }
  }
}
