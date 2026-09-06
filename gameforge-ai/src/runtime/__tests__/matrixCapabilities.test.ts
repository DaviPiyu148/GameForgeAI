import test from 'node:test';
import assert from 'node:assert/strict';
import { RuntimeConfigCompiler, type ScaleTier } from '../RuntimeConfig';
import type { GameArchetype, GameDSL, WorldMode } from '../types';

const ARCHETYPES: GameArchetype[] = ['platformer', 'arena', 'shooter', 'collector', 'survival', 'runner'];
const WORLD_MODES: WorldMode[] = ['linear', 'campaign', 'open_world'];
const SCALE_TIERS: ScaleTier[] = ['prototype', 'standard', 'campaign'];

function createMatrixDSL(archetype: GameArchetype, worldMode: WorldMode, scale: ScaleTier): GameDSL {
  const isPlatformer = archetype === 'platformer' || archetype === 'runner';
  const baseDSL: GameDSL = {
    schema_version: '1.0',
    metadata: {
      title: `${archetype} ${worldMode} ${scale}`,
      genre: 'Test Genre',
      description: 'Automated 54-cell matrix test',
      archetype,
      scale,
    } as any,
    world: {
      width: 800,
      height: 600,
      gravity: isPlatformer ? 600 : 0,
      background_color: '#0a0b10',
      theme: 'neon',
      world_mode: worldMode,
    },
    player: {
      spawn_x: 400,
      spawn_y: 300,
      speed: 200,
      jump_power: isPlatformer ? 500 : 0,
      max_health: 100,
      width: 32,
      height: 32,
      color: '#00f0ff',
    },
    entities: [
      {
        id: 'test_ent_1',
        type: archetype === 'collector' ? 'collectible' : 'enemy',
        x: 200,
        y: 200,
        width: 24,
        height: 24,
        speed: 100,
        health: 20,
        behavior: 'patrol',
        color: '#ff0055',
        points: 10,
      },
    ],
    rules: [
      {
        id: 'r_test',
        trigger: 'on_collect',
        action: 'add_score',
        params: { amount: 10 },
      },
    ],
  };

  if (worldMode === 'campaign') {
    const levelCount = scale === 'campaign' ? 4 : (scale === 'standard' ? 3 : 2);
    baseDSL.levels = [];
    for (let i = 1; i <= levelCount; i++) {
      baseDSL.levels.push({
        level_number: i,
        title: `Level ${i}`,
        world: {
          width: 800 + i * 200,
          height: 600,
          gravity: isPlatformer ? 600 : 0,
          background_color: '#0a0b10',
          theme: 'neon',
        },
        spawn_x: 100,
        spawn_y: 300,
        entities: [
          {
            id: `lvl_${i}_ent`,
            type: 'collectible',
            x: 300,
            y: 300,
            width: 20,
            height: 20,
            speed: 0,
            health: 1,
            behavior: 'stationary',
            color: '#00ffcc',
            points: 25,
          },
        ],
        rules: [
          {
            id: `lvl_${i}_rule`,
            trigger: 'on_collect',
            action: 'add_score',
            params: { amount: 25 },
          },
        ],
        objective: {
          type: 'collect_all',
          target_count: 1,
          description: `Clear Level ${i}`,
        },
      });
    }
  } else if (worldMode === 'open_world') {
    baseDSL.open_world = {
      world_width: 2400,
      world_height: 1800,
      regions: [
        {
          id: 'reg_central',
          name: 'Central Hub',
          x: 0,
          y: 0,
          width: 1200,
          height: 900,
          danger_level: 1,
          theme: 'neon',
        },
        {
          id: 'reg_outskirts',
          name: 'Outskirts',
          x: 1200,
          y: 0,
          width: 1200,
          height: 900,
          danger_level: 3,
          theme: 'wasteland',
        },
      ],
      connections: [
        {
          from_region_id: 'reg_central',
          to_region_id: 'reg_outskirts',
          boundary_side: 'right',
          spawn_x: 1250,
          spawn_y: 450,
          traversal_type: 'seamless',
        },
      ],
      pois: [],
      activities: [],
      factions: [],
      actors: [],
      vehicles: [],
    };
  }

  return baseDSL;
}

