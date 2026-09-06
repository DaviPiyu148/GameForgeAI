import test from 'node:test';
import assert from 'node:assert/strict';
import { RuntimeConfigCompiler } from '../RuntimeConfig';
import {
  PLATFORMER_FIXTURE,
  ARENA_FIXTURE,
  SHOOTER_FIXTURE,
  COLLECTOR_FIXTURE,
  SURVIVAL_FIXTURE,
  RUNNER_FIXTURE,
  OPEN_WORLD_FIXTURE,
} from '../fixtures';

test('Fixtures Compilation: All canonical archetype fixtures compile into valid RuntimeGameConfig', () => {
  const fixtures = [
    { name: 'Platformer', dsl: PLATFORMER_FIXTURE, expectedArchetype: 'platformer' },
    { name: 'Arena', dsl: ARENA_FIXTURE, expectedArchetype: 'arena' },
    { name: 'Shooter', dsl: SHOOTER_FIXTURE, expectedArchetype: 'shooter' },
    { name: 'Collector', dsl: COLLECTOR_FIXTURE, expectedArchetype: 'collector' },
    { name: 'Survival', dsl: SURVIVAL_FIXTURE, expectedArchetype: 'survival' },
    { name: 'Runner', dsl: RUNNER_FIXTURE, expectedArchetype: 'runner' },
    { name: 'OpenWorld', dsl: OPEN_WORLD_FIXTURE, expectedArchetype: 'survival' },
  ];

  for (const f of fixtures) {
    const res = RuntimeConfigCompiler.compile(f.dsl);
    assert.equal(res.success, true, `Fixture '${f.name}' failed to compile: ${res.error}`);
    const config = res.config!;
    assert.equal(config.archetypePolicy.archetype, f.expectedArchetype);
    assert.ok(config.stages.length >= 1);

    if (config.worldMode === 'open_world') {
      assert.ok(config.openWorldConfig);
      assert.ok(config.openWorldConfig.openWorldDef.regions.length >= 2);
    } else {
      assert.ok(config.stages[0].entities.length >= 1);
      assert.ok(config.stages[0].rules.length >= 1);
    }
  }
});
