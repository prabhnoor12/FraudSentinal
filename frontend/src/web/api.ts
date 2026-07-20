type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export type ApiError = {
  status: number;
  message: string;
  details?: unknown;
};

export type TokenResponse = {
  access_token?: string | null;
  refresh_token?: string | null;
  token_type?: string;
  mfa_required?: boolean;
  pre_auth_token?: string | null;
  message?: string | null;
};

type RequestOptions = {
  auth?: boolean;
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: JsonValue;
  headers?: Record<string, string>;
  retryOnUnauthorized?: boolean;
};

const ACCESS_TOKEN_KEY = 'fraudsentinel.accessToken';
const REFRESH_TOKEN_KEY = 'fraudsentinel.refreshToken';

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof document !== 'undefined';
}

function getApiBaseUrlFromMeta(): string | null {
  if (!isBrowser()) return null;
  const el = document.querySelector<HTMLMetaElement>('meta[name="fraudsentinel-api-base-url"]');
  const content = el?.content?.trim();
  return content ? content.replace(/\/+$/, '') : null;
}

export function getApiBaseUrl(): string {
  return getApiBaseUrlFromMeta() ?? 'http://localhost:8000';
}

export function getAccessToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(tokens: { accessToken?: string | null; refreshToken?: string | null }): void {
  if (!isBrowser()) return;
  if (tokens.accessToken != null) window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
  if (tokens.refreshToken != null) window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
}

export function clearTokens(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function buildQueryString(query: RequestOptions['query']): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) continue;
    params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : '';
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) return response.json();
  const text = await response.text();
  return text.length ? text : null;
}

function toApiError(status: number, body: unknown): ApiError {
  const detail = (body as any)?.detail;
  const message =
    typeof detail === 'string'
      ? detail
      : typeof (body as any)?.message === 'string'
        ? (body as any).message
        : status === 0
          ? 'Network error'
          : `Request failed (${status})`;

  return { status, message, details: body };
}

export async function apiRequest<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${path}${buildQueryString(options.query)}`;

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers ?? {}),
  };

  if (options.body !== undefined) headers['Content-Type'] = 'application/json';

  if (options.auth) {
    const token = getAccessToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw toApiError(0, null);
  }

  const body = await parseResponseBody(response);

  if (response.status === 401 && options.auth && options.retryOnUnauthorized !== false) {
    const refreshed = await tryRefreshTokens();
    if (refreshed) return apiRequest<T>(method, path, { ...options, retryOnUnauthorized: false });
  }

  if (!response.ok) throw toApiError(response.status, body);
  return body as T;
}

async function tryRefreshTokens(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const result = await apiRequest<TokenResponse>('POST', '/auth/refresh', {
      body: { refresh_token: refreshToken },
      retryOnUnauthorized: false,
    });
    if (result.access_token) setTokens({ accessToken: result.access_token });
    if (result.refresh_token) setTokens({ refreshToken: result.refresh_token });
    return Boolean(result.access_token);
  } catch {
    clearTokens();
    return false;
  }
}

export const api = {
  auth: {
    async register(payload: {
      email: string;
      password: string;
      full_name?: string | null;
      organisation_name?: string | null;
    }): Promise<unknown> {
      return apiRequest('POST', '/auth/register', { body: payload });
    },
    async login(payload: { email: string; password: string }): Promise<TokenResponse> {
      const result = await apiRequest<TokenResponse>('POST', '/auth/login', { body: payload });
      setTokens({
        accessToken: result.access_token ?? null,
        refreshToken: result.refresh_token ?? null,
      });
      return result;
    },
    async logout(): Promise<void> {
      const refreshToken = getRefreshToken();
      try {
        await apiRequest('POST', '/auth/logout', {
          auth: true,
          body: refreshToken ? { refresh_token: refreshToken } : undefined,
        });
      } finally {
        clearTokens();
      }
    },
    async me(): Promise<unknown> {
      return apiRequest('GET', '/auth/me', { auth: true });
    },
  },
  audit: {
    async list(params?: { limit?: number; offset?: number }): Promise<unknown[]> {
      return apiRequest('GET', '/audit', {
        auth: true,
        query: { limit: params?.limit ?? 50, offset: params?.offset ?? 0 },
      });
    },
    async stats(): Promise<unknown> {
      return apiRequest('GET', '/audit/stats', { auth: true });
    },
  },
  usage: {
    async listEvents(): Promise<unknown[]> {
      return apiRequest('GET', '/usage/events', { auth: true });
    },
    async listSummaries(): Promise<unknown[]> {
      return apiRequest('GET', '/usage/summaries', { auth: true });
    },
  },
  settings: {
    async get(organisationId: number): Promise<unknown> {
      return apiRequest('GET', `/settings/${organisationId}`, { auth: true });
    },
    async update(organisationId: number, payload: Record<string, JsonValue>): Promise<unknown> {
      return apiRequest('PUT', `/settings/${organisationId}`, { auth: true, body: payload });
    },
  },
};

