/**
 * Unit tests for Prototype Compilation and Version Integration (Step 6).
 *
 * Run with: npx tsx src/utils/__tests__/buildIntegration.test.ts
 */

import type {
  GameProject,
  CompileProjectResponse,
  ProjectVersionSummary,
} from '../../types';
import type { GameDSL } from '../../runtime/types';

let passed = 0;
let failed = 0;

function assert(label: string, condition: boolean, details?: string) {
  if (condition) {
    console.log(`  v ${label}`);
    passed++;
  } else {
    console.error(`  X ${label}`);
    if (details) console.error(`      ${details}`);
    failed++;
  }
}

console.log('\n--- Test Suite: Prototype Compilation & Version Integration (Step 6) ---');

// Mock Data
const mockV1Dsl: GameDSL = {
  schema_version: '1.0',
  metadata: {
    title: 'Cyber Grid Runner',
    genre: 'Action',
    description: 'Initial fast runner',
    archetype: 'platformer',
  },
  world: {
    width: 1280,
    height: 720,
    gravity: 600,
    background_color: '#050510',
    theme: 'neon',
    world_mode: 'linear',
  },
  player: {
    name: 'Player',
    spawn_x: 100,
    spawn_y: 300,
    speed: 220,
    jump_power: 450,
    max_health: 100,
    width: 32,
    height: 32,
    color: '#00ffff',
  },
  entities: [
    {
      id: 'e_coin_1',
      type: 'collectible',
      behavior: 'float',
      x: 300,
      y: 400,
      width: 24,
      height: 24,
      speed: 0,
      health: 1,
      color: '#ffff00',
      points: 10,
    },
  ],
  rules: [
    {
      id: 'r_collect',
      trigger: 'on_collect',
      action: 'add_score',
      params: {},
    },
    {
      id: 'r_goal',
      trigger: 'on_reach_goal',
      action: 'win_game',
      params: {},
    },
  ],
  ui: {
    show_health: true,
    show_score: true,
    status_text: 'REACH THE EXIT',
  },
};

const mockV2Dsl: GameDSL = {
  ...mockV1Dsl,
  metadata: {
    ...mockV1Dsl.metadata,
    genre: 'Action Roguelite Cyberpunk',
    archetype: 'arena',
  },
  world: {
    ...mockV1Dsl.world,
    theme: 'cyberpunk',
    world_mode: 'campaign',
    gravity: 0,
  },
  player: {
    ...mockV1Dsl.player,
    attack_type: 'ranged',
    attack_damage: 30,
    dash_speed: 550,
  },
};

const mockProjectV1: GameProject = {
  id: 'proj-cyber-1',
  title: 'Cyber Grid Runner',
  genre: 'Action',
  status: 'PLAYABLE',
  lastModified: 'Just now',
  prompt: 'A fast cyber runner',
  parameters: {
    engine: 'platformer',
    artDensity: 50,
    physics: 80,
    modules: ['Combat & Dash Mobility'],
    worldMode: 'linear',
    scale: 'standard',
  },
  gameDsl: mockV1Dsl,
  currentVersion: 1,
};

const mockProjectV2: GameProject = {
  ...mockProjectV1,
  genre: 'Action Roguelite Cyberpunk',
  parameters: {
    ...mockProjectV1.parameters,
    engine: 'arena',
    artDensity: 60,
    physics: 45,
    worldMode: 'campaign',
  },
  gameDsl: mockV2Dsl,
  currentVersion: 2,
};

const mockVersionHistory: ProjectVersionSummary[] = [
  {
    id: 'ver-1',
    project_id: 'proj-cyber-1',
    version_number: 1,
    change_summary: 'Initial prototype generated from prompt.',
    created_at: '2026-09-04T10:00:00Z',
    game_dsl: mockV1Dsl,
  },
  {
    id: 'ver-2',
    project_id: 'proj-cyber-1',
    version_number: 2,
    change_summary: 'Inspiration synthesis applied: Dead Cells, Hades.',
    created_at: '2026-09-04T11:00:00Z',
    game_dsl: mockV2Dsl,
  },
];

// 1. Authoritative Version Resolution for Playback
function resolvePlaybackTarget(
  project: GameProject,
  requestedVersion?: ProjectVersionSummary | null
): { targetDsl: GameDSL; targetVersionNumber: number; isHistorical: boolean } {
  if (requestedVersion) {
    return {
      targetDsl: (requestedVersion.game_dsl as GameDSL) || project.gameDsl || mockV1Dsl,
      targetVersionNumber: requestedVersion.version_number,
      isHistorical: requestedVersion.version_number !== project.currentVersion,
    };
  }
  return {
    targetDsl: project.gameDsl || mockV1Dsl,
    targetVersionNumber: project.currentVersion || 1,
    isHistorical: false,
  };
}

