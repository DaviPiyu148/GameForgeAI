import test from 'node:test';
import assert from 'node:assert/strict';
import { RuleEngine, type GameContext } from '../rules';
import type { RuleDef } from '../types';

function createMockContext(initialScore = 0, initialHealth = 100): { context: GameContext; log: string[] } {
  const log: string[] = [];
  const state = {
    score: initialScore,
    health: initialHealth,
    maxHealth: 100,
    playerSpeed: 200,
    isWon: false,
    isLost: false,
  };

  const context: GameContext = {
    get score() { return state.score; },
    get health() { return state.health; },
    get maxHealth() { return state.maxHealth; },
    get playerSpeed() { return state.playerSpeed; },
    get isWon() { return state.isWon; },
    get isLost() { return state.isLost; },
    addScore: (pts: number) => {
      state.score += pts;
      log.push(`addScore(${pts}) -> ${state.score}`);
    },
    damagePlayer: (dmg: number) => {
      state.health = Math.max(0, state.health - dmg);
      log.push(`damagePlayer(${dmg}) -> ${state.health}`);
    },
    healPlayer: (amount: number) => {
      state.health = Math.min(state.maxHealth, state.health + amount);
      log.push(`healPlayer(${amount}) -> ${state.health}`);
    },
    setGameWon: (reason: string) => {
      state.isWon = true;
      log.push(`setGameWon(${reason})`);
    },
    setGameLost: (reason: string) => {
      state.isLost = true;
      log.push(`setGameLost(${reason})`);
    },
    applySpeedBoost: (durationMs: number, multiplier: number) => {
      log.push(`applySpeedBoost(${durationMs}, ${multiplier})`);
    },
    spawnBonusEntity: () => {
      log.push('spawnBonusEntity()');
    },
    triggerScreenShake: (intensity?: number) => {
      log.push(`triggerScreenShake(${intensity})`);
    },
    spawnWave: (wave?: number) => {
      log.push(`spawnWave(${wave})`);
    },
    grantPowerup: (ptype: string) => {
      log.push(`grantPowerup(${ptype})`);
    },
    spawnParticles: (colorHex?: string, count?: number) => {
      log.push(`spawnParticles(${colorHex}, ${count})`);
    },
  };

  return { context, log };
}

test('RuleEngine: executes multiple independent rules on the same trigger', () => {
  const rules: RuleDef[] = [
    {
      id: 'rule_collect_score',
      trigger: 'on_collect',
      action: 'add_score',
      params: { amount: 50 },
    },
    {
      id: 'rule_collect_heal',
      trigger: 'on_collect',
      action: 'heal_player',
      params: { amount: 20 },
    },
    {
      id: 'rule_collect_boost',
      trigger: 'on_collect',
      action: 'speed_boost',
      params: { duration: 2000, multiplier: 1.5 },
    },
  ];

  const engine = new RuleEngine(rules);
  const { context, log } = createMockContext(0, 50);

  engine.trigger('on_collect', context);

  assert.equal(context.score, 50);
  assert.equal(context.health, 70);
  assert.ok(log.includes('addScore(50) -> 50'));
  assert.ok(log.includes('healPlayer(20) -> 70'));
  assert.ok(log.includes('applySpeedBoost(2000, 1.5)'));
  assert.equal(engine.getActiveStackDepth(), 0);
});

test('RuleEngine: supports legitimate causal rule chains (A -> B -> C -> D)', () => {
  const rules: RuleDef[] = [
    {
      id: 'r1_collect',
      trigger: 'on_collect',
      action: 'add_score',
      params: { amount: 100 },
    },
    {
      id: 'r2_score_target',
      trigger: 'on_score_target',
      action: 'damage_player',
      params: { amount: 100, target_score: 100 },
    },
    {
      id: 'r3_death',
      trigger: 'on_player_death',
      action: 'lose_game',
      params: { message: 'FELL IN BATTLE' },
    },
  ];

  const engine = new RuleEngine(rules);
  const { context, log } = createMockContext(0, 100);

  const originalAddScore = context.addScore;
  context.addScore = (pts: number) => {
    const prev = context.score;
    originalAddScore(pts);
    engine.evaluateScoreThresholds(prev, context.score, context);
  };

  const originalDamage = context.damagePlayer;
  context.damagePlayer = (dmg: number) => {
    originalDamage(dmg);
    if (context.health <= 0) {
      engine.trigger('on_player_death', context);
    }
  };

  engine.trigger('on_collect', context);

  assert.equal(context.score, 100);
  assert.equal(context.health, 0);
  assert.equal(context.isLost, true);
  assert.ok(log.includes('setGameLost(FELL IN BATTLE)'));
  assert.equal(engine.getActiveStackDepth(), 0);
});

