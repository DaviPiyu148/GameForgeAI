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
  theme: 'cyberpunk' | 'retro_arcade' | 'dungeon' | 'space' | 'neon' | 'minimal' | 'wasteland' | 'urban' | 'colony' | 'fantasy';
  difficulty_scaling?: number;
  wave_count?: number;
  procedural_seed?: number;
  hazard_density?: number;
  world_mode?: 'linear' | 'campaign' | 'open_world';
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
  is_boss?: boolean;
  boss_phases?: number;
  telegraph_ms?: number;
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

export interface ObjectiveDef {
  type: 'collect_all' | 'defeat_all' | 'reach_exit' | 'survive_time' | 'score_target';
  target_count?: number;
  target_score?: number;
  time_limit_seconds?: number;
  exit_x?: number;
  exit_y?: number;
  description?: string;
}

export interface LevelDef {
  level_number: number;
  title: string;
  theme?: 'cyberpunk' | 'retro_arcade' | 'dungeon' | 'space' | 'neon' | 'minimal' | 'wasteland' | 'urban' | 'colony' | 'fantasy';
  world?: WorldDef;
  spawn_x?: number;
  spawn_y?: number;
  objective?: ObjectiveDef;
  entities: EntityDef[];
  rules?: RuleDef[];
  completion_message?: string;
  is_finale?: boolean;
}

// --- Phase 6: Generalized Open World Runtime Interfaces ---
export interface RegionDef {
  id: string;
  name: string;
  theme: string;
  bounds_x?: number;
  bounds_y?: number;
  width: number;
  height: number;
  danger_level: number;
  population_density?: number;
  controlling_faction?: string | null;
  traversal_connections?: string[];
  background_color?: string | null;
  ambient_theme?: string | null;
}

export interface WorldConnectionDef {
  from_region: string;
  to_region: string;
  bidirectional?: boolean;
  traversal_types?: ('on_foot' | 'vehicle' | 'fast_travel')[];
  required_state_key?: string | null;
}

export interface POIDef {
  id: string;
  name: string;
  type:
    | 'safehouse'
    | 'shop'
    | 'garage'
    | 'outpost'
    | 'terminal'
    | 'landmark'
    | 'hospital'
    | 'mission_giver'
    | 'dungeon'
    | 'station'
    | 'hideout'
    | 'arena'
    | 'resource_node';
  region_id: string;
  x: number;
  y: number;
  icon?: string | null;
  discovered?: boolean;
  activity_ids?: string[];
  interaction_text?: string | null;
}

export interface ActivityPrerequisite {
  min_reputation?: Record<string, number>;
  required_state?: Record<string, number | string | boolean>;
  completed_activities?: string[];
}

export interface ActivityConsequence {
  reputation_changes?: Record<string, number>;
  threat_change?: number;
  state_mutations?: Record<string, number | string | boolean>;
  unlock_regions?: string[];
  unlock_pois?: string[];
  message?: string | null;
}

export interface ActivityDef {
  id: string;
  title: string;
  description: string;
  type:
    | 'mission'
    | 'delivery'
    | 'race'
    | 'combat'
    | 'collection'
    | 'investigation'
    | 'escort'
    | 'patrol'
    | 'exploration'
    | 'minigame';
  region_id?: string | null;
  start_poi_id?: string | null;
  target_poi_id?: string | null;
  target_actor_id?: string | null;
  target_count?: number;
  time_limit_seconds?: number;
  prerequisites?: ActivityPrerequisite;
  rewards?: Record<string, number | string | boolean>;
  success_consequences?: ActivityConsequence;
  failure_consequences?: ActivityConsequence | null;
  status?: 'available' | 'active' | 'completed' | 'failed' | 'locked';
}

export interface ScheduleDef {
  start_hour: number;
  end_hour: number;
  region_id: string;
  poi_id?: string | null;
  activity_name?: string;
}

