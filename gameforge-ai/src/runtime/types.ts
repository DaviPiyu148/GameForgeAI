export type Archetype = 'survival' | 'shooter' | 'platformer' | 'collector' | 'arena' | 'runner';

export type EntityType = 'enemy' | 'collectible' | 'obstacle' | 'platform' | 'hazard';

export type EntityBehavior =
  | 'patrol'
  | 'chase'
  | 'stationary'
  | 'bounce'
  | 'float'
  | 'flee'
  | 'guard'
  | 'ranged_attack';

export type RuleTrigger =
  | 'on_collect'
  | 'on_collide_enemy'
  | 'on_reach_goal'
  | 'on_score_target'
  | 'on_time_limit'
  | 'on_player_death'
  | 'on_wave_start'
  | 'on_dash'
  | 'on_hazard_touch'
  | 'on_enemy_defeat'
  | 'on_checkpoint'
  | 'on_powerup_expire';

export type RuleAction =
  | 'add_score'
  | 'damage_player'
  | 'heal_player'
  | 'win_game'
  | 'lose_game'
  | 'spawn_entity'
  | 'speed_boost'
  | 'trigger_screen_shake'
  | 'spawn_wave'
  | 'grant_powerup'
  | 'activate_checkpoint'
  | 'spawn_particles'
  | 'knockback_target';

export interface CoreLoopSpec {
  player_action: string;
  immediate_feedback?: string;
  increasing_pressure?: string;
  progression?: string;
  resolution?: string;
}

export interface ObjectiveSpec {
  primary: string;
  supporting?: string[];
  completion_criteria?: string;
  failure_condition?: string;
}

export interface ProgressionPhase {
  phase: 'EARLY' | 'MID' | 'FINALE';
  trigger: string;
  description: string;
  runtime_effect: string;
}

export interface GameDesignSpec {
  title: string;
  elevator_pitch: string;
  genre: string;
  subgenre?: string;
  theme: 'cyberpunk' | 'retro_arcade' | 'dungeon' | 'space' | 'neon' | 'minimal';
  visual_style?: string;
  camera?: 'top_down' | 'side_view' | 'fixed_arena';
  core_gameplay_loop: string;
  player_role: string;
  primary_objective: string;
  secondary_objectives?: string[];
  player_abilities?: string[];
  enemy_archetypes?: Record<string, any>[];
  hazards?: Record<string, any>[];
  collectibles?: Record<string, any>[];
  progression?: Record<string, any>;
  difficulty_curve?: 'gentle' | 'escalating' | 'challenging';
  win_conditions?: string[];
  loss_conditions?: string[];
  level_structure?: Record<string, any>;
  estimated_session_length?: string;
  selected_modules?: string[];
  rationale?: string[];
  loop_details?: CoreLoopSpec;
  objective_details?: ObjectiveSpec;
  progression_phases?: ProgressionPhase[];
}

export interface GameMetadata {
  title: string;
  genre: string;
  description: string;
  archetype: Archetype;
}

export interface WorldDef {
  width: number;
  height: number;
  gravity: number;
  background_color: string;
  theme: 'cyberpunk' | 'retro_arcade' | 'dungeon' | 'space' | 'neon' | 'minimal';
  difficulty_scaling?: number;
  wave_count?: number;
  procedural_seed?: number;
  hazard_density?: number;
}

export interface PlayerDef {
  name?: string;
  spawn_x: number;
  spawn_y: number;
  speed: number;
  jump_power: number;
  max_health: number;
  width: number;
  height: number;
  color: string;
  dash_speed?: number;
  dash_cooldown?: number;
  stamina?: number;
  attack_type?: 'melee' | 'ranged' | 'aoe' | 'none';
  attack_damage?: number;
  attack_cooldown?: number;
  weapon_color?: string;
}

export interface EntityDef {
  id: string;
  type: EntityType;
  x: number;
  y: number;
  width: number;
  height: number;
  speed: number;
  health: number;
  behavior: EntityBehavior;
  color: string;
  points: number;
  damage?: number;
  fire_rate?: number;
  patrol_radius?: number;
  detection_radius?: number;
  loot_drop?: string | null;
}

export interface RuleDef {
  id: string;
  trigger: RuleTrigger;
  action: RuleAction;
  params: Record<string, number | string | boolean>;
}

export interface UIDef {
  show_health: boolean;
  show_score: boolean;
  show_stamina?: boolean;
  show_wave?: boolean;
  show_objectives?: boolean;
  status_text: string;
}

export interface GameDSL {
  schema_version: string;
  metadata: GameMetadata;
  world: WorldDef;
  player: PlayerDef;
  entities: EntityDef[];
  rules: RuleDef[];
  ui: UIDef;
  design_spec?: GameDesignSpec;
}

export interface RuntimeMetadata {
  rendererVersion: string;
  phaserVersion: string;
  dslSchemaVersion: string;
  seed: number;
  provider?: string;
  model?: string;
  fallbackUsed?: boolean;
  fallbackReason?: string;
}

export type GameState = 'READY' | 'PLAYING' | 'PAUSED' | 'WON' | 'LOST';

// --- Telemetry & Playtest Types ---
export type TelemetryEventType =
  | 'SESSION_STARTED'
  | 'SESSION_START'
  | 'SESSION_ENDED'
  | 'SESSION_END'
  | 'PLAYER_DAMAGED'
  | 'PLAYER_DAMAGE'
  | 'PLAYER_DIED'
  | 'PLAYER_DEATH'
  | 'OBJECTIVE_PROGRESS'
  | 'OBJECTIVE_COMPLETED'
  | 'WAVE_STARTED'
  | 'WAVE_COMPLETED'
  | 'PHASE_STARTED'
  | 'COLLECTIBLE_COLLECTED'
  | 'ITEM_COLLECTED'
  | 'ENEMY_SPAWNED'
  | 'ENEMY_DEFEATED'
  | 'PROJECTILE_FIRED'
  | 'CHECKPOINT_REACHED'
  | 'GAME_WON'
  | 'GAME_LOST'
  | 'SCORE_CHANGED';

export interface TelemetryEvent {
  type: TelemetryEventType;
  timestamp: number;
  data?: Record<string, any>;
}

export interface PlaytestSummary {
  duration_seconds: number;
  score: number;
  damage_taken: number;
  damage_dealt: number;
  enemies_defeated: number;
  collectibles_gathered: number;
  objectives_completed: number;
  outcome: 'WON' | 'LOST' | 'ABANDONED' | 'PLAYED';
  waves_reached?: number;
  phase_reached?: string;
  version_number?: number;
  seed?: number;
  telemetry_events?: TelemetryEvent[];
}

export interface PlaytestProblem {
  category: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
  evidence: string;
  diagnosis: string;
}

export interface PlaytestRecommendation {
  id: string;
  category: string;
  description: string;
  dsl_change_type: string;
  evidence?: string;
  suggested_patch: Record<string, any>;
}

export interface PlaytestAnalysis {
  fun_rating: number;
  difficulty_rating: number;
  clarity_rating: number;
  strengths: string[];
  problems: (string | PlaytestProblem)[];
  recommendations: PlaytestRecommendation[];
}
