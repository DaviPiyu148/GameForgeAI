import { apiClient } from './api';
import type {
  GameProject,
  ProjectUpdateInput,
  GameBlueprint,
  RemixIntent,
  RemixApplyResponse,
  ProjectVersionSummary,
  CompileProjectResponse,
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
   * List historical playtest sessions and telemetry for a project.
   */
  async getPlaytests(id: string): Promise<import('../types').PlaytestSessionRecord[]> {
    return await apiClient.get<import('../types').PlaytestSessionRecord[]>(`/projects/${id}/playtests`);
  },

  /**
   * Restore an older version as a new immutable forward version (vN+1).
   */
  async restoreVersion(id: string, targetVersionNumber: number): Promise<GameProject> {
    return await apiClient.post<GameProject>(`/projects/${id}/restore`, null, {
      params: { target_version_number: targetVersionNumber },
    });
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

  /**
   * Deterministically compile a project version into a validated playable Phaser prototype.
   */
  async compileProject(id: string, versionNumber?: number): Promise<CompileProjectResponse> {
    return await apiClient.post<CompileProjectResponse>(`/projects/${id}/compile`, {
      versionNumber,
    });
  },

  /**
   * Run playtest critique and generate actionable gameplay improvement recommendations.
   */
  async analyzePlaytest(id: string, sessionId?: string, telemetryPayload?: Record<string, any>): Promise<import('../runtime/types').PlaytestAnalysis> {
    return await apiClient.post<import('../runtime/types').PlaytestAnalysis>(`/projects/${id}/analyze-playtest`, {
      session_id: sessionId,
      telemetry: telemetryPayload,
    });
  },

  /**
   * Apply approved playtest improvement recommendations to create an immutable forward version (vN+1).
   */
  async applyImprovements(id: string, request: import('../types').ImprovementApplyRequest): Promise<import('../types').ImprovementApplyResponse> {
    return await apiClient.post<import('../types').ImprovementApplyResponse>(`/projects/${id}/improvements`, request);
  },
};

