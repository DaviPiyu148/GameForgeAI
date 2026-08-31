import { apiClient } from './api';
import type {
  DiscoveryFilters,
  DiscoverySearchResponse,
  BuildInspirationResponse,
  DiscoverySessionContext,
  DiscoveryFeedbackResponse,
} from '../types';

export const discoveryService = {
  /**
   * Search offline game catalog using natural language prompt and optional hard filters.
   */
  async searchGames(
    prompt: string,
    limit: number = 24,
    filters?: DiscoveryFilters,
    mode?: 'BEST_MATCH' | 'DISCOVER' | 'HIDDEN_GEMS' | 'POPULAR',
    sessionContext?: DiscoverySessionContext
  ): Promise<DiscoverySearchResponse> {
    return await apiClient.post<DiscoverySearchResponse>('/discovery/search', {
      prompt,
      limit,
      filters: filters && Object.keys(filters).length > 0 ? filters : undefined,
      mode: mode || 'BEST_MATCH',
      session_context: sessionContext,
    });
  },

  /**
   * Submit Like, Dislike, or Less Like This feedback.
   */
  async submitFeedback(
    gameId: string,
    feedback: 'like' | 'dislike' | 'less_like_this'
  ): Promise<DiscoveryFeedbackResponse> {
    return await apiClient.post<DiscoveryFeedbackResponse>('/discovery/feedback', {
      game_id: gameId,
      feedback,
    });
  },


  /**
   * Retrieve games similar to a specific game by Steam App ID.
   */
  async getSimilarGames(
    steamAppId: string,
    limit: number = 12
  ): Promise<DiscoverySearchResponse> {
    return await apiClient.get<DiscoverySearchResponse>(`/discovery/similar/${encodeURIComponent(steamAppId)}?limit=${limit}`);
  },

  /**
   * Retrieve games similar to a blend of 1 to 5 seed games.
   */
  async getMoreLikeThis(
    seedGameIds: string[],
    limit: number = 12
  ): Promise<DiscoverySearchResponse> {
    return await apiClient.post<DiscoverySearchResponse>('/discovery/more-like-this', {
      seed_game_ids: seedGameIds,
      limit,
    });
  },

  /**
   * Extract archetype, modules, and prompt starter for build studio from a discovered game.
   */
  async getBuildInspiration(
    steamAppId: string
  ): Promise<BuildInspirationResponse> {
    return await apiClient.get<BuildInspirationResponse>(`/discovery/build-inspiration/${encodeURIComponent(steamAppId)}`);
  },
};

