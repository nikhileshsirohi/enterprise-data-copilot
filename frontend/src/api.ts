import type { AskResponse, AuthSession, AuthUser, ChatSession, ChatSessionDetail } from "./types";

const API_BASE_URL =
  import.meta.env.VITE_AI_API_BASE_URL ?? "http://127.0.0.1:8001/api/v1";
const DJANGO_API_BASE_URL =
  import.meta.env.VITE_DJANGO_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

type RequestOptions = {
  token: string;
  method?: string;
  body?: unknown;
};

async function apiRequest<T>(path: string, options: RequestOptions): Promise<T> {
  return request<T>(`${API_BASE_URL}${path}`, options);
}

async function djangoRequest<T>(path: string, options: RequestOptions): Promise<T> {
  return request<T>(`${DJANGO_API_BASE_URL}${path}`, options);
}

async function request<T>(url: string, options: RequestOptions): Promise<T> {
  const response = await fetch(url, {
    method: options.method ?? "GET",
    headers: {
      Authorization: `Bearer ${options.token}`,
      "Content-Type": "application/json",
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.detail ?? `Request failed with status ${response.status}`;
    throw new Error(Array.isArray(message) ? "Request validation failed." : String(message));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function login(params: { username: string; password: string }): Promise<AuthSession> {
  const response = await fetch(`${DJANGO_API_BASE_URL}/auth/login/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(String(payload?.detail ?? "Invalid username or password."));
  }

  return response.json() as Promise<AuthSession>;
}

export function getCurrentUser(token: string): Promise<AuthUser> {
  return djangoRequest<AuthUser>("/auth/me/", { token });
}

export function logout(params: {
  token: string;
  refresh: string;
  sessionId: string;
}): Promise<void> {
  return djangoRequest<void>("/auth/logout/", {
    token: params.token,
    method: "POST",
    body: {
      refresh: params.refresh,
      session_id: params.sessionId,
    },
  });
}

export function askQuestion(params: {
  token: string;
  question: string;
  sessionId: string | null;
  limit: number;
}): Promise<AskResponse> {
  return apiRequest<AskResponse>("/ask/", {
    token: params.token,
    method: "POST",
    body: {
      question: params.question,
      session_id: params.sessionId,
      limit: params.limit,
      persist: true,
      use_cache: true,
    },
  });
}

export async function listChatSessions(token: string): Promise<ChatSession[]> {
  const response = await apiRequest<{ sessions: ChatSession[] }>("/chat/sessions", { token });
  return response.sessions;
}

export function getChatSession(token: string, sessionId: string): Promise<ChatSessionDetail> {
  return apiRequest<ChatSessionDetail>(`/chat/sessions/${sessionId}`, { token });
}

export function archiveChatSession(token: string, sessionId: string): Promise<void> {
  return apiRequest(`/chat/sessions/${sessionId}`, {
    token,
    method: "DELETE",
  });
}
