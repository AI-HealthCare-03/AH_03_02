import { api } from "./client";

export interface ChatMessageCreateRequest {
  question: string;
}

export interface ChatMessageResponse {
  answer: string;
  created_at: string;
}

export const chatApi = {
  ask: (question: string) =>
    api.post<ChatMessageResponse>("/chat/messages", { question } satisfies ChatMessageCreateRequest),
};
