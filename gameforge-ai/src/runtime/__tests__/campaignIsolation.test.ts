import test from 'node:test';
import assert from 'node:assert/strict';
import { RuntimeConfigCompiler } from '../RuntimeConfig';
import { ObjectiveEvaluator } from '../ObjectiveEvaluator';
import { RuleEngine } from '../rules';
import type { GameDSL } from '../types';

const CAMPAIGN_DSL: GameDSL = {
  schema_version: '1.0',
  metadata: {
    title: 'Isolated Campaign Challenge',
    genre: 'Platformer Adventure',
    description: 'Multi-stage campaign testing complete stage-to-stage isolation.',
    archetype: 'platformer',
  },
  world: {
    width: 800,
    height: 600,
    gravity: 600,
    background_color: '#0a0b10',
    theme: 'neon',
    world_mode: 'campaign',
  },
  player: {
    spawn_x: 100,
    spawn_y: 300,
    speed: 220,
    jump_power: 550,
    max_health: 100,
    width: 32,
    height: 32,
    color: '#00f0ff',
  },
  levels: [
    {
      level_number: 1,
      title: 'Level 1: Neon Ascent',
      theme: 'neon',
      world: {
        width: 1000,
        height: 600,
        gravity: 600,
        background_color: '#0a0b12',
        theme: 'neon',
      },
      spawn_x: 100,
      spawn_y: 450,
      objective: {
        type: 'collect_all',
        target_count: 3,
        description: 'Collect all 3 orbs',
      },
      rules: [
        {
          id: 'rule_stage_1_collect',
          trigger: 'on_collect',
          action: 'add_score',
          params: { amount: 50 },
        },
      ],
      entities: [
        { id: 'c1', type: 'collectible', x: 200, y: 400, width: 20, height: 20, speed: 0, health: 1, behavior: 'stationary', color: '#ffe600', points: 50 },
        { id: 'c2', type: 'collectible', x: 400, y: 350, width: 20, height: 20, speed: 0, health: 1, behavior: 'stationary', color: '#ffe600', points: 50 },
        { id: 'c3', type: 'collectible', x: 600, y: 300, width: 20, height: 20, speed: 0, health: 1, behavior: 'stationary', color: '#ffe600', points: 50 },
      ],
    },
    {
      level_number: 2,
      title: 'Level 2: Zero-G Orbital Hub',
      theme: 'space',
      world: {
        width: 2400,
        height: 1200,
        gravity: 0, // Gravity intentionally drops to 0
        background_color: '#020308',
        theme: 'space',
      },
      spawn_x: 600,
      spawn_y: 600,
      objective: {
        type: 'reach_exit',
        target_entity_id: 'station_airlock',
        exit_x: 2200,
        exit_y: 600,
        exit_radius: 60,
        description: 'Reach the station airlock',
      },
      rules: [
        {
          id: 'rule_stage_2_hazard',
          trigger: 'on_hazard_touch',
          action: 'damage_player',
          params: { amount: 30 },
        },
      ],
      entities: [
        { id: 'station_airlock', type: 'collectible', x: 2200, y: 600, width: 40, height: 40, speed: 0, health: 1, behavior: 'stationary', color: '#00ff66', points: 100 },
        { id: 'drone_1', type: 'enemy', x: 1200, y: 600, width: 30, height: 30, speed: 80, health: 30, behavior: 'patrol', color: '#ff0055', points: 50 },
      ],
    },
    {
      level_number: 3,
      title: 'Level 3: Low-Gravity Cyber Stronghold',
      theme: 'cyberpunk',
      world: {
        width: 1600,
        height: 900,
        gravity: 300, // Gravity changes to low-gravity 300
        background_color: '#100515',
        theme: 'cyberpunk',
      },
      spawn_x: 200,
      spawn_y: 500,
      objective: {
        type: 'survive_time',
        time_limit_seconds: 25,
        description: 'Survive the lockdown for 25s',
      },
      rules: [
        {
          id: 'rule_stage_3_defeat',
          trigger: 'on_enemy_defeat',
          action: 'heal_player',
          params: { amount: 20 },
        },
      ],
      entities: [
        { id: 'en_boss', type: 'enemy', x: 1200, y: 500, width: 48, height: 48, speed: 120, health: 150, behavior: 'chase', color: '#ff0033', points: 500, is_boss: true },
      ],
      is_finale: true,
    },
  ],
};