test('54-Cell Capability Matrix: Evaluates all 6 Archetypes × 3 World Modes × 3 Scale Tiers', () => {
  let supportedCount = 0;
  let unsupportedCount = 0;
  let totalEvaluated = 0;

  for (const archetype of ARCHETYPES) {
    for (const worldMode of WORLD_MODES) {
      for (const scale of SCALE_TIERS) {
        totalEvaluated++;
        const dsl = createMatrixDSL(archetype, worldMode, scale);
        const result = RuntimeConfigCompiler.compile(dsl);

        const isPlatformer = archetype === 'platformer' || archetype === 'runner';
        const isProhibited = isPlatformer && worldMode === 'open_world';

        if (isProhibited) {
          unsupportedCount++;
          assert.equal(result.success, false, `Expected ${archetype} + ${worldMode} to be rejected.`);
          assert.ok(result.error?.includes('Incompatible game configuration'));
        } else {
          supportedCount++;
          assert.equal(result.success, true, `Expected ${archetype} + ${worldMode} + ${scale} to compile successfully. Error: ${result.error}`);
          const config = result.config!;
          assert.equal(config.archetypePolicy.archetype, archetype);
          assert.equal(config.worldMode, worldMode);
          assert.equal(config.scaleProfile.tier, scale);

          if (worldMode === 'campaign') {
            assert.ok(config.stages.length >= 2, 'Campaign should have >= 2 stages');
          } else {
            assert.equal(config.stages.length, 1, 'Linear/Open World single-stage root config');
          }
        }
      }
    }
  }

  assert.equal(totalEvaluated, 54, 'Exactly 54 cells must be evaluated');
  // Prohibited: platformer (3 scales) + runner (3 scales) in open_world = 6 unsupported cells
  assert.equal(unsupportedCount, 6, 'Exactly 6 cells should be unsupported (platformer/runner open_world)');
  assert.equal(supportedCount, 48, 'Exactly 48 cells should be supported');
});

test('Runtime Compiler: rejects malformed or invalid runtime artifacts', () => {
  // 1. Null payload
  const resNull = RuntimeConfigCompiler.compile(null as any);
  assert.equal(resNull.success, false);
  assert.ok(resNull.error?.includes('Invalid GameDSL payload'));

  // 2. Missing metadata
  const resNoMeta = RuntimeConfigCompiler.compile({ world: {}, player: {} } as any);
  assert.equal(resNoMeta.success, false);
  assert.ok(resNoMeta.error?.includes('missing required metadata'));

  // 3. Missing player
  const resNoPlayer = RuntimeConfigCompiler.compile({ metadata: { archetype: 'arena' }, world: {} } as any);
  assert.equal(resNoPlayer.success, false);
  assert.ok(resNoPlayer.error?.includes('missing required metadata, player, or world'));

  // 4. Missing archetype
  const resNoArch = RuntimeConfigCompiler.compile({
    metadata: { title: 'No Arch' },
    world: { width: 800, height: 600 },
    player: { spawn_x: 100, spawn_y: 100 },
  } as any);
  assert.equal(resNoArch.success, false);
  assert.ok(resNoArch.error?.includes('missing required metadata.archetype'));

  // 5. Unknown archetype
  const resUnknownArch = RuntimeConfigCompiler.compile({
    metadata: { archetype: 'turn_based_grand_strategy' },
    world: { width: 800, height: 600 },
    player: { spawn_x: 100, spawn_y: 100 },
  } as any);
  assert.equal(resUnknownArch.success, false);
  assert.ok(resUnknownArch.error?.includes('Unsupported archetype'));

  // 6. Unknown world mode
  const resUnknownMode = RuntimeConfigCompiler.compile({
    metadata: { archetype: 'arena' },
    world: { width: 800, height: 600, world_mode: 'infinite_procedural_multiverse' },
    player: { spawn_x: 100, spawn_y: 100 },
  } as any);
  assert.equal(resUnknownMode.success, false);
  assert.ok(resUnknownMode.error?.includes('Unsupported world mode'));

  // 7. Missing levels in campaign mode
  const resMissingLevels = RuntimeConfigCompiler.compile({
    metadata: { archetype: 'arena' },
    world: { width: 800, height: 600, world_mode: 'campaign' },
    player: { spawn_x: 100, spawn_y: 100 },
    levels: [],
  } as any);
  assert.equal(resMissingLevels.success, false);
  assert.ok(resMissingLevels.error?.includes('Malformed Campaign GameDSL'));

  // 8. Incomplete open-world config (missing regions)
  const resEmptyOW = RuntimeConfigCompiler.compile({
    metadata: { archetype: 'arena' },
    world: { width: 800, height: 600, world_mode: 'open_world' },
    player: { spawn_x: 100, spawn_y: 100 },
    open_world: { regions: [] } as any,
  } as any);
  assert.equal(resEmptyOW.success, false);
  assert.ok(resEmptyOW.error?.includes('Malformed Open World GameDSL'));

  // 9. Malformed objective type in levels
  const resBadObj = RuntimeConfigCompiler.compile({
    metadata: { archetype: 'arena' },
    world: { width: 800, height: 600, world_mode: 'campaign' },
    player: { spawn_x: 100, spawn_y: 100 },
    levels: [
      {
        level_number: 1,
        title: 'Stage 1',
        objective: { type: 'solve_crossword_puzzle' } as any,
        entities: [],
      },
    ],
  } as any);
  assert.equal(resBadObj.success, false);
  assert.ok(resBadObj.error?.includes('Malformed objective type'));

  // 10. Invalid entity (missing id)
  const resBadEntNoId = RuntimeConfigCompiler.compile({
    metadata: { archetype: 'arena' },
    world: { width: 800, height: 600 },
    player: { spawn_x: 100, spawn_y: 100 },
    entities: [{ type: 'enemy' } as any],
  } as any);
  assert.equal(resBadEntNoId.success, false);
  assert.ok(resBadEntNoId.error?.includes("missing required 'id'"));

  // 11. Invalid entity (unknown type)
  const resBadEntType = RuntimeConfigCompiler.compile({
    metadata: { archetype: 'arena' },
    world: { width: 800, height: 600 },
    player: { spawn_x: 100, spawn_y: 100 },
    entities: [{ id: 'alien', type: 'quantum_singularity' } as any],
  } as any);
  assert.equal(resBadEntType.success, false);
  assert.ok(resBadEntType.error?.includes('unknown type'));

  // 12. Invalid player attack type
  const resBadAttack = RuntimeConfigCompiler.compile({
    metadata: { archetype: 'arena' },
    world: { width: 800, height: 600 },
    player: { spawn_x: 100, spawn_y: 100, attack_type: 'laser_orbital_cannon' } as any,
  } as any);
  assert.equal(resBadAttack.success, false);
  assert.ok(resBadAttack.error?.includes('Invalid player attack type'));
});

