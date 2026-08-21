import { apiClient } from './api';
import type { UserPreferencesData, UserProgressData } from '../types';

export const profileService = {
  /**
   * Retrieve server-authoritative XP and level progression status.
   */
  async getProgress(): Promise<UserProgressData> {
    return apiClient.get<UserProgressData>('/profile/progress');
  },

  /**
   * Retrieve user genre preferences derived from behavioral telemetry.
   */
  async getPreferences(): Promise<UserPreferencesData> {
    return apiClient.get<UserPreferencesData>('/profile/preferences');
  },

  /**
   * Upload or replace profile avatar image.
   */
  async uploadAvatar(file: File): Promise<{ avatar_url: string; message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.postFormData<{ avatar_url: string; message: string }>('/auth/avatar', formData);
  },

  /**
   * Delete custom avatar and revert to default generated avatar.
   */
  async deleteAvatar(): Promise<{ avatar_url: null; message: string }> {
    return apiClient.delete<{ avatar_url: null; message: string }>('/auth/avatar');
  },
};
