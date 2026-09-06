import test from 'node:test';
import assert from 'node:assert/strict';
import { RuntimeStateMachine } from '../RuntimeStateMachine';
import { ObjectiveEvaluator } from '../ObjectiveEvaluator';
import { WaveController } from '../WaveController';

test('Terminal Safety: RuntimeStateMachine transitions and locks terminal states', () => {
  const machine = new RuntimeStateMachine('ACTIVE');
  assert.equal(machine.getState(), 'ACTIVE');
  assert.equal(machine.canMutateGameplay(), true);
  assert.equal(machine.isTerminal(), false);

  // Transition to WON
  const won = machine.transitionTo('WON', 'ALL OBJECTIVES COMPLETE');
  assert.equal(won, true);
  assert.equal(machine.getState(), 'WON');
  assert.equal(machine.canMutateGameplay(), false);
  assert.equal(machine.isTerminal(), true);
  assert.equal(machine.getEndReason(), 'ALL OBJECTIVES COMPLETE');

  // Attempting to transition back to ACTIVE or PAUSED from terminal state MUST be blocked
  assert.equal(machine.transitionTo('ACTIVE'), false);
  assert.equal(machine.transitionTo('PAUSED'), false);
  assert.equal(machine.beginTransition('ILLEGAL_ATTEMPT'), false);
  assert.equal(machine.getState(), 'WON');
  assert.equal(machine.canMutateGameplay(), false);

  // Scene destruction is the only legal exit from terminal
  assert.equal(machine.transitionTo('DESTROYED'), true);
  assert.equal(machine.getState(), 'DESTROYED');
  assert.equal(machine.canMutateGameplay(), false);
  assert.equal(machine.isTerminal(), true);
});

test('Terminal Safety: ObjectiveEvaluator ignores all post-terminal mutations', () => {
  const evaluator = new ObjectiveEvaluator({
    type: 'collect_all',
    target_count: 5,
    description: 'Collect all orbs',
  });

  assert.equal(evaluator.getStatus(), 'IN_PROGRESS');
  assert.equal(evaluator.recordCollection(2), false);
  assert.equal(evaluator.getProgress().current, 2);

  // Complete objective -> reaches COMPLETED terminal status
  assert.equal(evaluator.recordCollection(3), true);
  assert.equal(evaluator.getStatus(), 'COMPLETED');
  assert.equal(evaluator.isComplete(), true);
  assert.equal(evaluator.getProgress().current, 5);

  // Post-terminal mutations must be completely ignored
  assert.equal(evaluator.recordCollection(5), false);
  assert.equal(evaluator.getProgress().current, 5);

  evaluator.recordScore(999);
  assert.equal(evaluator.recordEnemyDefeat(10), false);
  assert.equal(evaluator.recordExitReached(), false);
  assert.equal(evaluator.getStatus(), 'COMPLETED');
});

test('Terminal Safety: WaveController blocks all spawning and progression in terminal state', () => {
  let waveStarts = 0;
  let waveSpawns = 0;

  const controller = new WaveController(5, {
    onWaveStartNotification: () => { waveStarts++; },
    onWaveSpawnEnemies: () => { waveSpawns++; },
  });

  controller.startInitialWave();
  assert.equal(controller.getCurrentWave(), 1);
  assert.equal(waveStarts, 1);
  assert.equal(waveSpawns, 1);

  // Player dies or stage ends -> set terminal
  controller.setTerminal(true);

  // Requests to advance wave or notify clears are rejected
  assert.equal(controller.requestNextWave(), false);
  assert.equal(controller.getCurrentWave(), 1);
  assert.equal(waveStarts, 1);
  assert.equal(waveSpawns, 1);

  const clear = controller.onWaveEnemiesCleared();
  assert.equal(clear.shouldAdvance, false);
  assert.equal(clear.isVictory, false);
});

