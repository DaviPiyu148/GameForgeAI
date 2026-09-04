import { apiClient } from './api';
import type { ProjectInspirationRecord } from '../types';

interface ProjectInspirationListApiResponse {
  inspirations: ProjectInspirationRecord[];
}

export const inspirationService = {
  /**
   * Attach a game discovery as inspiration to an owned project.
   */
  async attach(projectId: string, steamAppId: string): Promise<ProjectInspirationRecord> {
    return await apiClient.post<ProjectInspirationRecord>(
      `/projects/${projectId}/inspirations`,
      { steamAppId }
    );
  },

  /**
   * List all inspirations attached to an owned project.
   */
  async list(projectId: string): Promise<ProjectInspirationRecord[]> {
    const res = await apiClient.get<ProjectInspirationListApiResponse>(
      `/projects/${projectId}/inspirations`
    );
    return res.inspirations || [];
  },

  /**
   * Detach a game inspiration from an owned project by steamAppId.
   */
  async detach(projectId: string, steamAppId: string): Promise<void> {
    await apiClient.delete<void>(`/projects/${projectId}/inspirations/${steamAppId}`);
  },
};