test('RuleEngine: detects and terminates direct synchronous cycle (A -> A) safely', () => {
  const rules: RuleDef[] = [
    {
      id: 'r_loop',
      trigger: 'on_score_target',
      action: 'add_score',
      params: { amount: 50, target_score: 50, repeating: true },
    },
  ];

  const engine = new RuleEngine(rules);
  const { context, log } = createMockContext(0, 100);

  context.addScore = (pts: number) => {
    const prev = context.score;
    (context as any)._score = ((context as any)._score || 0) + pts;
    log.push(`addScore(${pts})`);
    engine.evaluateScoreThresholds(prev, (context as any)._score, context);
  };
  Object.defineProperty(context, 'score', {
    get() { return (context as any)._score || 0; },
  });

  engine.evaluateScoreThresholds(0, 50, context);

  assert.ok(log.filter(l => l.includes('addScore(50)')).length === 1);
  assert.equal(engine.getActiveStackDepth(), 0);
});

test('RuleEngine: detects and terminates indirect synchronous cycle (A -> B -> A)', () => {
  const rules: RuleDef[] = [
    {
      id: 'rule_A',
      trigger: 'on_collect',
      action: 'damage_player',
      params: { amount: 20 },
    },
    {
      id: 'rule_B',
      trigger: 'on_collide_enemy',
      action: 'spawn_entity',
      params: {},
    },
  ];

  const engine = new RuleEngine(rules);
  const { context, log } = createMockContext(0, 100);

  context.damagePlayer = (dmg: number) => {
    log.push(`damagePlayer(${dmg})`);
    engine.trigger('on_collide_enemy', context);
  };

  context.spawnBonusEntity = () => {
    log.push('spawnBonusEntity -> triggering on_collect');
    engine.trigger('on_collect', context);
  };

  engine.trigger('on_collect', context);

  assert.ok(log.includes('damagePlayer(20)'));
  assert.ok(log.includes('spawnBonusEntity -> triggering on_collect'));
  assert.equal(engine.getActiveStackDepth(), 0);
});

test('RuleEngine: detects static cycles with validateRuleGraph', () => {
  const cyclicRules: RuleDef[] = [
    {
      id: 'r_score',
      trigger: 'on_score_target',
      action: 'add_score',
      params: { amount: 50, target_score: 100 },
    },
  ];

  const result = RuleEngine.validateRuleGraph(cyclicRules);
  assert.equal(result.hasCycles, true);
  assert.ok(result.cycles.length > 0);
  assert.ok(result.warnings.some(w => w.includes('Cyclic rule dependency detected')));
});

test('RuleEngine: supports legitimate repeated threshold crossings when score re-crosses target', () => {
  const rules: RuleDef[] = [
    {
      id: 'r_repeat',
      trigger: 'on_score_target',
      action: 'heal_player',
      params: { amount: 25, target_score: 100, repeating: true },
    },
  ];

  const engine = new RuleEngine(rules);
  const { context, log } = createMockContext(0, 50);

  engine.evaluateScoreThresholds(90, 110, context);
  assert.equal(log.length, 1);
  assert.equal(context.health, 75);

  engine.evaluateScoreThresholds(110, 120, context);
  assert.equal(log.length, 1);

  engine.evaluateScoreThresholds(120, 80, context);
  assert.equal(log.length, 1);

  engine.evaluateScoreThresholds(80, 105, context);
  assert.equal(log.length, 2);
  assert.equal(context.health, 100);
});

test('RuleEngine: detects and terminates indirect 3-node cycle (A -> B -> C -> A)', () => {
  const rules: RuleDef[] = [
    {
      id: 'rule_node_A',
      trigger: 'on_collect',
      action: 'damage_player',
      params: { amount: 10 },
    },
    {
      id: 'rule_node_B',
      trigger: 'on_collide_enemy',
      action: 'speed_boost',
      params: { duration: 1000, multiplier: 1.5 },
    },
    {
      id: 'rule_node_C',
      trigger: 'on_dash',
      action: 'spawn_entity',
      params: {},
    },
  ];

  const engine = new RuleEngine(rules);
  const { context, log } = createMockContext(0, 100);

  // Setup causal wiring: A -> B -> C -> A
  context.damagePlayer = (dmg: number) => {
    log.push(`damagePlayer(${dmg}) -> triggering on_collide_enemy`);
    engine.trigger('on_collide_enemy', context);
  };

  context.applySpeedBoost = (duration: number, mult: number) => {
    log.push(`applySpeedBoost(${duration}, ${mult}) -> triggering on_dash`);
    engine.trigger('on_dash', context);
  };

  context.spawnBonusEntity = () => {
    log.push('spawnBonusEntity -> triggering on_collect (cycle loop back to A)');
    engine.trigger('on_collect', context);
  };

  // Kick off trigger on A
  engine.trigger('on_collect', context);

  // Verify full sequence executed once and cleanly broke on re-entry of A
  assert.ok(log.includes('damagePlayer(10) -> triggering on_collide_enemy'));
  assert.ok(log.includes('applySpeedBoost(1000, 1.5) -> triggering on_dash'));
  assert.ok(log.includes('spawnBonusEntity -> triggering on_collect (cycle loop back to A)'));
  assert.equal(engine.getActiveStackDepth(), 0);
});
