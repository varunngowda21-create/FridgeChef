import { z } from 'zod';
import { getErrorMessage } from './errors';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export class ApiClientError extends Error {
  code: string;
  status: number;
  details?: unknown;
  requestId?: string;

  constructor(code: string, message: string, status: number, details?: unknown, requestId?: string) {
    super(message);
    this.name = 'ApiClientError';
    this.code = code;
    this.status = status;
    this.details = details;
    this.requestId = requestId;
  }
}

// In-memory token storage per PRD Section 12.5 & AGENTS.md
let memoryAccessToken: string | null = null;
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

export const tokenStorage = {
  getAccessToken: (): string | null => memoryAccessToken,
  setAccessToken: (token: string | null): void => {
    memoryAccessToken = token;
  },
  clear: (): void => {
    memoryAccessToken = null;
    sessionStorage.removeItem('fc_session_flag');
  },
};

type AuthListener = (isAuthenticated: boolean) => void;
const authListeners: Set<AuthListener> = new Set();

export const subscribeAuthChange = (listener: AuthListener) => {
  authListeners.add(listener);
  return () => {
    authListeners.delete(listener);
  };
};

const notifyAuthChange = (isAuthenticated: boolean) => {
  authListeners.forEach((fn) => fn(isAuthenticated));
};

function getCsrfToken(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function refreshToken(): Promise<string> {
  try {
    const csrf = getCsrfToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (csrf) {
      headers['X-CSRF-Token'] = csrf;
    }

    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers,
      credentials: 'include', // sends httpOnly refresh token cookie
      body: JSON.stringify({}),
    });

    if (!res.ok) {
      throw new Error('Refresh failed');
    }

    const data = await res.json();
    const newToken = data.access_token;
    tokenStorage.setAccessToken(newToken);
    return newToken;
  } catch (err) {
    tokenStorage.clear();
    notifyAuthChange(false);
    throw err;
  }
}

interface RequestOptions extends RequestInit {
  schema?: z.ZodTypeAny;
  isRetry?: boolean;
}

export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { schema, isRetry = false, ...fetchOptions } = options;
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

  const headers = new Headers(fetchOptions.headers || {});
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  // Attach in-memory access token
  const token = tokenStorage.getAccessToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Attach CSRF token for mutating requests
  const csrfToken = getCsrfToken();
  if (csrfToken && !headers.has('X-CSRF-Token')) {
    headers.set('X-CSRF-Token', csrfToken);
  }

  // Include credentials for httpOnly cookies
  fetchOptions.credentials = 'include';

  let response: Response;
  try {
    response = await fetch(url, { ...fetchOptions, headers });
  } catch (networkError) {
    throw new ApiClientError(
      'NETWORK_ERROR',
      'Unable to connect to the server. Please check your internet connection.',
      0,
      networkError
    );
  }

  // Handle 401 Unauthorized with token refresh (PRD Section 12.5)
  if (response.status === 401 && !isRetry && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/register')) {
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((newToken) => {
          headers.set('Authorization', `Bearer ${newToken}`);
          return request<T>(endpoint, { ...options, isRetry: true });
        })
        .catch((err) => Promise.reject(err));
    }

    isRefreshing = true;

    try {
      const newToken = await refreshToken();
      processQueue(null, newToken);
      headers.set('Authorization', `Bearer ${newToken}`);
      return await request<T>(endpoint, { ...options, isRetry: true });
    } catch (refreshErr) {
      processQueue(refreshErr, null);
      throw new ApiClientError(
        'UNAUTHORIZED',
        getErrorMessage('UNAUTHORIZED'),
        401
      );
    } finally {
      isRefreshing = false;
    }
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null as unknown as T;
  }

  // Parse JSON response
  let json: Record<string, unknown> | null = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      json = (await response.json()) as Record<string, unknown>;
    } catch {
      json = null;
    }
  }

  if (!response.ok) {
    const errorEnvelope = json?.error as { code?: string; message?: string; details?: unknown; request_id?: string } | undefined;
    const code = errorEnvelope?.code || `HTTP_${response.status}`;
    const userMessage = getErrorMessage(code, errorEnvelope?.message);
    throw new ApiClientError(code, userMessage, response.status, errorEnvelope?.details, errorEnvelope?.request_id);
  }

  // Validate at boundary if schema provided
  if (schema && json !== null) {
    const parseResult = schema.safeParse(json);
    if (!parseResult.success) {
      console.warn('API Response Schema Validation Warning:', parseResult.error);
      return json as T; // Return data anyway for resilience in production
    }
    return parseResult.data as T;
  }

  return json as T;
}

export const api = {
  get: <T>(path: string, schema?: z.ZodTypeAny) =>
    request<T>(path, { method: 'GET', schema }),

  post: <T>(path: string, body?: unknown, schema?: z.ZodTypeAny) =>
    request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      schema,
    }),

  put: <T>(path: string, body?: unknown, schema?: z.ZodTypeAny) =>
    request<T>(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      schema,
    }),

  patch: <T>(path: string, body?: unknown, schema?: z.ZodTypeAny) =>
    request<T>(path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      schema,
    }),

  delete: <T>(path: string, body?: unknown, schema?: z.ZodTypeAny) =>
    request<T>(path, {
      method: 'DELETE',
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      schema,
    }),

  upload: <T>(path: string, formData: FormData, schema?: z.ZodTypeAny) =>
    request<T>(path, {
      method: 'POST',
      body: formData,
      schema,
    }),
};

