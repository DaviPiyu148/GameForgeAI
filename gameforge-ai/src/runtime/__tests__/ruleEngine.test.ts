import test from 'node:test';
import assert from 'node:assert/strict';
import { RuleEngine, type GameContext } from '../rules';
import type { RuleDef } from '../types';

test('P0-001 Regression: on_score_target -> add_score does not recurse indefinitely', () => {
  let score = 0;
  let addScoreCalls = 0;

  const context: GameContext = {
    score: 0,
    health: 100,
    maxHealth: 100,
    playerSpeed: 200,
    isWon: false,
    isLost: false,
    addScore: (pts: number) => {
      addScoreCalls++;
      const prev = score;
      score += pts;
      context.score = score;
      engine.evaluateScoreThresholds(prev, score, context);
    },
    damagePlayer: () => {},
    healPlayer: () => {},
    setGameWon: () => {},
    setGameLost: () => {},
    applySpeedBoost: () => {},
  };

  const recursiveRules: RuleDef[] = [
    {
      id: 'rule_score_target_recurse',
      trigger: 'on_score_target',
      action: 'add_score',
      params: { target_score: 50, amount: 25 },
    },
  ];

  const engine = new RuleEngine(recursiveRules);

  // Initial score is 0. Adding 40 does not cross target 50.
  context.addScore(40);
  assert.equal(score, 40);
  assert.equal(addScoreCalls, 1);

  // Adding 20 pushes score to 60 (crossing 50 threshold).
  // Rule triggers once: adding 25 (score becomes 85).
  // Because rule is single-shot on threshold, it does not recurse further.
  context.addScore(20);
  assert.equal(score, 85);
  assert.equal(addScoreCalls, 3); // initial 40 + add 20 + rule bonus 25

  // Subsequent additions do not re-fire the already-met threshold rule
  context.addScore(10);
  assert.equal(score, 95);
  assert.equal(addScoreCalls, 4);
});

test('RuleEngine Re-entrancy Guard: suppresses direct cyclic trigger chains', () => {
  let triggerCount = 0;

  const context: GameContext = {
    score: 0,
    health: 100,
    maxHealth: 100,
    playerSpeed: 200,
    isWon: false,
    isLost: false,
    addScore: () => {},
    damagePlayer: () => {
      triggerCount++;
      // Directly re-trigger same event in handler
      engine.trigger('on_collide_enemy', context);
    },
    healPlayer: () => {},
    setGameWon: () => {},
    setGameLost: () => {},
    applySpeedBoost: () => {},
  };

  const cyclicRules: RuleDef[] = [
    {
      id: 'rule_cyclic_damage',
      trigger: 'on_collide_enemy',
      action: 'damage_player',
      params: { amount: 10 },
    },
  ];

  const engine = new RuleEngine(cyclicRules);

  // Calling trigger should not throw stack overflow; should be suppressed immediately by cycle detection (triggerCount = 1)
  assert.doesNotThrow(() => {
    engine.trigger('on_collide_enemy', context);
  });

  assert.equal(triggerCount, 1);
});
