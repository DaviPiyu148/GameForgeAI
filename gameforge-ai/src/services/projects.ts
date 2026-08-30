import { apiClient } from './api';
import type {
  GameProject,
  ProjectUpdateInput,
  GameBlueprint,
  RemixIntent,
  RemixApplyResponse,
  ProjectVersionSummary,
} from '../types';

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
  async updateProject(id: string, data: ProjectUpdateInput): Promise<GameProject> {
    return await apiClient.patch<GameProject>(`/projects/${id}`, data);
  },

  /**
   * Fetch the nontechnical-friendly Game Blueprint for a project.
   */
  async getBlueprint(id: string): Promise<GameBlueprint> {
    return await apiClient.get<GameBlueprint>(`/projects/${id}/blueprint`);
  },

  /**
   * Apply structured remix intents, creating a new immutable project version.
   */
  async applyRemix(id: string, intents: RemixIntent[]): Promise<RemixApplyResponse> {
    return await apiClient.post<RemixApplyResponse>(`/projects/${id}/remix`, { intents });
  },

  /**
   * List revision history (including remix provenance) for a project.
   */
  async getVersions(id: string): Promise<ProjectVersionSummary[]> {
    return await apiClient.get<ProjectVersionSummary[]>(`/projects/${id}/versions`);
  },

  /**
   * Permanently delete an owned project (204 No Content on success).
   */
  async deleteProject(id: string): Promise<void> {
    await apiClient.delete<void>(`/projects/${id}`);
  },

  /**
   * Create an independent snapshot copy of an owned project.
   * The duplicate gets a fresh v1 version history and no runtime history.
   */
  async duplicateProject(id: string): Promise<GameProject> {
    return await apiClient.post<GameProject>(`/projects/${id}/duplicate`);
  },
};
