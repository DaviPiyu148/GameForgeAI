import test from 'node:test';
import assert from 'node:assert/strict';
import { RuntimeConfigCompiler } from '../RuntimeConfig';
import type { GameDSL } from '../types';

test('P1-004 Regression: Multi-level campaign compiles independent stage rules, gravity, bounds, and objectives', () => {
  const campaignDsl: GameDSL = {
    schema_version: '3.0',
    metadata: {
      title: 'Neon Odyssey',
      genre: 'Action',
      description: '2-stage campaign',
      archetype: 'arena',
    },
    world: {
      width: 800,
      height: 600,
      gravity: 0,
      background_color: '#000000',
      theme: 'neon',
      world_mode: 'campaign',
    },
    player: {
      name: 'Hero',
      spawn_x: 100,
      spawn_y: 100,
      speed: 200,
      jump_power: 0,
      max_health: 100,
      width: 32,
      height: 32,
      color: '#00ffff',
    },
    entities: [],
    rules: [
      {
        id: 'global_rule_1',
        trigger: 'on_collect',
        action: 'add_score',
        params: { amount: 10 },
      },
    ],
    ui: {
      show_health: true,
      show_score: true,
      status_text: 'INITIALIZING',
    },
    levels: [
      {
        level_number: 1,
        title: 'The Ingress Gate',
        theme: 'cyberpunk',
        world: {
          width: 1000,
          height: 800,
          gravity: 0,
          background_color: '#0a0a1a',
          theme: 'cyberpunk',
          world_mode: 'campaign',
        },
        spawn_x: 50,
        spawn_y: 50,
        objective: {
          type: 'collect_all',
          target_count: 5,
          description: 'Collect 5 data chips',
        },
        entities: [
          {
            id: 'chip_1',
            type: 'collectible',
            x: 200,
            y: 200,
            width: 16,
            height: 16,
            speed: 0,
            health: 1,
            behavior: 'stationary',
            color: '#00ffcc',
            points: 20,
          },
        ],
        rules: [
          {
            id: 'lvl1_local_rule',
            trigger: 'on_collect',
            action: 'add_score',
            params: { amount: 100 },
          },
        ],
      },
      {
        level_number: 2,
        title: 'Gravity Core',
        theme: 'space',
        world: {
          width: 1600,
          height: 1200,
          gravity: 500,
          background_color: '#1a0033',
          theme: 'space',
          world_mode: 'campaign',
        },
        spawn_x: 200,
        spawn_y: 400,
        objective: {
          type: 'defeat_all',
          target_count: 3,
          description: 'Eliminate Core Drones',
        },
        entities: [
          {
            id: 'drone_1',
            type: 'enemy',
            x: 500,
            y: 500,
            width: 24,
            height: 24,
            speed: 120,
            health: 50,
            behavior: 'chase',
            color: '#ff0055',
            points: 50,
          },
        ],
        rules: [
          {
            id: 'lvl2_local_rule',
            trigger: 'on_enemy_defeat',
            action: 'heal_player',
            params: { amount: 30 },
          },
        ],
        is_finale: true,
      },
    ],
  };

  const res = RuntimeConfigCompiler.compile(campaignDsl);
  assert.equal(res.success, true);
  if (!res.config) {
    assert.fail('res.config must not be undefined');
  }

  const stages = res.config.stages;
  assert.equal(stages.length, 2);

  // Stage 1 Assertions
  const s1 = stages[0];
  assert.equal(s1.title, 'The Ingress Gate');
  assert.equal(s1.worldBounds.width, 1000);
  assert.equal(s1.worldBounds.height, 800);
  assert.equal(s1.gravityY, 0);
  assert.equal(s1.playerSpawn.x, 50);
  assert.equal(s1.playerSpawn.y, 50);
  assert.equal(s1.objective.type, 'collect_all');
  assert.equal(s1.rules.length, 1);
  assert.equal(s1.rules[0].id, 'lvl1_local_rule');
  assert.equal(s1.rules[0].params.amount, 100);

  // Stage 2 Assertions (Conflicting values cleanly resolved)
  const s2 = stages[1];
  assert.equal(s2.title, 'Gravity Core');
  assert.equal(s2.worldBounds.width, 1600);
  assert.equal(s2.worldBounds.height, 1200);
  assert.equal(s2.gravityY, 500);
  assert.equal(s2.playerSpawn.x, 200);
  assert.equal(s2.playerSpawn.y, 400);
  assert.equal(s2.objective.type, 'defeat_all');
  assert.equal(s2.rules.length, 1);
  assert.equal(s2.rules[0].id, 'lvl2_local_rule');
  assert.equal(s2.rules[0].params.amount, 30);
  assert.equal(s2.isFinale, true);
});

test('RuntimeConfigCompiler: Rejects platformer + open world incompatibility safely', () => {
  const invalidDsl: any = {
    schema_version: '3.0',
    metadata: {
      title: 'Platformer Open World',
      archetype: 'platformer',
    },
    world: {
      width: 800,
      height: 600,
      gravity: 600,
      world_mode: 'open_world',
    },
    player: {
      spawn_x: 100,
      spawn_y: 100,
    },
    open_world: {
      regions: [{ id: 'reg_1', name: 'Zone 1', width: 800, height: 600 }],
    },
  };

  const res = RuntimeConfigCompiler.compile(invalidDsl);
  assert.equal(res.success, false);
  assert.ok(res.error?.includes('Incompatible game configuration'));
});