test('Open World Archetype Verification: Arena, Shooter, Collector, Survival supported contracts', () => {
  const supportedOWArchetypes: GameArchetype[] = ['arena', 'shooter', 'collector', 'survival'];

  for (const archetype of supportedOWArchetypes) {
    const dsl = createMatrixDSL(archetype, 'open_world', 'standard');
    const result = RuntimeConfigCompiler.compile(dsl);

    assert.equal(result.success, true, `Expected open_world + ${archetype} to compile successfully.`);
    const config = result.config!;
    assert.equal(config.worldMode, 'open_world');
    assert.equal(config.archetypePolicy.archetype, archetype);
    assert.ok(config.openWorldConfig);
    assert.equal(config.openWorldConfig.openWorldDef.regions.length, 2);

    // Verify archetype capability policy in open world
    if (archetype === 'shooter') {
      assert.equal(config.archetypePolicy.allowsRangedCombat, true);
    } else if (archetype === 'arena') {
      assert.equal(config.archetypePolicy.allowsMeleeCombat, true);
    } else if (archetype === 'collector') {
      assert.equal(config.archetypePolicy.defaultAttackType, 'none');
    } else if (archetype === 'survival') {
      assert.equal(config.archetypePolicy.allowsDash, true);
    }
  }
});

test('Scale Overflow & Unsupported Features: Rejects over-budget artifacts and unsupported semantics', () => {
  // 1. Level overflow for prototype scale tier (3 levels, max allowed is 2)
  const protoDSL = createMatrixDSL('arena', 'campaign', 'prototype');
  protoDSL.levels!.push({
    level_number: 3,
    title: 'Stage 3 Overflow',
    entities: [],
    rules: [],
  });
  const resProtoLevelOverflow = RuntimeConfigCompiler.compile(protoDSL);
  assert.equal(resProtoLevelOverflow.success, false);
  assert.ok(resProtoLevelOverflow.error?.includes("Scale tier 'prototype' allows a maximum of 2 levels"));

  // 2. Wave overflow for prototype tier (4 waves, max allowed is 3)
  const waveProtoDSL = createMatrixDSL('arena', 'linear', 'prototype');
  waveProtoDSL.world.wave_count = 4;
  const resProtoWaveOverflow = RuntimeConfigCompiler.compile(waveProtoDSL);
  assert.equal(resProtoWaveOverflow.success, false);
  assert.ok(resProtoWaveOverflow.error?.includes("Scale tier 'prototype' allows a maximum of 3 waves"));

  // 3. Wave overflow for standard tier (6 waves, max allowed is 5)
  const waveStdDSL = createMatrixDSL('arena', 'linear', 'standard');
  waveStdDSL.world.wave_count = 6;
  const resStdWaveOverflow = RuntimeConfigCompiler.compile(waveStdDSL);
  assert.equal(resStdWaveOverflow.success, false);
  assert.ok(resStdWaveOverflow.error?.includes("Scale tier 'standard' allows a maximum of 5 waves"));

  // 4. Entity ceiling overflow (> 30 entities in level)
  const entOverflowDSL = createMatrixDSL('arena', 'linear', 'standard');
  const excessEntities: any[] = [];
  for (let i = 0; i < 31; i++) {
    excessEntities.push({
      id: `ent_${i}`,
      type: 'collectible',
      x: 100,
      y: 100,
      width: 20,
      height: 20,
    });
  }
  entOverflowDSL.entities = excessEntities;
  const resEntOverflow = RuntimeConfigCompiler.compile(entOverflowDSL);
  assert.equal(resEntOverflow.success, false);
  assert.ok(resEntOverflow.error?.includes('exceeds maximum entity budget (found 31, maximum allowed is 30)'));

  // 5. Rule ceiling overflow (> 15 rules)
  const ruleOverflowDSL = createMatrixDSL('arena', 'linear', 'standard');
  const excessRules: any[] = [];
  for (let i = 0; i < 16; i++) {
    excessRules.push({
      id: `rule_${i}`,
      trigger: 'on_collect',
      action: 'add_score',
      params: { amount: 10 },
    });
  }
  ruleOverflowDSL.rules = excessRules;
  const resRuleOverflow = RuntimeConfigCompiler.compile(ruleOverflowDSL);
  assert.equal(resRuleOverflow.success, false);
  assert.ok(resRuleOverflow.error?.includes('exceeds maximum rule budget (found 16, maximum allowed is 15)'));

  // 6. Open World region ceiling overflow (> 6 regions)
  const owRegionOverflowDSL = createMatrixDSL('arena', 'open_world', 'standard');
  for (let i = 3; i <= 7; i++) {
    owRegionOverflowDSL.open_world!.regions.push({
      id: `reg_${i}`,
      name: `Region ${i}`,
      x: i * 800,
      y: 0,
      width: 800,
      height: 600,
      danger_level: 1,
    });
  }
  const resRegionOverflow = RuntimeConfigCompiler.compile(owRegionOverflowDSL);
  assert.equal(resRegionOverflow.success, false);
  assert.ok(resRegionOverflow.error?.includes('allows a maximum of 6 regions, but received 7'));

  // 7. Unsupported Open World Actor Schedules (non-empty schedules array)
  const owScheduleDSL = createMatrixDSL('arena', 'open_world', 'standard');
  owScheduleDSL.open_world!.actors = [
    {
      id: 'guard_1',
      name: 'City Guard',
      archetype: 'guard',
      region_id: 'reg_central',
      x: 200,
      y: 200,
      width: 24,
      height: 24,
      health: 50,
      speed: 80,
      behavior: 'patrol',
      color: '#aaaaaa',
      schedules: [
        {
          start_hour: 8,
          end_hour: 18,
          region_id: 'reg_central',
          activity_name: 'day_patrol',
        },
      ],
    } as any,
  ];
  const resSchedule = RuntimeConfigCompiler.compile(owScheduleDSL);
  assert.equal(resSchedule.success, false);
  assert.ok(resSchedule.error?.includes('Unsupported open-world feature: Actor \'guard_1\' declares schedules'));

  // 8. Unsupported Dynamic Event Modifiers (Option B: rejected with controlled validation error)
  const owModifierDSL = createMatrixDSL('arena', 'open_world', 'standard');
  owModifierDSL.open_world!.events = [
    {
      id: 'event_storm',
      name: 'Electric Storm',
      type: 'storm',
      region_ids: ['reg_central'],
      duration_seconds: 30,
      active: true,
      threat_modifier: 1,
      danger_modifier: 1,
      player_speed_modifier: 0.5,
    } as any,
  ];
  const resModifier = RuntimeConfigCompiler.compile(owModifierDSL);
  assert.equal(resModifier.success, false);
  assert.ok(resModifier.error?.includes("Unsupported open-world feature: Event 'event_storm' declares dynamic physics/stat modifiers"));
});
