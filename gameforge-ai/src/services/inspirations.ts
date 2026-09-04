import { apiClient } from './api';
import type {
  ApplySynthesisProposalRequest,
  ApplySynthesisProposalResponse,
  InspirationSynthesisProposal,
  ProjectInspirationRecord,
} from '../types';

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

  /**
   * Synthesize a structured GameForge design proposal from 2-5 attached project inspirations.
   * Deterministic proposal for developer review; does not modify the Blueprint.
   */
  async synthesize(projectId: string): Promise<InspirationSynthesisProposal> {
    return await apiClient.post<InspirationSynthesisProposal>(
      `/projects/${projectId}/inspirations/synthesize`
    );
  },

  /**
   * Apply an approved inspiration synthesis proposal to an owned project's Blueprint.
   * Creates a new forward ProjectVersion (vN+1).
   */
  async applySynthesis(
    projectId: string,
    data: ApplySynthesisProposalRequest
  ): Promise<ApplySynthesisProposalResponse> {
    return await apiClient.post<ApplySynthesisProposalResponse>(
      `/projects/${projectId}/inspirations/synthesize/apply`,
      data
    );
  },
};