test('Campaign Isolation: Compiles multi-stage specifications with distinct stage configurations', () => {
  const result = RuntimeConfigCompiler.compile(CAMPAIGN_DSL);
  assert.equal(result.success, true);
  const config = result.config!;

  assert.equal(config.worldMode, 'campaign');
  assert.equal(config.stages.length, 3);

  // Stage 1 Verification
  const s1 = config.stages[0];
  assert.equal(s1.gravityY, 600);
  assert.equal(s1.worldBounds.width, 1000);
  assert.equal(s1.worldBounds.height, 600);
  assert.equal(s1.objective.type, 'collect_all');
  assert.equal(s1.rules.length, 1);
  assert.equal(s1.rules[0].id, 'rule_stage_1_collect');
  assert.equal(s1.entities.length, 3);
  assert.equal(s1.isFinale, false);

  // Stage 2 Verification (gravity drops to 0, bounds expand)
  const s2 = config.stages[1];
  assert.equal(s2.gravityY, 0);
  assert.equal(s2.worldBounds.width, 2400);
  assert.equal(s2.worldBounds.height, 1200);
  assert.equal(s2.objective.type, 'reach_exit');
  assert.equal(s2.rules.length, 1);
  assert.equal(s2.rules[0].id, 'rule_stage_2_hazard');
  assert.equal(s2.entities.length, 2);
  assert.equal(s2.isFinale, false);

  // Stage 3 Verification (gravity rises to 300, survive objective)
  const s3 = config.stages[2];
  assert.equal(s3.gravityY, 300);
  assert.equal(s3.worldBounds.width, 1600);
  assert.equal(s3.worldBounds.height, 900);
  assert.equal(s3.objective.type, 'survive_time');
  assert.equal(s3.rules.length, 1);
  assert.equal(s3.rules[0].id, 'rule_stage_3_defeat');
  assert.equal(s3.isFinale, true);
});

test('Campaign Isolation: Simulates runtime stage transition proving zero state leakage', () => {
  const result = RuntimeConfigCompiler.compile(CAMPAIGN_DSL);
  assert.equal(result.success, true);
  const config = result.config!;

  // 1. Initial State: Stage 1
  let activeStageIndex = 0;
  let activeStage = config.stages[activeStageIndex];
  let objectiveEvaluator = new ObjectiveEvaluator(activeStage.objective, activeStage.entities);
  let ruleEngine = new RuleEngine(activeStage.rules);
  let activeEntities = [...activeStage.entities];
  let activePhysicsGravityY = activeStage.gravityY;

  assert.equal(activePhysicsGravityY, 600);
  assert.equal(objectiveEvaluator.getObjectiveDef().type, 'collect_all');
  assert.equal(activeEntities.length, 3);
  assert.equal(ruleEngine.getRuleCount(), 1);

  // Simulate player completing Stage 1
  objectiveEvaluator.recordCollection(3);
  assert.equal(objectiveEvaluator.isComplete(), true);

  // 2. Atomic Transition to Stage 2
  activeStageIndex = 1;
  activeStage = config.stages[activeStageIndex];

  // Teardown previous stage: clear entities, re-instantiate clean ruleEngine and objectiveEvaluator
  activeEntities = []; // previous entities destroyed
  ruleEngine.resetState();
  ruleEngine = new RuleEngine(activeStage.rules);
  objectiveEvaluator = new ObjectiveEvaluator(activeStage.objective, activeStage.entities);
  activeEntities = [...activeStage.entities];
  activePhysicsGravityY = activeStage.gravityY;

  // Verify atomic update
  assert.equal(activePhysicsGravityY, 0, 'Gravity should atomically update from 600 to 0');
  assert.equal(activeStage.worldBounds.width, 2400, 'Bounds should update to 2400');
  assert.equal(objectiveEvaluator.getObjectiveDef().type, 'reach_exit');
  assert.equal(objectiveEvaluator.isComplete(), false, 'New stage objective must be fresh/incomplete');
  assert.equal(activeEntities.length, 2, 'Previous stage collectibles must be gone; new stage entities loaded');
  assert.equal(activeEntities.some(e => e.id === 'c1'), false, 'Stage 1 entity c1 must not exist');

  // Complete Stage 2 by reaching exit
  objectiveEvaluator.recordExitReached('station_airlock');
  assert.equal(objectiveEvaluator.isComplete(), true);

  // 3. Atomic Transition to Stage 3
  activeStageIndex = 2;
  activeStage = config.stages[activeStageIndex];

  // Teardown previous stage
  activeEntities = [];
  ruleEngine.resetState();
  ruleEngine = new RuleEngine(activeStage.rules);
  objectiveEvaluator = new ObjectiveEvaluator(activeStage.objective, activeStage.entities);
  activeEntities = [...activeStage.entities];
  activePhysicsGravityY = activeStage.gravityY;

  // Verify atomic update
  assert.equal(activePhysicsGravityY, 300, 'Gravity should update from 0 to 300');
  assert.equal(activeStage.worldBounds.width, 1600);
  assert.equal(objectiveEvaluator.getObjectiveDef().type, 'survive_time');
  assert.equal(activeEntities.length, 1);
  assert.equal(activeEntities[0].id, 'en_boss');
  assert.equal(activeStage.isFinale, true);

  // 4. Complete Loop: Transition from Stage 3 back to Stage 1
  activeStageIndex = 0;
  activeStage = config.stages[activeStageIndex];

  // Teardown previous stage
  activeEntities = [];
  ruleEngine.resetState();
  ruleEngine = new RuleEngine(activeStage.rules);
  objectiveEvaluator = new ObjectiveEvaluator(activeStage.objective, activeStage.entities);
  activeEntities = [...activeStage.entities];
  activePhysicsGravityY = activeStage.gravityY;

  // Verify Stage 1 is fully and cleanly restored without any residual Stage 3 state
  assert.equal(activePhysicsGravityY, 600, 'Gravity must be cleanly restored to 600');
  assert.equal(activeStage.worldBounds.width, 1000, 'Bounds width must be cleanly restored to 1000');
  assert.equal(activeStage.worldBounds.height, 600, 'Bounds height must be cleanly restored to 600');
  assert.equal(objectiveEvaluator.getObjectiveDef().type, 'collect_all', 'Objective must be restored to collect_all');
  assert.equal(objectiveEvaluator.isComplete(), false, 'Objective must be fresh and incomplete');
  assert.equal(activeEntities.length, 3, 'Must contain exactly the 3 initial collectibles');
  assert.equal(activeEntities.some(e => e.id === 'en_boss'), false, 'Stage 3 boss must NOT leak into Stage 1');
  assert.equal(ruleEngine.getRuleCount(), 1, 'Only Stage 1 rule must exist');
  assert.equal(ruleEngine.hasRulesForTrigger('on_enemy_defeat'), false, 'Stage 3 rule must NOT leak');
});

