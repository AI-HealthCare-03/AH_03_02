import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
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
