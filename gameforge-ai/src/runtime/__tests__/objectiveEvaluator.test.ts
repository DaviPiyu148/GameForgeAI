import test from 'node:test';
import assert from 'node:assert/strict';
import { ObjectiveEvaluator } from '../ObjectiveEvaluator';

test('ObjectiveEvaluator: collect_all completes at target boundary', () => {
  let completed = false;
  const evalr = new ObjectiveEvaluator(
    { type: 'collect_all', target_count: 3, description: 'Collect 3 data crystals' },
    { collectibles: 5, enemies: 2 },
    {
      onComplete: () => {
        completed = true;
      },
    }
  );

  assert.equal(evalr.isComplete(), false);
  assert.equal(evalr.recordCollection(1), false);
  assert.equal(evalr.recordCollection(1), false);
  assert.equal(evalr.isComplete(), false);

  // Reaching target 3 completes
  assert.equal(evalr.recordCollection(1), true);
  assert.equal(evalr.isComplete(), true);
  assert.equal(completed, true);

  // Subsequent collections do not re-complete or mutate terminal status
  assert.equal(evalr.recordCollection(1), false);
  assert.equal(evalr.getStatus(), 'COMPLETED');
});

test('ObjectiveEvaluator: defeat_all completes when required enemies are defeated', () => {
  let completed = false;
  const evalr = new ObjectiveEvaluator(
    { type: 'defeat_all', target_count: 2 },
    { collectibles: 0, enemies: 2 },
    {
      onComplete: () => {
        completed = true;
      },
    }
  );

  evalr.recordEnemyDefeat(1);
  assert.equal(evalr.isComplete(), false);

  evalr.recordEnemyDefeat(1);
  assert.equal(evalr.isComplete(), true);
  assert.equal(completed, true);
});

test('ObjectiveEvaluator: reach_exit by coordinates proximity', () => {
  let completed = false;
  const evalr = new ObjectiveEvaluator(
    { type: 'reach_exit', exit_x: 500, exit_y: 300, description: 'Reach extraction point' },
    undefined,
    {
      onComplete: () => {
        completed = true;
      },
    }
  );

  // Player far away at (100, 100)
  evalr.update(0.016, 100, 100);
  assert.equal(evalr.isComplete(), false);

  // Player arrives at (510, 310) (distance ~14px <= exitRadius 50px)
  evalr.update(0.016, 510, 310);
  assert.equal(evalr.isComplete(), true);
  assert.equal(completed, true);
});

test('ObjectiveEvaluator: survive_time counts down and completes upon duration expiry', () => {
  let completed = false;
  const evalr = new ObjectiveEvaluator(
    { type: 'survive_time', time_limit_seconds: 10 },
    undefined,
    {
      onComplete: () => {
        completed = true;
      },
    }
  );

  evalr.update(4.0);
  assert.equal(evalr.isComplete(), false);
  assert.equal(evalr.getProgress().timeRemaining, 6);

  evalr.update(6.0);
  assert.equal(evalr.isComplete(), true);
  assert.equal(completed, true);
});

test('ObjectiveEvaluator: score_target completes when score crosses threshold', () => {
  let completed = false;
  const evalr = new ObjectiveEvaluator(
    { type: 'score_target', target_score: 250 },
    undefined,
    {
      onComplete: () => {
        completed = true;
      },
    }
  );

  evalr.recordScore(100);
  assert.equal(evalr.isComplete(), false);

  evalr.recordScore(250);
  assert.equal(evalr.isComplete(), true);
  assert.equal(completed, true);
});
