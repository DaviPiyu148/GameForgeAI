import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveArchetypePolicy } from '../ArchetypePolicy';

test('ArchetypePolicy: Platformer configuration and prohibitions', () => {
  const policy = resolveArchetypePolicy('platformer');
  assert.equal(policy.archetype, 'platformer');
  assert.equal(policy.isPlatformer, true);
  assert.equal(policy.jumpEnabled, true);
  assert.equal(policy.allowsRangedCombat, false);
  assert.equal(policy.allowsMeleeCombat, true);
  assert.equal(policy.allowsEnemyWaves, false);
  assert.ok(policy.prohibitedSystems.includes('ENEMY_WAVES'));
});

test('ArchetypePolicy: Data Collector configuration and prohibitions', () => {
  const policy = resolveArchetypePolicy('collector');
  assert.equal(policy.archetype, 'collector');
  assert.equal(policy.isPlatformer, false);
  assert.equal(policy.allowsRangedCombat, false);
  assert.equal(policy.allowsEnemyWaves, false);
  assert.equal(policy.defaultAttackType, 'none');
  assert.ok(policy.prohibitedSystems.includes('ENEMY_WAVES'));
  assert.ok(policy.prohibitedSystems.includes('PLATFORMING_JUMP'));
});

test('ArchetypePolicy: Top-Down Shooter configuration', () => {
  const policy = resolveArchetypePolicy('shooter');
  assert.equal(policy.archetype, 'shooter');
  assert.equal(policy.allowsRangedCombat, true);
  assert.equal(policy.allowsEnemyWaves, true);
  assert.equal(policy.defaultAttackType, 'ranged');
});

test('ArchetypePolicy: Arena Survival configuration', () => {
  const policy = resolveArchetypePolicy('arena');
  assert.equal(policy.archetype, 'arena');
  assert.equal(policy.allowsRangedCombat, true);
  assert.equal(policy.allowsEnemyWaves, true);
  assert.equal(policy.allowsDash, true);
});

test('ArchetypePolicy: Survival Action configuration', () => {
  const policy = resolveArchetypePolicy('survival');
  assert.equal(policy.archetype, 'survival');
  assert.equal(policy.allowsRangedCombat, true);
  assert.equal(policy.allowsEnemyWaves, true);
  assert.equal(policy.allowsDash, true);
  assert.equal(policy.isPlatformer, false);
});

test('ArchetypePolicy: Endless Runner configuration and prohibitions', () => {
  const policy = resolveArchetypePolicy('runner');
  assert.equal(policy.archetype, 'runner');
  assert.equal(policy.isPlatformer, true);
  assert.equal(policy.jumpEnabled, true);
  assert.equal(policy.allowsEnemyWaves, false);
  assert.equal(policy.defaultAttackType, 'none');
  assert.ok(policy.prohibitedSystems.includes('ENEMY_WAVES'));
  assert.ok(policy.prohibitedSystems.includes('OPEN_WORLD_REGIONS'));
});
