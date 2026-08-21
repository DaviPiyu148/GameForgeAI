/**
 * Base HTTP API client for GameForge AI.
 * Uses relative `/api` path in development (proxied by Vite to http://127.0.0.1:8000)
 * or `VITE_API_URL` when explicitly configured.
 */

export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
export const AUTH_TOKEN_KEY = 'gameforge_auth_token';

export class ApiError extends Error {
  public code: string;
  public status: number;
  public requestId?: string;

  constructor(message: string, code: string = 'API_ERROR', status: number = 500, requestId?: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, ...customConfig } = options;

  let url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  const headers = new Headers(customConfig.headers || {});
  if (!headers.has('Content-Type') && !(customConfig.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Inject Authorization header if token exists in localStorage
  try {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  } catch {
    // localStorage unavailable
  }

  const config: RequestInit = {
    ...customConfig,
    headers,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      if (response.status === 401) {
        try {
          if (localStorage.getItem(AUTH_TOKEN_KEY)) {
            localStorage.removeItem(AUTH_TOKEN_KEY);
            window.dispatchEvent(new CustomEvent('gameforge:auth-expired'));
          }
        } catch {
          // localStorage unavailable
        }
      }

      let errorCode = 'HTTP_ERROR';
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;
      let requestId: string | undefined;

      try {
        const errorData = await response.json();
        if (errorData?.error) {
          errorCode = errorData.error.code || errorCode;
          errorMessage = errorData.error.message || errorMessage;
          requestId = errorData.error.request_id;
        } else if (errorData?.detail) {
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map((d: { msg?: string }) => d.msg || 'Validation error').join('; ');
            errorCode = 'VALIDATION_ERROR';
          } else {
            errorMessage = String(errorData.detail);
          }
        }
      } catch {
        // Response body was not JSON
      }

      throw new ApiError(errorMessage, errorCode, response.status, requestId);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }
    // Network errors (connection refused, offline, etc.)
    throw new ApiError(
      'Unable to connect to GameForge backend service.',
      'NETWORK_ERROR',
      0
    );
  }
}

export const apiClient = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: 'GET' }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  postFormData: <T>(endpoint: string, formData: FormData, options?: RequestOptions) =>
    request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: formData,
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: 'DELETE' }),
};
