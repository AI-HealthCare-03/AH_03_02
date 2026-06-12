import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authApi, type UserInfo } from "../api/auth";

const TOKEN_KEY = "access_token";

function readStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
}

interface AuthContextValue {
  user: UserInfo | null;
  token: string | null;
  login: (token: string, persistent?: boolean) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(readStoredToken);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(!!readStoredToken());

  useEffect(() => {
    if (!token) { setIsLoading(false); return; }
    authApi.me()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        sessionStorage.removeItem(TOKEN_KEY);
        setToken(null);
      })
      .finally(() => setIsLoading(false));
  }, [token]);

  async function login(newToken: string, persistent = true) {
    // 계정 전환 시 이전 계정의 react-query 캐시(staleTime 5분) 잔존 방지 — 먼저 비운다.
    // (이걸 안 하면 새 계정 로그인 후 다른 계정으로 재로그인 시 이전 계정 빈 데이터가 그대로 보임)
    queryClient.clear();
    if (persistent) {
      localStorage.setItem(TOKEN_KEY, newToken);
      sessionStorage.removeItem(TOKEN_KEY);
    } else {
      sessionStorage.setItem(TOKEN_KEY, newToken);
      localStorage.removeItem(TOKEN_KEY);
    }
    setToken(newToken);
    const me = await authApi.me();
    setUser(me);
  }

  function logout() {
    // 로그아웃 시에도 캐시를 비워 다음 로그인 계정에 잔존 데이터가 새지 않도록 한다.
    queryClient.clear();
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    // 온보딩 모달 세션 키 정리 — 다음 로그인 시 다시 노출되도록 (검진/설문 0건이면)
    for (let i = sessionStorage.length - 1; i >= 0; i--) {
      const k = sessionStorage.key(i);
      if (k && k.startsWith("welcome_seen_")) sessionStorage.removeItem(k);
    }
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
