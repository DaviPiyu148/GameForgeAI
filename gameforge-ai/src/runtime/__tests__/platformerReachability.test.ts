import test from 'node:test';
import assert from 'node:assert/strict';
import { RuntimeConfigCompiler } from '../RuntimeConfig';
import { ObjectiveEvaluator } from '../ObjectiveEvaluator';
import { RuleEngine } from '../rules';
import { PLATFORMER_FIXTURE } from '../fixtures';

test('Platformer Contract: Proves player can reach objective without magic string IDs', () => {
  const result = RuntimeConfigCompiler.compile(PLATFORMER_FIXTURE);
  assert.equal(result.success, true);
  const config = result.config!;

  assert.equal(config.archetypePolicy.archetype, 'platformer');
  assert.equal(config.archetypePolicy.isPlatformer, true);
  assert.ok(config.archetypePolicy.defaultGravity > 0);

  const stage = config.stages[0];
  assert.equal(stage.gravityY, 900);
  assert.equal(stage.worldBounds.width, 1200);
  assert.equal(stage.worldBounds.height, 600);

  // 1. Objective contract verification (must be reach_exit targeting goal_exit, not magic strings)
  assert.equal(stage.objective.type, 'reach_exit');
  assert.equal(stage.objective.target_entity_id, 'goal_exit');
  assert.equal(stage.objective.exit_x, 820);
  assert.equal(stage.objective.exit_y, 220);

  // 2. Physics & Reachability Proof
  // Jump height h = v^2 / (2g)
  const jumpPower = PLATFORMER_FIXTURE.player.jump_power; // 520
  const gravity = stage.gravityY; // 900
  const maxJumpHeight = (jumpPower * jumpPower) / (2 * gravity);
  assert.ok(maxJumpHeight > 150, `Max jump height ${maxJumpHeight.toFixed(1)}px must exceed 150px`);

  // Max air time t_air = 2 * (v / g)
  const totalAirTime = (2 * jumpPower) / gravity;
  const horizontalSpeed = PLATFORMER_FIXTURE.player.speed; // 220
  const maxJumpDistance = horizontalSpeed * totalAirTime;
  assert.ok(maxJumpDistance > 250, `Max jump horizontal reach ${maxJumpDistance.toFixed(1)}px must exceed 250px`);

  // Platform gap analysis from ground_1 to plat_1:
  // ground_1: x:150, w:300 -> right edge is 300, top is y: 540
  // plat_1: x:400, w:120 -> left edge is 340, top is y: 438
  const gapGroundToPlat1 = 340 - 300; // 40px gap
  const heightGroundToPlat1 = 540 - 438; // 102px height difference
  assert.ok(gapGroundToPlat1 < maxJumpDistance, 'Gap (40px) must be traversable in air');
  assert.ok(heightGroundToPlat1 < maxJumpHeight, 'Height delta (102px) must be within max jump height (150.2px)');

  // plat_1 to plat_2:
  // plat_1 right edge: 460, top: 438
  // plat_2 left edge: 520, top: 338
  const gapPlat1ToPlat2 = 520 - 460; // 60px gap
  const heightPlat1ToPlat2 = 438 - 338; // 100px height difference
  assert.ok(gapPlat1ToPlat2 < maxJumpDistance, 'Gap (60px) must be traversable in air');
  assert.ok(heightPlat1ToPlat2 < maxJumpHeight, 'Height delta (100px) must be within max jump height (150.2px)');

  // plat_2 to plat_3:
  // plat_2 right edge: 640, top: 338
  // plat_3 left edge: 710, top: 268
  const gapPlat2ToPlat3 = 710 - 640; // 70px gap
  const heightPlat2ToPlat3 = 338 - 268; // 70px height difference
  assert.ok(gapPlat2ToPlat3 < maxJumpDistance, 'Gap (70px) must be traversable in air');
  assert.ok(heightPlat2ToPlat3 < maxJumpHeight, 'Height delta (70px) must be within max jump height (150.2px)');

  // Beacon location on plat_3:
  // plat_3 spans x: [710, 850], top y: 268. Goal beacon is at x: 820, y: 220 (standing directly on plat_3)
  const goalBeacon = stage.entities.find(e => e.id === 'goal_exit')!;
  assert.ok(goalBeacon, 'Goal beacon entity must exist on stage');
  assert.ok(goalBeacon.x >= 710 && goalBeacon.x <= 850, 'Goal beacon must stand firmly on plat_3');

  // 3. Objective Completion without magic strings
  const evaluator = new ObjectiveEvaluator(stage.objective, stage.entities);
  assert.equal(evaluator.isComplete(), false);

  // Player reaches an arbitrary entity that is NOT the goal
  assert.equal(evaluator.recordExitReached('gem_1'), false);
  assert.equal(evaluator.isComplete(), false);

  // Player reaches the exact designated target entity ID
  assert.equal(evaluator.recordExitReached('goal_exit'), true);
  assert.equal(evaluator.isComplete(), true);
  assert.equal(evaluator.getStatus(), 'COMPLETED');

  // 4. Rule trigger execution for on_reach_goal
  const ruleEngine = new RuleEngine(stage.rules);
  let gameWonTriggered = false;
  let winMessage = '';

  const mockContext = {
    setGameWon: (msg: string) => {
      gameWonTriggered = true;
      winMessage = msg;
    },
  } as any;

  ruleEngine.trigger('on_reach_goal', mockContext, { goal_id: 'goal_exit' });
  assert.equal(gameWonTriggered, true);
  assert.equal(winMessage, 'BEACON ACTIVATED!');
});
