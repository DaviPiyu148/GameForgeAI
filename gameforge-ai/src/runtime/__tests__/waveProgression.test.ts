import test from 'node:test';
import assert from 'node:assert/strict';
import { WaveController } from '../WaveController';
import { RuleEngine, type GameContext } from '../rules';
import type { RuleDef } from '../types';

test('P0-002 Regression: on_wave_start -> spawn_wave does not recurse during startup', () => {
  let waveStarts = 0;
  let spawnCount = 0;

  const waveCtrl = new WaveController(3, {
    onWaveStartNotification: (waveNum) => {
      waveStarts++;
      ruleEngine.trigger('on_wave_start', dummyContext, { wave: waveNum });
    },
    onWaveSpawnEnemies: () => {
      spawnCount++;
    },
  });

  const recursiveWaveRules: RuleDef[] = [
    {
      id: 'rule_wave_recurse',
      trigger: 'on_wave_start',
      action: 'spawn_wave',
      params: { wave: 1 },
    },
  ];

  const dummyContext: GameContext = {
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
      waveCtrl.requestNextWave();
    },
  };

  const ruleEngine = new RuleEngine(recursiveWaveRules);

  // Scene startup starts initial wave
  assert.doesNotThrow(() => {
    waveCtrl.startInitialWave();
  });

  // Must cleanly start Wave 1 without infinite recursion
  assert.equal(waveCtrl.getCurrentWave(), 1);
  assert.equal(waveStarts, 1);
  assert.equal(spawnCount, 1);
});

test('WaveController: complete progression from wave 1 to victory', () => {
  let victoryCalled = false;
  let enemiesSpawned = 0;

  const waveCtrl = new WaveController(2, {
    onWaveSpawnEnemies: (cfg) => {
      enemiesSpawned += cfg.enemyCount;
    },
    onAllWavesCompleted: () => {
      victoryCalled = true;
    },
  });

  // Wave 1
  assert.equal(waveCtrl.startInitialWave(), true);
  assert.equal(waveCtrl.getCurrentWave(), 1);
  assert.equal(enemiesSpawned, 2);

  // Clear wave 1 enemies
  const outcome1 = waveCtrl.onWaveEnemiesCleared();
  assert.equal(outcome1.shouldAdvance, true);
  assert.equal(outcome1.isVictory, false);

  // Advance to wave 2
  assert.equal(waveCtrl.requestNextWave(), true);
  assert.equal(waveCtrl.getCurrentWave(), 2);
  assert.equal(enemiesSpawned, 6); // 2 + 4

  // Clear wave 2 enemies (final wave)
  const outcome2 = waveCtrl.onWaveEnemiesCleared();
  assert.equal(outcome2.shouldAdvance, false);
  assert.equal(outcome2.isVictory, true);
  assert.equal(victoryCalled, true);
  assert.equal(waveCtrl.isCompleted(), true);

  // Cannot advance beyond max waves
  assert.equal(waveCtrl.requestNextWave(), false);
});

test('WaveController: terminal state prevents new waves', () => {
  const waveCtrl = new WaveController(3);
  waveCtrl.startInitialWave();
  assert.equal(waveCtrl.getCurrentWave(), 1);

  // Player dies -> set terminal
  waveCtrl.setTerminal(true);

  // Requesting next wave must be rejected
  assert.equal(waveCtrl.requestNextWave(), false);
  assert.equal(waveCtrl.getCurrentWave(), 1);
});
