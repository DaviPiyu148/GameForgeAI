import test from 'node:test';
import assert from 'node:assert/strict';
import { WaveController, type WaveSpawnConfig } from '../WaveController';
import { RuleEngine, type GameContext } from '../rules';
import type { RuleDef } from '../types';

test('WaveController: startup and initial wave progression', () => {
  const spawned: WaveSpawnConfig[] = [];
  const notifications: number[] = [];
  let allCompleted = false;

  const controller = new WaveController(3, {
    onWaveSpawnEnemies: (config) => spawned.push(config),
    onWaveStartNotification: (num) => notifications.push(num),
    onAllWavesCompleted: () => { allCompleted = true; },
  });

  assert.equal(controller.getCurrentWave(), 0);
  assert.equal(controller.getState(), 'IDLE');

  // 1. Initial wave startup
  const started = controller.startInitialWave();
  assert.equal(started, true);
  assert.equal(controller.getCurrentWave(), 1);
  assert.equal(controller.getState(), 'ACTIVE');
  assert.equal(spawned.length, 1);
  assert.equal(spawned[0].waveNumber, 1);
  assert.equal(notifications.length, 1);
  assert.equal(notifications[0], 1);
  assert.equal(allCompleted, false);

  // Calling startInitialWave again should be a no-op
  assert.equal(controller.startInitialWave(), false);
});

test('WaveController: intermediate waves advance correctly up to max waves', () => {
  const spawned: WaveSpawnConfig[] = [];
  const notifications: number[] = [];
  let allCompleted = false;

  const controller = new WaveController(3, {
    onWaveSpawnEnemies: (config) => spawned.push(config),
    onWaveStartNotification: (num) => notifications.push(num),
    onAllWavesCompleted: () => { allCompleted = true; },
  });

  controller.startInitialWave();

  // Wave 1 cleared
  const clear1 = controller.onWaveEnemiesCleared();
  assert.equal(clear1.shouldAdvance, true);
  assert.equal(clear1.isVictory, false);

  // Advance to Wave 2
  const advancedTo2 = controller.requestNextWave();
  assert.equal(advancedTo2, true);
  assert.equal(controller.getCurrentWave(), 2);
  assert.equal(controller.getState(), 'ACTIVE');

  // Wave 2 cleared
  const clear2 = controller.onWaveEnemiesCleared();
  assert.equal(clear2.shouldAdvance, true);
  assert.equal(clear2.isVictory, false);

  // Advance to Wave 3 (final wave)
  const advancedTo3 = controller.requestNextWave();
  assert.equal(advancedTo3, true);
  assert.equal(controller.getCurrentWave(), 3);

  // Wave 3 cleared -> triggers victory / all completed
  const clear3 = controller.onWaveEnemiesCleared();
  assert.equal(clear3.shouldAdvance, false);
  assert.equal(clear3.isVictory, true);
  assert.equal(allCompleted, true);
  assert.equal(controller.isCompleted(), true);

  // Subsequent requestNextWave after completion should return false
  assert.equal(controller.requestNextWave(), false);
});

test('WaveController: blocks wave progression when terminal state (death or game over) is set', () => {
  const spawned: WaveSpawnConfig[] = [];
  const controller = new WaveController(3, {
    onWaveSpawnEnemies: (config) => spawned.push(config),
  });

  controller.startInitialWave();
  assert.equal(controller.getCurrentWave(), 1);

  // Set terminal (player died or stage finished)
  controller.setTerminal(true);

  // Subsequent requests to advance must be rejected
  assert.equal(controller.requestNextWave(), false);
  assert.equal(controller.getCurrentWave(), 1);

  const clearResult = controller.onWaveEnemiesCleared();
  assert.equal(clearResult.shouldAdvance, false);
  assert.equal(clearResult.isVictory, false);
});

test('WaveController + RuleEngine: cyclic wave rule is cleanly suppressed without recursion', () => {
  let waveSpawnAttempts = 0;
  let waveStartsCount = 0;

  // Rule: on_wave_start -> spawn_wave (which requests next wave!)
  const cyclicRules: RuleDef[] = [
    {
      id: 'rule_cyclic_wave',
      trigger: 'on_wave_start',
      action: 'spawn_wave',
      params: {},
    },
  ];

  const ruleEngine = new RuleEngine(cyclicRules);

  const controller = new WaveController(5, {
    onWaveStartNotification: (waveNum) => {
      waveStartsCount++;
      // Trigger rules on wave start
      ruleEngine.trigger('on_wave_start', mockContext, { wave: waveNum });
    },
  });

  const mockContext: GameContext = {
    score: 0,
    health: 100,
    maxHealth: 100,
    playerSpeed: 200,
    isWon: false,
    isLost: false,
    addScore: () => {},
    damagePlayer: () => {},
    healPlayer: () => {},
    setGameWon: () => {},
    setGameLost: () => {},
    applySpeedBoost: () => {},
    spawnWave: () => {
      waveSpawnAttempts++;
      // Attempt to advance wave recursively
      controller.requestNextWave();
    },
  };

  // Start wave 1
  const started = controller.startInitialWave();
  assert.equal(started, true);

  // Verify: Wave start notification fired once for wave 1
  assert.equal(waveStartsCount, 1);
  // spawn_wave action attempted once
  assert.equal(waveSpawnAttempts, 1);
  // BUT controller rejected recursive requestNextWave during notification lock
  // Current wave remains 1, not 2, 3, etc.
  assert.equal(controller.getCurrentWave(), 1);
  assert.equal(controller.getState(), 'ACTIVE');
});

test('WaveController + RuleEngine: explicit wave-spawn rule after clear advances legally', () => {
  let wavesSpawned = 0;
  const controller = new WaveController(3, {
    onWaveSpawnEnemies: () => { wavesSpawned++; },
  });

  const mockContext: GameContext = {
    score: 0,
    health: 100,
    maxHealth: 100,
    playerSpeed: 200,
    isWon: false,
    isLost: false,
    addScore: () => {},
    damagePlayer: () => {},
    healPlayer: () => {},
    setGameWon: () => {},
    setGameLost: () => {},
    applySpeedBoost: () => {},
    spawnWave: () => {
      controller.requestNextWave();
    },
  };

  controller.startInitialWave();
  assert.equal(controller.getCurrentWave(), 1);
  assert.equal(wavesSpawned, 1);

  // Wave 1 cleared, legitimate rule calls spawnWave
  const rules: RuleDef[] = [
    {
      id: 'rule_manual_wave',
      trigger: 'on_enemy_defeat',
      action: 'spawn_wave',
      params: {},
    },
  ];

  const ruleEngine = new RuleEngine(rules);
  ruleEngine.trigger('on_enemy_defeat', mockContext);

  assert.equal(controller.getCurrentWave(), 2);
  assert.equal(wavesSpawned, 2);
});