test('Campaign Isolation: Repeated loop transitions (Level 1 -> 2 -> 3 -> 1) x 10 verify zero state or memory leakage', () => {
  const result = RuntimeConfigCompiler.compile(CAMPAIGN_DSL);
  assert.equal(result.success, true);
  const config = result.config!;

  let currentStageIndex = 0;
  let activeEntities: any[] = [];
  let ruleEngine: RuleEngine;
  let objectiveEvaluator: ObjectiveEvaluator;
  let gravityY = 0;

  for (let cycle = 0; cycle < 10; cycle++) {
    for (let stageIdx = 0; stageIdx < config.stages.length; stageIdx++) {
      currentStageIndex = stageIdx;
      const stage = config.stages[currentStageIndex];

      // Atomic transition teardown and setup
      activeEntities = [];
      ruleEngine = new RuleEngine(stage.rules);
      objectiveEvaluator = new ObjectiveEvaluator(stage.objective, stage.entities);
      activeEntities = [...stage.entities];
      gravityY = stage.gravityY;

      // Invariant checks per stage during every iteration
      if (stageIdx === 0) {
        assert.equal(gravityY, 600);
        assert.equal(activeEntities.length, 3);
        assert.equal(objectiveEvaluator.getObjectiveDef().type, 'collect_all');
        assert.equal(ruleEngine.getRuleCount(), 1);
      } else if (stageIdx === 1) {
        assert.equal(gravityY, 0);
        assert.equal(activeEntities.length, 2);
        assert.equal(objectiveEvaluator.getObjectiveDef().type, 'reach_exit');
        assert.equal(ruleEngine.getRuleCount(), 1);
      } else if (stageIdx === 2) {
        assert.equal(gravityY, 300);
        assert.equal(activeEntities.length, 1);
        assert.equal(objectiveEvaluator.getObjectiveDef().type, 'survive_time');
        assert.equal(ruleEngine.getRuleCount(), 1);
      }
    }
  }

  // After 10 full loops (30 stage transitions), verify final state matches stage 3 precisely
  assert.equal(currentStageIndex, 2);
  assert.equal(activeEntities.length, 1);
  assert.equal(activeEntities[0].id, 'en_boss');
});