export interface ActorDef {
  id: string;
  name: string;
  archetype:
    | 'civilian'
    | 'guard'
    | 'security'
    | 'merchant'
    | 'quest_giver'
    | 'hostile'
    | 'companion'
    | 'patrol'
    | 'courier';
  faction_id?: string | null;
  region_id: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  health?: number;
  speed?: number;
  behavior: EntityBehavior;
  color?: string;
  dialogue?: string | null;
  schedules?: ScheduleDef[];
  gives_activity_id?: string | null;
}

export interface FactionDef {
  id: string;
  name: string;
  description?: string | null;
  initial_reputation?: number;
  hostility_threshold?: number;
  controlled_regions?: string[];
  color?: string;
  alert_unit_archetype?: string | null;
}

export interface VehicleDef {
  id: string;
  name: string;
  type: 'car' | 'bike' | 'hovercraft' | 'truck' | 'speedster' | 'mount' | 'cart' | 'buggy';
  region_id: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  max_speed: number;
  acceleration?: number;
  handling?: number;
  health?: number;
  color?: string;
  traversal_mode?: 'ground' | 'hover' | 'water';
  is_occupied?: boolean;
}

export interface ThreatResponseUnitDef {
  min_threat_level: number;
  archetype: string;
  count: number;
  faction_id?: string | null;
  behavior: EntityBehavior;
}

export interface ThreatSystemDef {
  name: string;
  current_level: number;
  max_level: number;
  decay_rate_per_sec: number;
  escalation_events?: string[];
  response_units?: ThreatResponseUnitDef[];
}

export interface WorldTimeDef {
  start_hour: number;
  time_scale: number;
  day_night_cycle?: boolean;
}

export interface WorldEventDef {
  id: string;
  name: string;
  type:
    | 'faction_conflict'
    | 'roadblock'
    | 'security_lockdown'
    | 'convoy'
    | 'storm'
    | 'market_surge'
    | 'swarm_attack'
    | 'festival';
  region_ids?: string[];
  trigger_state_key?: string | null;
  duration_seconds: number;
  active?: boolean;
  threat_modifier?: number;
  danger_modifier?: number;
  description?: string | null;
}

export interface OpenWorldDef {
  regions: RegionDef[];
  connections?: WorldConnectionDef[];
  factions: FactionDef[];
  pois: POIDef[];
  activities: ActivityDef[];
  vehicles: VehicleDef[];
  actors: ActorDef[];
  threat_system?: ThreatSystemDef;
  time_system?: WorldTimeDef;
  events?: WorldEventDef[];
  initial_state?: Record<string, number | string | boolean>;
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
  levels?: LevelDef[];
  open_world?: OpenWorldDef;
}

export interface RuntimeMetadata {
  rendererVersion?: string;
  phaserVersion?: string;
  dslSchemaVersion?: string;
  seed: number;
  provider?: string;
  model?: string;
  fallbackUsed?: boolean;
  fallbackReason?: string;
  version_number?: number;
  project_id?: string;
  archetype?: string;
  engine?: string;
  compiled_at?: string;
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
  | 'SCORE_CHANGED'
  | 'REGION_ENTERED'
  | 'POI_DISCOVERED'
  | 'ACTIVITY_STARTED'
  | 'ACTIVITY_COMPLETED'
  | 'ACTIVITY_FAILED'
  | 'VEHICLE_ENTERED'
  | 'VEHICLE_EXITED'
  | 'ALERT_CHANGED'
  | 'FACTION_REPUTATION_CHANGED'
  | 'WORLD_EVENT_STARTED'
  | 'WORLD_EVENT_ENDED';

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
  is_actionable?: boolean;
}

export interface PlaytestAnalysis {
  fun_rating: number;
  difficulty_rating: number;
  clarity_rating: number;
  strengths: string[];
  problems: (string | PlaytestProblem)[];
  recommendations: PlaytestRecommendation[];
}
