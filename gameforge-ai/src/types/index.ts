export type ProjectStatus = 'PLAYABLE' | 'COMPILING' | 'ERROR';

export interface GameProject {
  id: string;
  title: string;
  genre: string;
  status: ProjectStatus;
  lastModified: string;
  parameters: BuildParams;
  prompt: string;
}

export interface BuildParams {
  engine: string;
  artDensity: number;
  physics: number;
  modules: string[];
}

export interface UserProfile {
  id: string;
  username: string;
  level: number;
  avatarPlaceholder: string;
}

export interface SavedDiscovery {
  id: string;
  matchPercentage: number;
  savedDate: string;
  title: string;
  author: string;
  icon: string;
  themeClass: 'secondary' | 'primary' | 'tertiary';
}

export interface RecommendationMatch {
  id: string;
  title: string;
  description: string;
  score: number;
  reasons: string[];
}

export interface AppState {
  currentUser: UserProfile;
  myGames: GameProject[];
  savedDiscoveries: SavedDiscovery[];
  currentBuildParams: BuildParams;
  currentPrompt: string;
  buildStatus: 'IDLE' | 'COMPILING' | 'SUCCESS' | 'ERROR';
  compilerLogs: string[];
  recommendations: RecommendationMatch[];
}

export interface AppContextType {
  state: AppState;
  setPrompt: (prompt: string) => void;
  updateBuildParams: (params: Partial<BuildParams>) => void;
  setBuildStatus: (status: AppState['buildStatus']) => void;
  addGameProject: (project: GameProject) => void;
  setState: React.Dispatch<React.SetStateAction<AppState>>;
  compileProject: (navigate: (path: string) => void) => void;
  clearCompilerLogs: () => void;
  fetchRecommendations: (prompt: string) => Promise<RecommendationMatch[]>;
}