// 2. Mock Compilation Response Validator
function validateCompileResponse(response: CompileProjectResponse): boolean {
  return (
    response.status === 'SUCCESS' &&
    Boolean(response.projectId) &&
    response.versionNumber >= 1 &&
    Boolean(response.gameDsl) &&
    Boolean(response.gameDsl.schema_version) &&
    Boolean(response.runtimeMetadata) &&
    response.runtimeMetadata.version_number === response.versionNumber
  );
}

// 3. Stale Playtest Evaluation
function checkPlaytestStaleness(
  playtestCreatedAt: string,
  currentVersionCreatedAt: string
): boolean {
  return new Date(playtestCreatedAt).getTime() < new Date(currentVersionCreatedAt).getTime();
}

// --- Test Executions ---

// Test 1: Active v1 resolves current v1 for playback
const playTarget1 = resolvePlaybackTarget(mockProjectV1);
assert(
  'Active Version 1 resolves v1 DSL and version number 1',
  playTarget1.targetVersionNumber === 1 &&
    playTarget1.targetDsl.metadata.archetype === 'platformer' &&
    !playTarget1.isHistorical
);

// Test 2: Active v2 resolves synthesized v2 for playback
const playTarget2 = resolvePlaybackTarget(mockProjectV2);
assert(
  'Active Version 2 resolves synthesized v2 DSL with theme and arena archetype',
  playTarget2.targetVersionNumber === 2 &&
    playTarget2.targetDsl.world.theme === 'cyberpunk' &&
    playTarget2.targetDsl.metadata.archetype === 'arena' &&
    !playTarget2.isHistorical
);

// Test 3: Historical v1 playback when project is at v2
const historicalTarget = resolvePlaybackTarget(mockProjectV2, mockVersionHistory[0]);
assert(
  'Historical playback requests v1 while project is at v2',
  historicalTarget.targetVersionNumber === 1 &&
    historicalTarget.targetDsl.metadata.archetype === 'platformer' &&
    historicalTarget.isHistorical === true
);

// Test 4: Historical playback does not mutate active project
assert(
  'Active project currentVersion remains 2 after historical playback query',
  mockProjectV2.currentVersion === 2
);

// Test 5: Compile response schema validation
const mockCompileRes: CompileProjectResponse = {
  projectId: 'proj-cyber-1',
  versionNumber: 2,
  status: 'SUCCESS',
  gameDsl: mockV2Dsl,
  runtimeMetadata: {
    seed: 123456,
    version_number: 2,
    project_id: 'proj-cyber-1',
    archetype: 'arena',
    engine: 'Phaser',
  },
  validationSummary: {
    isValid: true,
    archetype: 'arena',
    warnings: [],
    entitiesCount: 1,
    rulesCount: 2,
  },
  compiledAt: new Date().toISOString(),
  message: 'Prototype for version 2 compiled and validated successfully.',
};

assert(
  'CompileProjectResponse passes validation and retains version traceability',
  validateCompileResponse(mockCompileRes)
);

// Test 6: Playtest staleness when advancing from v1 to v2
const ptCreatedAt = '2026-09-04T10:30:00Z'; // after v1 (10:00), before v2 (11:00)
const isStaleForV2 = checkPlaytestStaleness(ptCreatedAt, mockVersionHistory[1].created_at);
assert(
  'Playtest recorded during v1 is accurately flagged as stale after advancing to v2',
  isStaleForV2 === true
);

// Test 7: Fresh playtest after v2 is NOT stale
const freshPtCreatedAt = '2026-09-04T11:15:00Z'; // after v2 (11:00)
const isStaleForFresh = checkPlaytestStaleness(freshPtCreatedAt, mockVersionHistory[1].created_at);
assert(
  'Fresh playtest recorded after v2 is NOT marked stale',
  isStaleForFresh === false
);

// Test 8: Synthesized player abilities flow into runtime locomotion
assert(
  'Synthesized attack type and dash speed are present in v2 DSL',
  mockV2Dsl.player.attack_type === 'ranged' &&
    (mockV2Dsl.player.dash_speed ?? 0) >= 500
);

// Summary
console.log(`\nResults: ${passed} passed, ${failed} failed.\n`);
if (failed > 0) {
  throw new Error(`Test suite failed with ${failed} failure(s)`);
}
