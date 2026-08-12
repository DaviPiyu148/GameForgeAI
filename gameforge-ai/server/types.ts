export interface GameEntry {
  id: string;
  title: string;
  description: string;
  genres: string[];
  themes: string[];
  mechanics: string[];
  tags: string[];
}

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

export interface BuildParams {
  engine: string;
  artDensity: number;
  physics: number;
  modules: string[];
}

export interface BuildRequest {
  prompt: string;
  parameters?: Partial<BuildParams>;
}

export interface BuildResponseSuccess {
  id: string;
  title: string;
  prompt: string;
  genre: string;
  status: 'PLAYABLE' | 'COMPILING' | 'ERROR';
  lastModified: string;
  parameters: BuildParams;
  createdAt: string;
}

export interface BuildResponseError {
  status: 'ERROR';
  message: string;
}
