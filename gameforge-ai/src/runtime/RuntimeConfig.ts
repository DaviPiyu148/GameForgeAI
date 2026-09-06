import type {
  EntityDef,
  GameArchetype,
  GameDSL,
  ObjectiveDef,
  OpenWorldDef,
  RuleDef,
  WorldMode,
} from './types';
import { resolveArchetypePolicy, type ArchetypePolicy } from './ArchetypePolicy';

export type ScaleTier = 'prototype' | 'standard' | 'campaign';

export interface ScaleProfile {
  tier: ScaleTier;
  levelCountRange: [number, number];
  entitiesPerLevelRange: [number, number];
  rulesPerLevelRange: [number, number];
  maxLevels: number;
  entityBudgetMultiplier: number;
  waveScalingFactor: number;
}

export interface RuntimeStageConfig {
  stageIndex: number;
  stageNumber: number;
  title: string;
  theme: string;
  backgroundColor: string;
  worldBounds: { width: number; height: number };
  gravityY: number;
  playerSpawn: { x: number; y: number };
  objective: ObjectiveDef;
  entities: EntityDef[];
  rules: RuleDef[];
  maxWaves: number;
  isFinale: boolean;
}

export interface RuntimeOpenWorldConfig {
  openWorldDef: OpenWorldDef;
  initialRegionId: string;
}

export interface RuntimeGameConfig {
  seed: number;
  archetypePolicy: ArchetypePolicy;
  worldMode: WorldMode;
  scaleProfile: ScaleProfile;
  stages: RuntimeStageConfig[];
  openWorldConfig?: RuntimeOpenWorldConfig;
  rawDsl: GameDSL;
}

export interface CompilationResult {
  success: boolean;
  config?: RuntimeGameConfig;
  error?: string;
  warnings?: string[];
}

const SCALE_PROFILES: Record<ScaleTier, ScaleProfile> = {
  prototype: {
    tier: 'prototype',
    levelCountRange: [1, 2],
    entitiesPerLevelRange: [4, 8],
    rulesPerLevelRange: [2, 5],
    maxLevels: 2,
    entityBudgetMultiplier: 0.8,
    waveScalingFactor: 1.0,
  },
  standard: {
    tier: 'standard',
    levelCountRange: [2, 3],
    entitiesPerLevelRange: [8, 14],
    rulesPerLevelRange: [3, 8],
    maxLevels: 3,
    entityBudgetMultiplier: 1.0,
    waveScalingFactor: 1.2,
  },
  campaign: {
    tier: 'campaign',
    levelCountRange: [3, 5],
    entitiesPerLevelRange: [10, 20],
    rulesPerLevelRange: [4, 12],
    maxLevels: 5,
    entityBudgetMultiplier: 1.3,
    waveScalingFactor: 1.5,
  },
};

