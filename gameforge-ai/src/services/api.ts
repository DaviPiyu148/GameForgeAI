import type { BuildParams } from '../types';

export interface RecommendationMatch {
  id: string;
  title: string;
  description: string;
  score: number;
  reasons: string[];
}

export interface RecommendationResponse {
  query: string;
  matches: RecommendationMatch[];
}

export interface BuildResponseSuccess {
  id: string;
  title: string;
  prompt: string;
  genre: string;
  status: 'PLAYABLE' | 'COMPILING' | 'ERROR';
  lastModified: string;
  parameters: BuildParams;
  createdAt?: string;
}

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:3001').replace(/\/+$/, '');

export async function healthCheck(): Promise<{ status: string; service: string }> {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json();
}

export async function recommendGames(prompt: string): Promise<RecommendationResponse> {
  const response = await fetch(`${API_BASE_URL}/api/recommendations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ prompt })
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Recommendation failed with status ${response.status}`);
  }

  return response.json();
}

export async function buildProject(
  prompt: string,
  parameters?: Partial<BuildParams>
): Promise<BuildResponseSuccess> {
  const response = await fetch(`${API_BASE_URL}/api/builds`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ prompt, parameters })
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok || data.status === 'ERROR') {
    const message = data.message || `Build failed with status ${response.status}`;
    const err = new Error(message);
    (err as any).status = 'ERROR';
    throw err;
  }

  return data as BuildResponseSuccess;
}