test('Terminal Safety: Context mutation simulation verifies zero leakage post-game-over', () => {
  const machine = new RuntimeStateMachine('ACTIVE');

  let score = 100;
  let health = 100;
  let bonusSpawned = 0;
  let powerupGranted = 0;

  // Guarded game context callbacks simulating GameScene's getGameContext()
  const context = {
    addScore: (pts: number) => {
      if (!machine.canMutateGameplay()) return;
      score += pts;
    },
    damagePlayer: (dmg: number) => {
      if (!machine.canMutateGameplay()) return;
      health = Math.max(0, health - dmg);
    },
    healPlayer: (amount: number) => {
      if (!machine.canMutateGameplay()) return;
      health = Math.min(100, health + amount);
    },
    spawnBonusEntity: () => {
      if (!machine.canMutateGameplay()) return;
      bonusSpawned++;
    },
    grantPowerup: () => {
      if (!machine.canMutateGameplay()) return;
      powerupGranted++;
    },
  };

  // 1. While ACTIVE, mutations succeed
  context.addScore(50);
  context.damagePlayer(25);
  context.spawnBonusEntity();
  assert.equal(score, 150);
  assert.equal(health, 75);
  assert.equal(bonusSpawned, 1);

  // 2. Terminal transition: LOST
  machine.setLost('HEALTH DEPLETED');
  assert.equal(machine.canMutateGameplay(), false);

  // 3. Post-terminal delayed callbacks / events attempt to mutate state
  context.addScore(200);
  context.healPlayer(50);
  context.damagePlayer(10);
  context.spawnBonusEntity();
  context.grantPowerup();

  // State remains pristine and unchanged
  assert.equal(score, 150);
  assert.equal(health, 75);
  assert.equal(bonusSpawned, 1);
  assert.equal(powerupGranted, 0);
});

test('Terminal Safety: Deferred callbacks (timers, tweens, rules, overlaps, transitions) cannot mutate post-terminal', async () => {
  const terminalStates = ['WON', 'LOST', 'DESTROYED'] as const;

  for (const terminalState of terminalStates) {
    const machine = new RuntimeStateMachine('ACTIVE');
    const evaluator = new ObjectiveEvaluator({
      type: 'collect_all',
      target_count: 10,
      description: 'Collect gems',
    });
    const waveController = new WaveController(5);

    let score = 100;
    let health = 100;
    let collections = 0;
    let regionTransitions = 0;

    // Simulation of GameScene deferred pathways
    const guardedContext = {
      addScore: (pts: number) => {
        if (!machine.canMutateGameplay()) return false;
        score += pts;
        return true;
      },
      damagePlayer: (dmg: number) => {
        if (!machine.canMutateGameplay()) return false;
        health = Math.max(0, health - dmg);
        return true;
      },
      healPlayer: (amt: number) => {
        if (!machine.canMutateGameplay()) return false;
        health = Math.min(100, health + amt);
        return true;
      },
      handleCollect: () => {
        if (!machine.canMutateGameplay()) return false;
        collections++;
        evaluator.recordCollection(1);
        return true;
      },
      handleRegionTransition: () => {
        if (!machine.canMutateGameplay()) return false;
        regionTransitions++;
        return true;
      },
    };

    // Pre-schedule deferred callbacks (simulating timer events and tween completions created before game over)
    const pendingTimerCallback = () => {
      guardedContext.damagePlayer(20);
      guardedContext.addScore(50);
    };

    const pendingTweenOnComplete = () => {
      guardedContext.healPlayer(30);
      guardedContext.handleCollect();
    };

    const pendingOverlapCallback = () => {
      guardedContext.handleCollect();
      guardedContext.damagePlayer(15);
    };

    const pendingRegionTransitionCallback = () => {
      guardedContext.handleRegionTransition();
    };

    const pendingWaveAdvanceRequest = () => {
      if (!machine.canMutateGameplay()) return false;
      return waveController.requestNextWave();
    };

    // Transition to terminal state
    if (terminalState === 'WON') {
      machine.setWon('OBJECTIVE_ACCOMPLISHED');
      waveController.setTerminal(true);
    } else if (terminalState === 'LOST') {
      machine.setLost('OUT_OF_BOUNDS');
      waveController.setTerminal(true);
    } else {
      machine.destroy();
      waveController.setTerminal(true);
    }

    assert.equal(machine.isTerminal(), true);
    assert.equal(machine.canMutateGameplay(), false);

    // Now execute all deferred pathways (they fire AFTER terminal transition)
    pendingTimerCallback();
    pendingTweenOnComplete();
    pendingOverlapCallback();
    pendingRegionTransitionCallback();
    const waveAdvanceResult = pendingWaveAdvanceRequest();

    // Verify zero mutations occurred
    assert.equal(score, 100, `Score must remain unchanged in ${terminalState}`);
    assert.equal(health, 100, `Health must remain unchanged in ${terminalState}`);
    assert.equal(collections, 0, `Collections must remain 0 in ${terminalState}`);
    assert.equal(regionTransitions, 0, `Region transitions must remain 0 in ${terminalState}`);
    assert.equal(waveAdvanceResult, false, `Wave advance must be rejected in ${terminalState}`);
    assert.equal(evaluator.getProgress().current, 0, `Objective progress must not advance in ${terminalState}`);
  }
});
