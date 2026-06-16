export const BASE = "/api/v1";

export function getToken(): string | null {
  return localStorage.getItem("access_token") ?? sessionStorage.getItem("access_token");
}

function setToken(token: string): void {
  if (localStorage.getItem("access_token") !== null) {
    localStorage.setItem("access_token", token);
  } else {
    sessionStorage.setItem("access_token", token);
  }
}

function clearToken(): void {
  localStorage.removeItem("access_token");
  sessionStorage.removeItem("access_token");
}

// HTTP 상태 코드별 한국어 fallback (백엔드 detail이 없는 극히 드문 경우)
const STATUS_FALLBACK: Record<number, string> = {
  400: "잘못된 요청입니다.",
  401: "로그인이 필요합니다.",
  403: "접근 권한이 없습니다.",
  404: "요청한 리소스를 찾을 수 없습니다.",
  405: "허용되지 않은 요청 방식입니다.",
  408: "요청 시간이 초과됐습니다.",
  409: "이미 처리된 요청이거나 충돌이 발생했습니다.",
  413: "요청 데이터가 너무 큽니다.",
  422: "입력 형식이 올바르지 않습니다.",
  429: "요청이 너무 잦습니다. 잠시 후 다시 시도해주세요.",
  500: "일시적 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
  502: "서버에 일시적 문제가 있습니다.",
  503: "서비스 점검 중입니다.",
  504: "서버 응답이 지연되고 있습니다.",
};

/**
 * 백엔드 에러 응답 → 사용자에게 보여줄 한국어 메시지로 변환.
 * 응답 형식:
 *   { detail: "메시지" }                 ← HTTPException
 *   { detail: [{ field: "이메일", message: "..." }] }  ← 검증 에러 (422)
 */
function extractMessage(data: unknown, status: number): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    // 문자열 detail (HTTPException)
    if (typeof detail === "string") return detail;
    // 배열 detail (검증 에러)
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (typeof first === "string") return first;
      if (first && typeof first === "object") {
        const obj = first as { field?: string; message?: string; msg?: string };
        const field = obj.field;
        const msg = obj.message ?? obj.msg ?? "";
        if (field && msg) return `${field}: ${msg}`;
        if (msg) return msg;
      }
    }
  }
  return STATUS_FALLBACK[status] ?? `오류가 발생했습니다. (코드 ${status})`;
}

let refreshing: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  if (refreshing) return refreshing;
  refreshing = fetch(`${BASE}/auth/token/refresh`, {
    method: "GET",
    credentials: "include",
  })
    .then(async (res) => {
      if (!res.ok) return null;
      const data = await res.json();
      const newToken: string = data.access_token;
      setToken(newToken);
      return newToken;
    })
    .catch(() => null)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  // FormData면 Content-Type을 브라우저가 자동 설정(multipart boundary 포함)하도록 비움
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // 네트워크 자체 에러(서버 다운·인터넷 끊김 등) 한국어 처리
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...options, headers, credentials: "include" });
  } catch {
    throw new Error("네트워크 연결을 확인해주세요.");
  }

  if (res.status === 401) {
    // 임퍼소네이션(view 토큰) 만료: refresh 쿠키는 관리자 것이므로 refresh하지 않고
    // 백업한 관리자 토큰으로 복원한 뒤 관리자 화면으로 보낸다.
    const adminBackup = sessionStorage.getItem("admin_token_backup");
    if (adminBackup) {
      sessionStorage.removeItem("admin_token_backup");
      sessionStorage.removeItem("impersonation_target");
      localStorage.setItem("access_token", adminBackup);
      sessionStorage.removeItem("access_token");
      window.location.href = "/admin/users";
      throw new Error("임퍼소네이션 세션이 만료돼 관리자로 돌아갑니다.");
    }
    const newToken = await tryRefresh();
    if (!newToken) {
      clearToken();
      window.location.href = "/";
      throw new Error("로그인이 만료됐습니다. 다시 로그인해주세요.");
    }
    // 새 토큰으로 원래 요청 재시도
    const retryHeaders = { ...headers, Authorization: `Bearer ${newToken}` };
    let retry: Response;
    try {
      retry = await fetch(`${BASE}${path}`, { ...options, headers: retryHeaders, credentials: "include" });
    } catch {
      throw new Error("네트워크 연결을 확인해주세요.");
    }
    if (retry.status === 401) {
      clearToken();
      window.location.href = "/";
      throw new Error("로그인이 만료됐습니다. 다시 로그인해주세요.");
    }
    const retryData = await retry.json().catch(() => ({}));
    if (!retry.ok) {
      throw new Error(extractMessage(retryData, retry.status));
    }
    return retryData as T;
  }

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(extractMessage(data, res.status));
  }

  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  postForm: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", body: formData }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
