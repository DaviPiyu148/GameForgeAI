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

/**
 * Pure diffing function that calculates celebratory toast notifications for user progression transitions.
 * Returns an array of toast definitions to publish outside of the render cycle (e.g. within a React useEffect).
 */
export function diffUserProgress(
  prev: UserProgressData | null | undefined,
  current: UserProgressData | null | undefined
): Array<{ variant: 'levelup' | 'xp' | 'milestone'; title: string; description?: string }> {
  if (!prev || !current) return [];

  const toasts: Array<{ variant: 'levelup' | 'xp' | 'milestone'; title: string; description?: string }> = [];

  const xpGained = current.total_xp - prev.total_xp;
  if (current.current_level > prev.current_level) {
    toasts.push({
      variant: 'levelup',
      title: `LEVEL UP → ${current.current_level}`,
      description: current.creator_title,
    });
  } else if (xpGained > 0) {
    toasts.push({
      variant: 'xp',
      title: `+${xpGained} XP`,
    });
  }

  if (current.unlocked_milestone_count > prev.unlocked_milestone_count) {
    const newlyUnlocked = current.milestones.find(
      (m) => m.is_unlocked && !prev.milestones.some((pm) => pm.milestone_key === m.milestone_key && pm.is_unlocked)
    );
    toasts.push({
      variant: 'milestone',
      title: 'NEW MILESTONE',
      description: newlyUnlocked?.title,
    });
  }

  return toasts;
}

