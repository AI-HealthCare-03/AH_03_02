import { api } from "./client";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
}

export interface ConsentItem {
  consent_type: "TERMS_OF_SERVICE" | "PRIVACY_INFO" | "SENSITIVE_HEALTH" | "MARKETING";
  version: string;
  agreed: boolean;
}

export interface SignUpRequest {
  email: string;
  password: string;
  name: string;
  gender: "MALE" | "FEMALE";
  birth_date: string;
  phone_number: string;
  consents?: ConsentItem[];
}

export interface UserInfo {
  id: number;
  name: string;
  email: string;
  phone_number: string;
  birthday: string;
  gender: "MALE" | "FEMALE";
  is_admin: boolean;
  created_at: string;
}

export interface PasswordResetRequestResponse {
  sent: boolean;
  mode: "demo" | "production";
  demo_code: string | null;
  expires_in_seconds: number;
}

export interface EmailVerificationRequestResponse {
  sent: boolean;
  mode: "demo" | "production";
  demo_code: string | null;
  expires_in_hours: number;
}

export interface SignUpResponse {
  user_id: number;
  email: string;
  email_verification: EmailVerificationRequestResponse;
}

export const authApi = {
  login: (body: LoginRequest) => api.post<LoginResponse>("/auth/login", body),
  signup: (body: SignUpRequest) => api.post<SignUpResponse>("/auth/signup", body),
  logout: () => api.post<void>("/auth/logout", {}),
  me: () => api.get<UserInfo>("/users/me"),
  changePassword: (body: { current_password: string; new_password: string }) =>
    api.patch<void>("/users/me/password", body),
  updateMe: (body: { name?: string; birthday?: string; phone_number?: string }) =>
    api.patch<UserInfo>("/users/me", body),
  deleteAccount: () => api.delete<void>("/users/me"),
  forgotPassword: (email: string) => api.post<{ temp_password: string }>("/auth/forgot-password", { email }),
  // 새 2단계 흐름
  requestPasswordReset: (email: string) =>
    api.post<PasswordResetRequestResponse>("/auth/password-reset/request", { email }),
  verifyPasswordReset: (email: string, code: string) =>
    api.post<{ temp_password: string }>("/auth/password-reset/verify", { email, code }),
  // REQ-AUTH-003 이메일 인증
  requestEmailVerification: (email: string) =>
    api.post<EmailVerificationRequestResponse>("/auth/email-verification/request", { email }),
  verifyEmail: (email: string, code: string) =>
    api.post<{ verified: boolean }>("/auth/email-verification/verify", { email, code }),
  // 회원가입 사전 이메일 중복 확인
  checkEmail: (email: string) =>
    api.get<{ available: boolean; email: string }>(`/auth/check-email?email=${encodeURIComponent(email)}`),
};
