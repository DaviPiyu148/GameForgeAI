import { apiClient, AUTH_TOKEN_KEY } from './api';
import type {
  AuthResponse,
  AuthUser,
  LoginRequest,
  RegisterRequest,
  BackendSavedDiscovery,
  SavedDiscoveryListResponse,
} from '../types';

export const authStorage = {
  getToken: (): string | null => {
    try {
      return localStorage.getItem(AUTH_TOKEN_KEY);
    } catch {
      return null;
    }
  },
  setToken: (token: string): void => {
    try {
      localStorage.setItem(AUTH_TOKEN_KEY, token);
    } catch (e) {
      console.warn('Failed to save auth token to localStorage', e);
    }
  },
  clearToken: (): void => {
    try {
      localStorage.removeItem(AUTH_TOKEN_KEY);
    } catch (e) {
      console.warn('Failed to remove auth token from localStorage', e);
    }
  },
};

export const authService = {
  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const res = await apiClient.post<AuthResponse>('/auth/register', data);
    if (res.access_token) {
      authStorage.setToken(res.access_token);
    }
    return res;
  },

  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const res = await apiClient.post<AuthResponse>('/auth/login', data);
    if (res.access_token) {
      authStorage.setToken(res.access_token);
    }
    return res;
  },

  getMe: async (): Promise<AuthUser> => {
    return apiClient.get<AuthUser>('/auth/me');
  },

  logout: (): void => {
    authStorage.clearToken();
  },
};

export const savedDiscoveriesService = {
  getSaved: async (): Promise<BackendSavedDiscovery[]> => {
    const res = await apiClient.get<SavedDiscoveryListResponse>('/saved-discoveries');
    return res.discoveries || [];
  },

  saveDiscovery: async (steamAppId: string): Promise<BackendSavedDiscovery> => {
    return apiClient.post<BackendSavedDiscovery>('/saved-discoveries', {
      steam_app_id: steamAppId,
    });
  },

  deleteSaved: async (id: string): Promise<void> => {
    return apiClient.delete<void>(`/saved-discoveries/${id}`);
  },
};
