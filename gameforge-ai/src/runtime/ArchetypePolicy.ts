import type { GameArchetype, PlayerAttackType } from './types';

export interface ArchetypePolicy {
  archetype: GameArchetype;
  displayName: string;
  isPlatformer: boolean;
  movementModel: 'platformer_horizontal' | 'top_down_omnidirectional';
  allowsRangedCombat: boolean;
  allowsMeleeCombat: boolean;
  defaultAttackType: PlayerAttackType;
  allowsEnemyWaves: boolean;
  allowsDash: boolean;
  jumpEnabled: boolean;
  defaultGravity: number;
  prohibitedSystems: string[];
}

const ARCHETYPE_POLICIES: Record<GameArchetype, ArchetypePolicy> = {
  platformer: {
    archetype: 'platformer',
    displayName: '2D Platformer',
    isPlatformer: true,
    movementModel: 'platformer_horizontal',
    allowsRangedCombat: false,
    allowsMeleeCombat: true,
    defaultAttackType: 'melee',
    allowsEnemyWaves: false,
    allowsDash: true,
    jumpEnabled: true,
    defaultGravity: 600,
    prohibitedSystems: ['ENEMY_WAVES', 'OPEN_WORLD_REGIONS'],
  },
  arena: {
    archetype: 'arena',
    displayName: 'Arena Survival',
    isPlatformer: false,
    movementModel: 'top_down_omnidirectional',
    allowsRangedCombat: true,
    allowsMeleeCombat: true,
    defaultAttackType: 'ranged',
    allowsEnemyWaves: true,
    allowsDash: true,
    jumpEnabled: false,
    defaultGravity: 0,
    prohibitedSystems: ['PLATFORMING_JUMP'],
  },
  survival: {
    archetype: 'survival',
    displayName: 'Survival Action',
    isPlatformer: false,
    movementModel: 'top_down_omnidirectional',
    allowsRangedCombat: true,
    allowsMeleeCombat: true,
    defaultAttackType: 'ranged',
    allowsEnemyWaves: true,
    allowsDash: true,
    jumpEnabled: false,
    defaultGravity: 0,
    prohibitedSystems: ['PLATFORMING_JUMP'],
  },
  shooter: {
    archetype: 'shooter',
    displayName: 'Top-Down Shooter',
    isPlatformer: false,
    movementModel: 'top_down_omnidirectional',
    allowsRangedCombat: true,
    allowsMeleeCombat: false,
    defaultAttackType: 'ranged',
    allowsEnemyWaves: true,
    allowsDash: true,
    jumpEnabled: false,
    defaultGravity: 0,
    prohibitedSystems: ['PLATFORMING_JUMP'],
  },
  collector: {
    archetype: 'collector',
    displayName: 'Data Collector',
    isPlatformer: false,
    movementModel: 'top_down_omnidirectional',
    allowsRangedCombat: false,
    allowsMeleeCombat: true,
    defaultAttackType: 'none',
    allowsEnemyWaves: false,
    allowsDash: true,
    jumpEnabled: false,
    defaultGravity: 0,
    prohibitedSystems: ['ENEMY_WAVES', 'PLATFORMING_JUMP'],
  },
  runner: {
    archetype: 'runner',
    displayName: 'Endless Runner',
    isPlatformer: true,
    movementModel: 'platformer_horizontal',
    allowsRangedCombat: false,
    allowsMeleeCombat: true,
    defaultAttackType: 'none',
    allowsEnemyWaves: false,
    allowsDash: true,
    jumpEnabled: true,
    defaultGravity: 600,
    prohibitedSystems: ['ENEMY_WAVES', 'OPEN_WORLD_REGIONS'],
  },
};

/**
 * Resolve the authoritative archetype policy for a given archetype string or fallback.
 */
export function resolveArchetypePolicy(archetypeRaw?: string, worldGravity?: number): ArchetypePolicy {
  const key = (archetypeRaw || '').toLowerCase().trim() as GameArchetype;
  if (key in ARCHETYPE_POLICIES) {
    const policy = ARCHETYPE_POLICIES[key];
    // If explicit world gravity > 0 on a non-platformer, honor physics gravity while keeping archetype identity
    if ((worldGravity ?? 0) > 0 && !policy.isPlatformer) {
      return {
        ...policy,
        isPlatformer: true,
        movementModel: 'platformer_horizontal',
        jumpEnabled: true,
      };
    }
    return policy;
  }

  // Fallback if unrecognized
  if ((worldGravity ?? 0) > 0) {
    return ARCHETYPE_POLICIES.platformer;
  }
  return ARCHETYPE_POLICIES.arena;
}
