import { apiClient } from './api';
import { getApiBaseUrl, joinApiUrl } from './urlUtils';
import type {
  BuildLogEntry,
  BuildLogListResponse,
  BuildParams,
  BuildResponse,
  BackendBuildStatus,
} from '../types';
export interface BuildStatusEventData {
  build_id: string;
  status: BackendBuildStatus;
  project_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface BuildEventHandlers {
  onLog?: (log: BuildLogEntry) => void;
  onStatus?: (statusData: BuildStatusEventData) => void;
  onError?: (err: Error) => void;
  onComplete?: () => void;
}

export const buildService = {
  /**
   * Submit a new game build job.
   */
  async createBuild(prompt: string, parameters: BuildParams): Promise<BuildResponse> {
    return await apiClient.post<BuildResponse>('/builds', {
      prompt,
      parameters,
    });
  },

  /**
   * Get authoritative status of a build job.
   */
  async getBuild(buildId: string): Promise<BuildResponse> {
    return await apiClient.get<BuildResponse>(`/builds/${buildId}`);
  },

  /**
   * Retrieve all persisted logs for a build job.
   */
  async getBuildLogs(buildId: string): Promise<BuildLogListResponse> {
    return await apiClient.get<BuildLogListResponse>(`/builds/${buildId}/logs`);
  },

  /**
   * Cancel an active build job.
   */
  async cancelBuild(buildId: string): Promise<BuildResponse> {
    return await apiClient.post<BuildResponse>(`/builds/${buildId}/cancel`, {});
  },

  /**
   * Subscribe to real-time Server-Sent Events for a build.
   * Strategy: Securely requests a single-purpose short-lived SSE credential (90s TTL),
   * then opens EventSource with ?sse_token=... so the user's primary JWT bearer token
   * is never exposed in the URL or server access logs.
   */
  subscribeBuildEvents(buildId: string, handlers: BuildEventHandlers): () => void {
    let eventSource: EventSource | null = null;
    let isClosed = false;

    (async () => {
      try {
        // 1. Obtain short-lived SSE credential scoped only to this build
        const sseAuth = await apiClient.post<{ sse_token: string; expires_in_seconds: number }>(
          `/builds/${buildId}/sse-token`,
          {}
        );

        if (isClosed) return;

        const tokenParam = `?sse_token=${encodeURIComponent(sseAuth.sse_token)}`;
        // FS-028 fix: use joinApiUrl so a trailing slash on API_BASE_URL never
        // produces a double-slash in the EventSource URL.
        const sseUrl = joinApiUrl(getApiBaseUrl(), `builds/${buildId}/events${tokenParam}`);
        eventSource = new EventSource(sseUrl);

        eventSource.addEventListener('log', (event: MessageEvent) => {
          try {
            const logData: BuildLogEntry = JSON.parse(event.data);
            if (handlers.onLog) {
              handlers.onLog(logData);
            }
          } catch (err) {
            console.warn('Failed to parse SSE log event', err);
          }
        });

        eventSource.addEventListener('status', (event: MessageEvent) => {
          try {
            const statusData: BuildStatusEventData = JSON.parse(event.data);
            if (handlers.onStatus) {
              handlers.onStatus(statusData);
            }

            // Terminal states close the SSE connection
            if (statusData.status === 'SUCCESS' || statusData.status === 'ERROR' || statusData.status === 'CANCELLED') {
              eventSource?.close();
              if (handlers.onComplete) {
                handlers.onComplete();
              }
            }
          } catch (err) {
            console.warn('Failed to parse SSE status event', err);
          }
        });

        eventSource.onerror = (err) => {
          console.warn('SSE connection encountered an error or closed', err);
          eventSource?.close();
          if (handlers.onError) {
            handlers.onError(new Error('SSE connection error'));
          }
        };
      } catch (err) {
        if (!isClosed && handlers.onError) {
          handlers.onError(err instanceof Error ? err : new Error('Failed to acquire SSE credential'));
        }
      }
    })();

    return () => {
      isClosed = true;
      if (eventSource) {
        eventSource.close();
      }
    };
  },
};
