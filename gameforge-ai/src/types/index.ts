import type { GameDSL, GameDesignSpec, RuntimeMetadata } from '../runtime/types';
export type { PlaytestSummary, PlaytestAnalysis, PlaytestRecommendation } from '../runtime/types';

export type ProjectStatus = 'PLAYABLE' | 'COMPILING' | 'ERROR';

export interface BuildParams {
  engine: string;
  artDensity: number;
  physics: number;
  modules: string[];
  scale?: 'prototype' | 'standard' | 'campaign';
  world_mode?: 'linear' | 'campaign' | 'open_world';
  worldMode?: 'linear' | 'campaign' | 'open_world';
}

export interface GameProject {
  id: string;
  title: string;
  genre: string;
  status: ProjectStatus;
  lastModified: string;
  parameters: BuildParams;
  prompt: string;
  designSpec?: GameDesignSpec;
  gameDsl?: GameDSL;
  runtimeMetadata?: RuntimeMetadata;
  currentVersion?: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface ProjectUpdateInput {
  title?: string;
  genre?: string;
  prompt?: string;
  parameters?: BuildParams;
  designSpec?: GameDesignSpec;
  gameDsl?: GameDSL;
  runtimeMetadata?: RuntimeMetadata;
}

export interface UserProfile {
  id: string;
  username: string;
  level: number;
  avatarPlaceholder: string;
  avatar_url?: string | null;
}

// --- Backend Auth Types (Phase B7 & V3) ---
export type AuthStatus = 'IDLE' | 'AUTHENTICATED' | 'UNAUTHENTICATED' | 'LOADING';

export interface AuthUser {
  id: string;
  email: string;
  username: string;
  level: number;
  avatar_url?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface XPEventItem {
  id: string;
  event_type: string;
  xp_amount: number;
  source_reference?: string | null;
  created_at: string;
}

export interface MilestoneItem {
  milestone_key: string;
  title: string;
  description: string;
  icon: string;
  xp_bonus: number;
  is_unlocked: boolean;
  unlocked_at?: string | null;
}

export interface UserProgressData {
  user_id: string;
  total_xp: number;
  current_level: number;
  creator_title: string;
  current_level_base_xp: number;
  next_level_xp: number;
  xp_into_level: number;
  xp_needed_for_next: number;
  progress_percentage: number;
  milestones: MilestoneItem[];
  unlocked_milestone_count: number;
  total_milestone_count: number;
  recent_events: XPEventItem[];
}

export interface GenreAffinityItem {
  genre: string;
  score: number;
  percentage: number;
  interaction_count: number;
  affinity_tier: 'High' | 'Moderate' | 'Emerging';
}

export interface UserPreferencesData {
  user_id: string;
  top_genres: GenreAffinityItem[];
  total_interactions: number;
  strongest_match?: string | null;
  recent_interest?: string | null;
  avoidances?: string[];
  suggested_explorations?: string[];
  confidence_level?: 'LOW' | 'MODERATE' | 'HIGH';
  summary_headline?: string | null;
  has_sufficient_data: boolean;
}

export interface CompareGamesResponse {
  games: GameDiscoveryItem[];
  common_genres: string[];
  common_tags: string[];
  common_modes: string[];
  differentiating_tags: string[];
}


export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  user: AuthUser;
  access_token: string;
  token_type: string;
}

// --- Backend Saved Discovery Types (Phase B7) ---
export interface BackendSavedDiscovery {
  id: string;
  user_id: string;
  steam_app_id: string;
  title: string;
  genres: string[];
  created_at: string;
}

export interface SavedDiscoveryListResponse {
  discoveries: BackendSavedDiscovery[];
}

// Kept for backward compatibility with UI components if needed
export interface SavedDiscovery {
  id: string;
  matchPercentage: number;
  savedDate: string;
  title: string;
  author: string;
  icon: string;
  themeClass: 'secondary' | 'primary' | 'tertiary';
}

// --- Backend Build Types ---
export type BackendBuildStatus = 'QUEUED' | 'RUNNING' | 'VALIDATING' | 'SUCCESS' | 'ERROR' | 'CANCELLED';

export interface BuildResponse {
  build_id: string;
  status: BackendBuildStatus;
  project_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  game_dsl?: GameDSL | null;
}

export interface BuildLogEntry {
  sequence: number;
  level: string;
  message: string;
  timestamp: string;
}

export interface BuildLogListResponse {
  build_id: string;
  logs: BuildLogEntry[];
}

// --- Backend Discovery Types ---
export interface DiscoveryFilters {
  platforms?: string[];
  player_modes?: string[];
  genres?: string[];
  tags?: string[];
  is_free?: boolean;
  min_year?: number;
  max_year?: number;
}

export interface DiscoverySessionContext {
  refinements?: string[];
  less_like_this_game_ids?: string[];
  temporary_avoid_tags?: string[];
  temporary_avoid_genres?: string[];
  surprise_seed?: number;
}

export interface DiscoveryFeedbackRequest {
  game_id: string;
  feedback: 'like' | 'dislike' | 'less_like_this';
}

export interface DiscoveryFeedbackResponse {
  status: string;
  game_id: string;
  feedback: string;
  message: string;
}

export interface DiscoverySearchRequest {
  prompt: string;
  limit?: number;
  filters?: DiscoveryFilters;
  mode?: 'BEST_MATCH' | 'DISCOVER' | 'HIDDEN_GEMS' | 'POPULAR';
  session_context?: DiscoverySessionContext;
}

export interface GameEnrichment {
  status: 'AVAILABLE' | 'NOT_FOUND' | 'RATE_LIMITED' | 'UNAVAILABLE';
  igdb_id?: number;
  cover_url?: string;
  screenshot_urls: string[];
  aggregated_rating?: number;
  aggregated_rating_count?: number;
  summary?: string;
  similar_igdb_ids: number[];
}

export interface StorefrontItem {
  provider: string;
  name: string;
  url: string;
  platform?: string;
}

export interface GameDiscoveryItem {
  id: string;
  external_id: string;
  source: string;
  title: string;
  display_title?: string;
  description: string;
  display_description?: string;
  original_description?: string;
  description_language?: string;
  description_source?: 'steam' | 'normalized' | 'igdb' | 'original';
  genres: string[];
  display_genres?: string[];
  original_genres?: string[];
  tags: string[];
  display_tags?: string[];
  original_tags?: string[];
  player_modes: string[];
  platforms: string[];
  release_year: number;
  is_free: boolean;
  total_reviews?: number;
  positive_percent?: number;
  review_score_desc?: string;
  enrichment?: GameEnrichment;
  cover_image_url?: string;
  hero_image_url?: string;
  screenshots?: string[];
  storefronts?: StorefrontItem[];
  developer?: string;
  publisher?: string;
}

export interface DiscoverySearchResult {
  game: GameDiscoveryItem;
  score: number;
  match_highlights: string[];
  explanation: string;
  is_hidden_gem?: boolean;
  trade_offs?: string[];
  personalization_reasons?: string[];
}

export interface DiscoverySearchResponse {
  query: string;
  match_count: number;
  no_strong_match: boolean;
  query_type?: string;
  target_entity?: string | null;
  mode?: 'BEST_MATCH' | 'DISCOVER' | 'HIDDEN_GEMS' | 'POPULAR';
  why_these?: string | null;
  personalized?: boolean;
  personalization_evidence?: string[];
  results: DiscoverySearchResult[];
}


// --- Phase 4: Game Blueprint & Remix ---
export interface BlueprintObjective {
  level_number?: number | null;
  type: string;
  description: string;
}

export interface GameBlueprint {
  project_id: string;
  title: string;
  genre: string;
  archetype: string;
  player_fantasy: string;
  theme: string;
  core_loop: string;
  estimated_session_length: string;
  level_count: number;
  world_area_count: number;
  objectives: BlueprintObjective[];
  progression: string[];
  encounter_types: string[];
  enemy_variety: number;
  finale: string;
  supported_mechanics: string[];
}

// Closed vocabulary of supported remix intents. Deliberately excludes "Add Boss"
// and "More Vehicles" -- those runtime capabilities don't exist until later phases
// (boss/finale system, living-world vehicles), so offering them here would display
// a capability the game can't actually deliver.
export type RemixIntentType =
  | 'increase_combat'
  | 'increase_exploration'
  | 'increase_difficulty'
  | 'decrease_difficulty'
  | 'add_levels'
  | 'more_story'
  | 'faster_pace'
  | 'more_enemies'
  | 'change_theme';

export const REMIX_INTENT_LABELS: Record<RemixIntentType, string> = {
  increase_combat: 'More Combat',
  increase_exploration: 'More Exploration',
  increase_difficulty: 'Harder',
  decrease_difficulty: 'Easier',
  add_levels: 'Add 2 Levels',
  more_story: 'More Story',
  faster_pace: 'Faster Pace',
  more_enemies: 'More Enemies',
  change_theme: 'Different Theme',
};

export interface RemixIntent {
  type: RemixIntentType;
  strength?: number;
}

export interface RemixApplyResponse {
  project_id: string;
  version_number: number;
  game_dsl: GameDSL;
  design_spec?: GameDesignSpec | null;
  blueprint: GameBlueprint;
  change_summary: string;
  status: string;
}

export interface ProjectVersionSummary {
  id: string;
  project_id: string;
  version_number: number;
  change_summary?: string | null;
  created_at: string;
  game_dsl: GameDSL;
  remix_intent?: RemixIntent[] | null;
}

export interface BuildInspirationResponse {
  source_game_id: string;
  title: string;
  inferred_archetype: string;
  inferred_theme: string;
  recommended_prompt: string;
  suggested_art_density?: number;
  suggested_physics?: number;
  suggested_modules: string[];
}

export interface AppError {
  code: string;
  message: string;
}

export interface AppState {
  user: AuthUser | null;
  authStatus: AuthStatus;
  isAuthModalOpen: boolean;
  authModalMode: 'login' | 'register';
  authModalReason?: string;
  postAuthAction?: (() => void) | null;
  myGames: GameProject[];
  savedDiscoveries: BackendSavedDiscovery[];
  isSavedDiscoveriesLoading?: boolean;
  currentBuildParams: BuildParams;
  currentPrompt: string;
  buildStatus: 'IDLE' | 'COMPILING' | 'SUCCESS' | 'ERROR';
  compilerLogs: string[];
  currentBuildId?: string | null;
  activeProjectId?: string | null;
  lastError?: AppError | null;
  isSearching?: boolean;
  discoveryResults?: DiscoverySearchResult[];
  discoveryMode?: 'BEST_MATCH' | 'DISCOVER' | 'HIDDEN_GEMS' | 'POPULAR';
  discoveryResponse?: DiscoverySearchResponse | null;
  discoverySession?: DiscoverySessionContext;
  isProjectsLoading?: boolean;
  projectsError?: string | null;
  progress?: UserProgressData | null;
  preferences?: UserPreferencesData | null;
}

export interface AppContextType {
  state: AppState;
  setPrompt: (prompt: string) => void;
  updateBuildParams: (params: Partial<BuildParams>) => void;
  setBuildStatus: (status: AppState['buildStatus']) => void;
  addGameProject: (project: GameProject) => void;
  updateGameProject: (project: GameProject) => void;
  setState: React.Dispatch<React.SetStateAction<AppState>>;
  compileProject: (navigate: (path: string) => void) => Promise<void>;
  cancelCurrentBuild: () => Promise<void>;
  retryBuild: (navigate: (path: string) => void) => Promise<void>;
  searchDiscovery: (
    prompt: string,
    navigate: (path: string) => void,
    mode?: 'BEST_MATCH' | 'DISCOVER' | 'HIDDEN_GEMS' | 'POPULAR',
    sessionContext?: DiscoverySessionContext
  ) => Promise<void>;
  refreshProjects: () => Promise<void>;
  clearCompilerLogs: () => void;
  // B7 Auth + Saved Discoveries Actions
  openAuthModal: (mode?: 'login' | 'register', reason?: string, onAuthenticated?: () => void) => void;
  closeAuthModal: () => void;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  saveDiscovery: (steamAppId: string) => Promise<void>;
  removeSavedDiscovery: (id: string) => Promise<void>;
  refreshSavedDiscoveries: () => Promise<void>;
  clearDiscoveryResults: () => void;
  // V3 Progression & Preferences Actions
  refreshProgress: () => Promise<void>;
  refreshPreferences: () => Promise<void>;
  uploadAvatar: (file: File) => Promise<string>;
  deleteAvatar: () => Promise<void>;
  updateUsername: (username: string) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  // Sprint A — Project Management
  deleteProject: (id: string) => Promise<void>;
  duplicateProject: (id: string) => Promise<void>;
}

