import test from 'node:test';
import assert from 'node:assert/strict';
import { createPRNG } from '../prng';
import { WaveController } from '../WaveController';
import { ObjectiveEvaluator } from '../ObjectiveEvaluator';

interface SimulationTrace {
  waveEnemySpawns: Array<{ wave: number; x: number; y: number }>;
  bonusCollectibleSpawns: Array<{ x: number; y: number }>;
  objectiveMilestones: number[];
  finalOutcome: 'WON' | 'LOST' | 'IN_PROGRESS';
}

function runSimulation(seed: number, inputs: { clearsWave1: boolean; collectsBonus: boolean }): SimulationTrace {
  const prng = createPRNG(seed);
  const trace: SimulationTrace = {
    waveEnemySpawns: [],
    bonusCollectibleSpawns: [],
    objectiveMilestones: [],
    finalOutcome: 'IN_PROGRESS',
  };

  const stageBounds = { width: 1200, height: 800 };

  const spawnWaveEnemies = (waveNum: number) => {
    const count = waveNum * 2;
    for (let i = 0; i < count; i++) {
      const rx = prng();
      const ry = prng();
      const x = Math.floor(80 + rx * (stageBounds.width - 160));
      const y = Math.floor(80 + ry * (stageBounds.height - 160));
      trace.waveEnemySpawns.push({ wave: waveNum, x, y });
    }
  };

  const spawnBonus = () => {
    const rx = prng();
    const ry = prng();
    const x = Math.floor(80 + rx * (stageBounds.width - 160));
    const y = Math.floor(80 + ry * (stageBounds.height - 160));
    trace.bonusCollectibleSpawns.push({ x, y });
  };

  const objectiveEvaluator = new ObjectiveEvaluator({
    type: 'defeat_all',
    target_count: 6,
    description: 'Eliminate all enemies',
  });

  const waveController = new WaveController(2, {
    onWaveSpawnEnemies: (config) => spawnWaveEnemies(config.waveNumber),
    onAllWavesCompleted: () => {
      trace.finalOutcome = 'WON';
    },
  });

  // 1. Start Initial Wave
  waveController.startInitialWave();
  spawnBonus();

  // 2. Process inputs
  if (inputs.clearsWave1) {
    // Defeat wave 1 enemies (2 enemies)
    objectiveEvaluator.recordEnemyDefeat(2);
    trace.objectiveMilestones.push(objectiveEvaluator.getProgress().current);

    const clearRes = waveController.onWaveEnemiesCleared();
    if (clearRes.shouldAdvance) {
      waveController.requestNextWave();
      spawnBonus();
    }
  }

  if (inputs.collectsBonus) {
    // Defeat wave 2 enemies (4 enemies)
    objectiveEvaluator.recordEnemyDefeat(4);
    trace.objectiveMilestones.push(objectiveEvaluator.getProgress().current);

    const clearRes2 = waveController.onWaveEnemiesCleared();
    if (clearRes2.isVictory) {
      trace.finalOutcome = 'WON';
    }
  }

  return trace;
}

test('Deterministic Replay: Same seed + same inputs produces 100% bit-exact simulation trace', () => {
  const seed = 987654321;
  const inputSequence = { clearsWave1: true, collectsBonus: true };

  const runA = runSimulation(seed, inputSequence);
  const runB = runSimulation(seed, inputSequence);

  // Assert exact equality across all simulation outputs
  assert.deepEqual(runA.waveEnemySpawns, runB.waveEnemySpawns, 'Wave enemy spawn coordinates must be identical');
  assert.deepEqual(runA.bonusCollectibleSpawns, runB.bonusCollectibleSpawns, 'Bonus collectible coordinates must be identical');
  assert.deepEqual(runA.objectiveMilestones, runB.objectiveMilestones, 'Objective progression milestones must be identical');
  assert.equal(runA.finalOutcome, runB.finalOutcome, 'Final terminal outcome must be identical');
  assert.equal(runA.finalOutcome, 'WON');
});

test('Deterministic Replay: Different seeds produce divergent simulation outputs', () => {
  const inputSequence = { clearsWave1: true, collectsBonus: true };

  const runSeed1 = runSimulation(111111, inputSequence);
  const runSeed2 = runSimulation(999999, inputSequence);

  // Enemy spawns and collectible spawns must diverge between distinct seeds
  assert.notDeepEqual(
    runSeed1.waveEnemySpawns,
    runSeed2.waveEnemySpawns,
    'Different seeds must produce divergent enemy spawn positions'
  );
  assert.notDeepEqual(
    runSeed1.bonusCollectibleSpawns,
    runSeed2.bonusCollectibleSpawns,
    'Different seeds must produce divergent bonus positions'
  );
});