export class RuntimeConfigCompiler {
  /**
   * Compiles and validates a raw GameDSL into an authoritative, strongly-typed RuntimeGameConfig.
   */
  public static compile(dsl: GameDSL, seedOverride?: number): CompilationResult {
    const warnings: string[] = [];

    if (!dsl || typeof dsl !== 'object') {
      return { success: false, error: 'Invalid GameDSL payload: null or not an object.' };
    }

    if (!dsl.metadata || !dsl.player || !dsl.world) {
      return { success: false, error: 'Malformed GameDSL: missing required metadata, player, or world root nodes.' };
    }

    // Validate Archetype
    if (!dsl.metadata.archetype || typeof dsl.metadata.archetype !== 'string' || !dsl.metadata.archetype.trim()) {
      return { success: false, error: 'Malformed GameDSL: missing required metadata.archetype.' };
    }
    const archetype = dsl.metadata.archetype.toLowerCase().trim() as GameArchetype;
    const validArchetypes: GameArchetype[] = ['platformer', 'arena', 'shooter', 'collector', 'survival', 'runner'];
    if (!validArchetypes.includes(archetype)) {
      return {
        success: false,
        error: `Unsupported archetype '${dsl.metadata.archetype}'. Expected one of: ${validArchetypes.join(', ')}.`,
      };
    }

    // Validate Player Attack Type if specified
    if (dsl.player.attack_type) {
      const validAttacks = ['melee', 'ranged', 'aoe', 'none'];
      if (!validAttacks.includes(dsl.player.attack_type)) {
        return {
          success: false,
          error: `Invalid player attack type '${dsl.player.attack_type}'. Expected one of: ${validAttacks.join(', ')}.`,
        };
      }
    }

    const worldGravity = dsl.world.gravity ?? 0;
    const archetypePolicy = resolveArchetypePolicy(archetype, worldGravity);

    // Resolve World Mode - world.world_mode is authoritative
    let worldMode: WorldMode;
    if (dsl.world.world_mode) {
      const modeRaw = dsl.world.world_mode.toLowerCase().trim();
      const validModes: WorldMode[] = ['linear', 'campaign', 'open_world'];
      if (!validModes.includes(modeRaw as WorldMode)) {
        return {
          success: false,
          error: `Unsupported world mode '${dsl.world.world_mode}'. Expected one of: ${validModes.join(', ')}.`,
        };
      }
      worldMode = modeRaw as WorldMode;
    } else {
      worldMode = (dsl.levels && dsl.levels.length > 1 ? 'campaign' : (dsl.open_world ? 'open_world' : 'linear'));
    }

    // Validation: Campaign mode requires non-empty levels array
    if (worldMode === 'campaign' && (!dsl.levels || dsl.levels.length === 0)) {
      return {
        success: false,
        error: 'Malformed Campaign GameDSL: world_mode is campaign but levels array is missing or empty.',
      };
    }

    // Validation: Open World mode requires valid open_world definition with regions
    if (worldMode === 'open_world' && (!dsl.open_world || !dsl.open_world.regions || dsl.open_world.regions.length === 0)) {
      return {
        success: false,
        error: 'Malformed Open World GameDSL: open_world configuration missing or contains no regions.',
      };
    }

    // Incompatibility check: Platformer and Runner cannot run in Open World mode
    if ((archetypePolicy.isPlatformer || archetype === 'runner' || archetypePolicy.prohibitedSystems.includes('OPEN_WORLD_REGIONS')) && worldMode === 'open_world') {
      return {
        success: false,
        error: `Incompatible game configuration: Archetype '${archetypePolicy.displayName}' cannot run in Open World mode.`,
      };
    }

    // Validate entities across root and levels
    const allEntities = [...(dsl.entities || [])];
    if (dsl.levels) {
      for (const lvl of dsl.levels) {
        allEntities.push(...(lvl.entities || []));
      }
    }
    const validEntityTypes = ['enemy', 'collectible', 'obstacle', 'platform', 'hazard'];
    for (const ent of allEntities) {
      if (!ent.id || typeof ent.id !== 'string') {
        return { success: false, error: `Invalid entity: entity missing required 'id'.` };
      }
      if (!ent.type || !validEntityTypes.includes(ent.type)) {
        return {
          success: false,
          error: `Invalid entity '${ent.id}': unknown type '${ent.type}'. Expected one of: ${validEntityTypes.join(', ')}.`,
        };
      }
    }

    // Validate level objectives if present
    const validObjectiveTypes = ['collect_all', 'defeat_all', 'reach_exit', 'survive_time', 'score_target'];
    if (dsl.levels) {
      for (let i = 0; i < dsl.levels.length; i++) {
        const lvl = dsl.levels[i];
        if (lvl.objective && !validObjectiveTypes.includes(lvl.objective.type)) {
          return {
            success: false,
            error: `Malformed objective type '${lvl.objective.type}' in level ${i + 1}. Expected one of: ${validObjectiveTypes.join(', ')}.`,
          };
        }
      }
    }

    // Resolve Seed
    const seed = seedOverride ?? dsl.world.procedural_seed ?? 18492031;

    // Resolve Scale Tier from canonical scale_tiers.py definition
    const rawScale = ((dsl.metadata as any)?.scale || '').toLowerCase().trim();
    let scaleTier: ScaleTier = 'standard';
    if (rawScale === 'prototype' || rawScale === 'standard' || rawScale === 'campaign') {
      scaleTier = rawScale;
    } else if (dsl.levels && dsl.levels.length >= 4) {
      scaleTier = 'campaign';
    } else if (dsl.levels && dsl.levels.length <= 1 && (dsl.entities || []).length <= 6) {
      scaleTier = 'prototype';
    }
    const scaleProfile = SCALE_PROFILES[scaleTier];
    const MAX_WAVES_BY_TIER: Record<ScaleTier, number> = {
      prototype: 3,
      standard: 5,
      campaign: 8,
    };
    const maxAllowedWaves = MAX_WAVES_BY_TIER[scaleTier];

    // Compile Stages (Multi-Level / Campaign support)
    const stages: RuntimeStageConfig[] = [];
    const rawLevels = dsl.levels && dsl.levels.length > 0 ? dsl.levels : null;

    if (rawLevels) {
      if (rawLevels.length > scaleProfile.maxLevels) {
        return {
          success: false,
          error: `Scale tier '${scaleTier}' allows a maximum of ${scaleProfile.maxLevels} levels, but received ${rawLevels.length}.`,
        };
      }

      for (let i = 0; i < rawLevels.length; i++) {
        const lvl = rawLevels[i];
        const lvlWorld = lvl.world || dsl.world;
        const stageBounds = {
          width: lvlWorld.width || dsl.world.width || 800,
          height: lvlWorld.height || dsl.world.height || 600,
        };
        const stageGravity = lvlWorld.gravity ?? dsl.world.gravity ?? archetypePolicy.defaultGravity;
        const stageSpawn = {
          x: lvl.spawn_x ?? dsl.player.spawn_x ?? Math.floor(stageBounds.width / 2),
          y: lvl.spawn_y ?? dsl.player.spawn_y ?? Math.floor(stageBounds.height / 2),
        };

        // Resolve stage rules (stage-local rules take priority; fallback to root dsl.rules)
        const stageRules = lvl.rules && lvl.rules.length > 0 ? lvl.rules : (dsl.rules || []);

        // Derive stage objective intelligently
        const stageEntities = lvl.entities || [];
        const stageCollectibles = stageEntities.filter((e) => e.type === 'collectible');
        const stageEnemies = stageEntities.filter((e) => e.type === 'enemy');
        const stageExitEntity = stageEntities.find((e) => e.id.toLowerCase().includes('exit') || e.id.toLowerCase().includes('goal') || e.id.toLowerCase().includes('beacon'));
        const hasGoalRule = (stageRules || []).some((r) => r.trigger === 'on_reach_goal');

        let stageObjective: ObjectiveDef;
        if (lvl.objective) {
          stageObjective = lvl.objective;
        } else if ((archetypePolicy.isPlatformer || hasGoalRule) && stageExitEntity) {
          stageObjective = {
            type: 'reach_exit',
            target_entity_id: stageExitEntity.id,
            exit_x: stageExitEntity.x,
            exit_y: stageExitEntity.y,
            exit_radius: Math.max(stageExitEntity.width, stageExitEntity.height) * 1.5,
            description: lvl.title ? `Reach the beacon in ${lvl.title}` : 'Reach the goal',
          };
        } else if (archetypePolicy.allowsEnemyWaves) {
          stageObjective = {
            type: 'survive_time',
            time_limit_seconds: 30,
            description: lvl.title ? `Survive in ${lvl.title}` : 'Survive incoming waves',
          };
        } else if (stageCollectibles.length > 0) {
          stageObjective = {
            type: 'collect_all',
            target_count: stageCollectibles.length,
            description: lvl.title ? `Collect all items in ${lvl.title}` : 'Collect all items',
          };
        } else if (stageEnemies.length > 0) {
          stageObjective = {
            type: 'defeat_all',
            target_count: stageEnemies.length,
            description: lvl.title ? `Defeat all enemies in ${lvl.title}` : 'Defeat all enemies',
          };
        } else {
          stageObjective = {
            type: 'score_target',
            target_score: 500,
            description: lvl.title ? `Score 500 points in ${lvl.title}` : 'Reach target score',
          };
        }

        if (stageEntities.length > 30) {
          return {
            success: false,
            error: `Level ${i + 1} exceeds maximum entity budget (found ${stageEntities.length}, maximum allowed is 30).`,
          };
        }
        if (stageRules.length > 15) {
          return {
            success: false,
            error: `Level ${i + 1} exceeds maximum rule budget (found ${stageRules.length}, maximum allowed is 15).`,
          };
        }

        const stageMaxWaves = archetypePolicy.allowsEnemyWaves
          ? (lvlWorld.wave_count ?? dsl.world.wave_count ?? 3)
          : 1;

        if (stageMaxWaves > maxAllowedWaves) {
          return {
            success: false,
            error: `Scale tier '${scaleTier}' allows a maximum of ${maxAllowedWaves} waves, but level ${i + 1} requested ${stageMaxWaves}.`,
          };
        }

        stages.push({
          stageIndex: i,
          stageNumber: lvl.level_number || i + 1,
          title: lvl.title || `Level ${i + 1}`,
          theme: lvl.theme || lvlWorld.theme || dsl.world.theme || 'neon',
          backgroundColor: lvlWorld.background_color || dsl.world.background_color || '#0a0b10',
          worldBounds: stageBounds,
          gravityY: stageGravity,
          playerSpawn: stageSpawn,
          objective: stageObjective,
          entities: stageEntities,
          rules: stageRules,
          maxWaves: stageMaxWaves,
          isFinale: Boolean(lvl.is_finale || i === rawLevels.length - 1),
        });
      }
    } else {
      // Single Stage / Linear Mode
      const stageBounds = {
        width: dsl.world.width || 800,
        height: dsl.world.height || 600,
      };
      const stageGravity = dsl.world.gravity ?? archetypePolicy.defaultGravity;
      const stageSpawn = {
        x: dsl.player.spawn_x ?? Math.floor(stageBounds.width / 2),
        y: dsl.player.spawn_y ?? Math.floor(stageBounds.height / 2),
      };

      const stageEntities = dsl.entities || [];
      const stageCollectibles = stageEntities.filter((e) => e.type === 'collectible');
      const stageEnemies = stageEntities.filter((e) => e.type === 'enemy');
      const stageExitEntity = stageEntities.find((e) => e.id.toLowerCase().includes('exit') || e.id.toLowerCase().includes('goal') || e.id.toLowerCase().includes('beacon'));
      const hasGoalRule = (dsl.rules || []).some((r) => r.trigger === 'on_reach_goal');

      if (stageEntities.length > 30) {
        return {
          success: false,
          error: `Stage exceeds maximum entity budget (found ${stageEntities.length}, maximum allowed is 30).`,
        };
      }
      if ((dsl.rules || []).length > 15) {
        return {
          success: false,
          error: `Stage exceeds maximum rule budget (found ${(dsl.rules || []).length}, maximum allowed is 15).`,
        };
      }

      let defaultObjective: ObjectiveDef;
      if ((archetypePolicy.isPlatformer || hasGoalRule) && stageExitEntity) {
        defaultObjective = {
          type: 'reach_exit',
          target_entity_id: stageExitEntity.id,
          exit_x: stageExitEntity.x,
          exit_y: stageExitEntity.y,
          exit_radius: Math.max(stageExitEntity.width, stageExitEntity.height) * 1.5,
          description: dsl.design_spec?.primary_objective || 'REACH THE GOAL',
        };
      } else if (archetypePolicy.allowsEnemyWaves) {
        defaultObjective = {
          type: 'survive_time',
          time_limit_seconds: 30,
          description: dsl.design_spec?.primary_objective || 'SURVIVE',
        };
      } else if (stageCollectibles.length > 0) {
        defaultObjective = {
          type: 'collect_all',
          target_count: stageCollectibles.length,
          description: dsl.design_spec?.primary_objective || 'COLLECT ALL ITEMS',
        };
      } else if (stageEnemies.length > 0) {
        defaultObjective = {
          type: 'defeat_all',
          target_count: stageEnemies.length,
          description: dsl.design_spec?.primary_objective || 'DEFEAT ALL ENEMIES',
        };
      } else {
        defaultObjective = {
          type: 'score_target',
          target_score: 500,
          description: dsl.design_spec?.primary_objective || 'SCORE 500 POINTS',
        };
      }

      const stageMaxWaves = archetypePolicy.allowsEnemyWaves ? (dsl.world.wave_count ?? 3) : 1;
      if (stageMaxWaves > maxAllowedWaves) {
        return {
          success: false,
          error: `Scale tier '${scaleTier}' allows a maximum of ${maxAllowedWaves} waves, but stage requested ${stageMaxWaves}.`,
        };
      }

      stages.push({
        stageIndex: 0,
        stageNumber: 1,
        title: dsl.metadata.title || 'Stage 1',
        theme: dsl.world.theme || 'neon',
        backgroundColor: dsl.world.background_color || '#0a0b10',
        worldBounds: stageBounds,
        gravityY: stageGravity,
        playerSpawn: stageSpawn,
        objective: defaultObjective,
        entities: stageEntities,
        rules: dsl.rules || [],
        maxWaves: stageMaxWaves,
        isFinale: true,
      });
    }

    // Resolve Open World Config if applicable
    let openWorldConfig: RuntimeOpenWorldConfig | undefined;
    if (worldMode === 'open_world' && dsl.open_world) {
      if (dsl.open_world.regions && dsl.open_world.regions.length > 6) {
        return {
          success: false,
          error: `Open World configuration allows a maximum of 6 regions, but received ${dsl.open_world.regions.length}.`,
        };
      }
      if (dsl.open_world.actors) {
        for (const actor of dsl.open_world.actors) {
          if (actor.schedules && actor.schedules.length > 0) {
            return {
              success: false,
              error: `Unsupported open-world feature: Actor '${actor.id}' declares schedules, which are not supported by the Phaser runtime kernel.`,
            };
          }
        }
      }
      if (dsl.open_world.events) {
        for (const event of dsl.open_world.events) {
          const rawEvt = event as any;
          if (
            rawEvt.modifiers ||
            rawEvt.event_modifiers ||
            rawEvt.player_speed_modifier ||
            rawEvt.enemy_damage_modifier
          ) {
            return {
              success: false,
              error: `Unsupported open-world feature: Event '${event.id}' declares dynamic physics/stat modifiers, which are not supported by the Phaser runtime kernel.`,
            };
          }
        }
      }

      if (dsl.open_world.regions && dsl.open_world.regions.length > 0) {
        const firstRegId = dsl.open_world.regions[0].id;
        openWorldConfig = {
          openWorldDef: dsl.open_world,
          initialRegionId: firstRegId,
        };
      }
    }

    const config: RuntimeGameConfig = {
      seed,
      archetypePolicy,
      worldMode,
      scaleProfile,
      stages,
      openWorldConfig,
      rawDsl: dsl,
    };

    return {
      success: true,
      config,
      warnings: warnings.length > 0 ? warnings : undefined,
    };
  }
}
