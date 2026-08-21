import { apiClient } from './api';
import type { GameProject } from '../types';

interface ProjectListApiResponse {
  projects: GameProject[];
}

export const projectService = {
  /**
   * Fetch all persisted projects from backend database.
   */
  async getProjects(limit: number = 100, offset: number = 0): Promise<GameProject[]> {
    const res = await apiClient.get<ProjectListApiResponse>('/projects', {
      params: { limit, offset },
    });
    return res.projects || [];
  },

  /**
   * Retrieve a single project by ID (includes gameDsl and runtimeMetadata).
   */
  async getProject(id: string): Promise<GameProject> {
    return await apiClient.get<GameProject>(`/projects/${id}`);
  },

  /**
   * Update permitted fields on a project.
   */
  async updateProject(id: string, data: Partial<GameProject>): Promise<GameProject> {
    return await apiClient.patch<GameProject>(`/projects/${id}`, data);
  },
};
