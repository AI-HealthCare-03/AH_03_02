import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authApi, type UserInfo } from "../api/auth";

const TOKEN_KEY = "access_token";
const ADMIN_BACKUP_KEY = "admin_token_backup";
const IMPERSONATION_KEY = "impersonation_target";

function readStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
}

interface ImpersonationTarget {
  id: number;
  name_masked: string;
}

interface AuthContextValue {
  user: UserInfo | null;
  token: string | null;
  login: (token: string, persistent?: boolean) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
  isImpersonating: boolean;
  impersonationTarget: ImpersonationTarget | null;
  startImpersonation: (viewToken: string, target: ImpersonationTarget) => Promise<void>;
  stopImpersonation: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(readStoredToken);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(!!readStoredToken());
  // 임퍼소네이션 메타는 sessionStorage에 둬 탭 새로고침에도 생존(탭 닫으면 소멸).
  const [impersonationTarget, setImpersonationTarget] = useState<ImpersonationTarget | null>(() => {
    const raw = sessionStorage.getItem(IMPERSONATION_KEY);
    return raw ? JSON.parse(raw) : null;
  });

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

  async function startImpersonation(viewToken: string, target: ImpersonationTarget) {
    // 현재 관리자 토큰을 백업(복귀용), view 토큰으로 교체. view 토큰은 비영속(sessionStorage).
    const adminToken = localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
    if (adminToken) sessionStorage.setItem(ADMIN_BACKUP_KEY, adminToken);
    sessionStorage.setItem(IMPERSONATION_KEY, JSON.stringify(target));
    setImpersonationTarget(target);
    // login(persistent=false): 캐시 clear + 토큰 저장 + me() 수행 (대상 사용자로 전환)
    await login(viewToken, false);
  }

  async function stopImpersonation() {
    const adminToken = sessionStorage.getItem(ADMIN_BACKUP_KEY);
    sessionStorage.removeItem(ADMIN_BACKUP_KEY);
    sessionStorage.removeItem(IMPERSONATION_KEY);
    setImpersonationTarget(null);
    if (adminToken) {
      await login(adminToken, true); // 관리자 토큰 복원(영속) + 캐시 clear
    } else {
      logout();
    }
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
    <AuthContext.Provider
      value={{
        user, token, login, logout, isLoading,
        isImpersonating: !!impersonationTarget, impersonationTarget,
        startImpersonation, stopImpersonation,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
