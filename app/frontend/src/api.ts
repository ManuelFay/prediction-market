import type {
  CommentPage,
  CommentRead,
  LedgerEntryRead,
  MarketCreatePayload,
  MarketRead,
  MarketWithBets,
  PositionRead,
  UserAuthRead,
  UserLoginPayload,
  UserRead
} from './types';

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? window.location.origin).replace(/\/$/, '');

type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  auth?: { username: string; password: string };
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers ?? {})
  };
  if (options.auth) {
    const { username, password } = options.auth;
    headers.Authorization = `Basic ${btoa(`${username}:${password}`)}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined
  });

  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail ?? 'Request failed');
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export const api = {
  login(payload: UserLoginPayload) {
    return request<UserAuthRead>('/auth/login', { method: 'POST', body: payload });
  },
  listUsers() {
    return request<UserRead[]>('/users');
  },
  listUsersWithPasswords(auth: { username: string; password: string }) {
    return request<UserAuthRead[]>('/admin/users', { headers: {}, auth });
  },
  createUser(name: string, auth: { username: string; password: string }) {
    return request<UserAuthRead>('/users', {
      method: 'POST',
      body: { name },
      auth
    });
  },
  resetPlatform(auth: { username: string; password: string }) {
    return request<void>('/reset', { method: 'POST', auth });
  },
  deposit(userId: number, amount: number, auth: { username: string; password: string }) {
    return request<void>(`/users/${userId}/deposit`, {
      method: 'POST',
      body: { amount },
      auth
    });
  },
  deleteUser(userId: number, auth: { username: string; password: string }) {
    return request<void>(`/users/${userId}`, { method: 'DELETE', auth });
  },
  getUser(userId: number) {
    return request<UserRead>(`/users/${userId}`);
  },
  getLedger(userId: number) {
    return request<LedgerEntryRead[]>(`/users/${userId}/ledger`);
  },
  getPositions(userId: number) {
    return request<PositionRead[]>(`/users/${userId}/positions`);
  },
  listMarkets() {
    return request<MarketRead[]>('/markets');
  },
  getMarket(id: number) {
    return request<MarketWithBets>(`/markets/${id}`);
  },
  createMarket(userId: number, payload: MarketCreatePayload) {
    return request<MarketRead>(`/markets?user_id=${userId}`, { method: 'POST', body: payload });
  },
  placeBet(marketId: number, userId: number, side: 'YES' | 'NO', password: string) {
    return request(`/markets/${marketId}/bet?user_id=${userId}`, {
      method: 'POST',
      body: { side, password }
    });
  },
  resolveMarket(marketId: number, outcome: 'YES' | 'NO' | 'INVALID') {
    return request(`/markets/${marketId}/resolve`, { method: 'POST', body: { outcome } });
  },
  deleteMarket(marketId: number, userId: number) {
    return request<void>(`/markets/${marketId}?user_id=${userId}`, { method: 'DELETE' });
  },
  getComments(marketId: number, page: number, pageSize: number) {
    return request<CommentPage>(`/markets/${marketId}/comments?page=${page}&page_size=${pageSize}`);
  },
  createComment(marketId: number, userId: number, text: string, password: string) {
    return request<CommentRead>(`/markets/${marketId}/comments?user_id=${userId}`, {
      method: 'POST',
      body: { text, password }
    });
  },
  deleteComment(commentId: number, userId: number, password: string) {
    return request<void>(`/comments/${commentId}?user_id=${userId}`, {
      method: 'DELETE',
      body: { password }
    });
  }
};
