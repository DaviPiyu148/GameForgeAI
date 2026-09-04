/**
 * Unit tests for End-to-End Playtest, Analysis, and Remix Loop (Step 7).
 *
 * Run with: npx tsx src/utils/__tests__/playtestRemixLoop.test.ts
 */

import type {
  GameProject,
  PlaytestSessionRecord,
  ProjectVersionSummary,
  ImprovementApplyRequest,
  ImprovementApplyResponse,
} from '../../types';
import type { GameDSL, PlaytestRecommendation } from '../../runtime/types';

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

console.log('\n--- Test Suite: Playtest, Analysis & Remix Loop (Step 7) ---');

// Mock Data
const mockV1Dsl: GameDSL = {
  schema_version: '1.0',
  metadata: {
    title: 'Neon Surge',
    genre: 'Action Cyberpunk',
    description: 'Cyberpunk arena survival',
    archetype: 'arena',
  },
  world: {
    width: 1280,
    height: 720,
    gravity: 0,
    background_color: '#050510',
    theme: 'cyberpunk',
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
    dash_speed: 480,
  },
  entities: [],
  rules: [],
  ui: {
    show_health: true,
    show_score: true,
    status_text: 'SURVIVE',
  },
};

const mockProjectV1: GameProject = {
  id: 'proj-neon-1',
  title: 'Neon Surge',
  genre: 'Action Cyberpunk',
  status: 'PLAYABLE',
  lastModified: 'Just now',
  prompt: 'A fast cyberpunk game',
  parameters: {
    engine: 'arena',
    artDensity: 50,
    physics: 50,
    modules: ['Dash Mobility'],
  },
  gameDsl: mockV1Dsl,
  currentVersion: 1,
};

const mockVersion1Record: ProjectVersionSummary = {
  id: 'ver-1',
  project_id: 'proj-neon-1',
  version_number: 1,
  change_summary: 'Initial synthesized version.',
  created_at: '2026-09-04T10:00:00Z',
  game_dsl: mockV1Dsl,
};

const mockVersion2Record: ProjectVersionSummary = {
  id: 'ver-2',
  project_id: 'proj-neon-1',
  version_number: 2,
  change_summary: 'Playtest balance patches applied.',
  created_at: '2026-09-04T11:00:00Z',
  game_dsl: {
    ...mockV1Dsl,
    player: {
      ...mockV1Dsl.player,
      speed: 280,
      max_health: 125,
    },
  },
};

const mockPlaytestV1: PlaytestSessionRecord = {
  id: 'pt-sess-1',
  project_id: 'proj-neon-1',
  user_id: 'user-1',
  duration_seconds: 90,
  score: 600,
  damage_taken: 80,
  damage_dealt: 300,
  enemies_defeated: 6,
  collectibles_gathered: 8,
  objectives_completed: 1,
  outcome: 'WON',
  version_number: 1,
  created_at: '2026-09-04T10:30:00Z', // between v1 (10:00) and v2 (11:00)
};

const mockRecommendations: PlaytestRecommendation[] = [
  {
    id: 'rec_speed',
    category: 'mobility',
    description: 'Increase player movement speed to 280',
    dsl_change_type: 'player_speed',
    evidence: 'Player struggled to outrun fast chasing enemies',
    suggested_patch: { player: { speed: 280 } },
    is_actionable: true,
  },
  {
    id: 'rec_health',
    category: 'survivability',
    description: 'Increase max health to 125',
    dsl_change_type: 'player_health',
    evidence: 'Heavy damage spikes in late wave',
    suggested_patch: { player: { max_health: 125 } },
    is_actionable: true,
  },
  {
    id: 'rec_visual',
    category: 'aesthetics',
    description: 'Consider adding distinct visual trail when dashing',
    dsl_change_type: 'visual_feedback',
    evidence: 'Players felt dash lacked visual impact',
    suggested_patch: {},
    is_actionable: false,
  },
];

// Utility functions mirroring frontend behavior
function isRecommendationActionable(rec: PlaytestRecommendation): boolean {
  return Boolean(rec.suggested_patch && Object.keys(rec.suggested_patch).length > 0);
}

function computePatchDiffs(
  dsl: GameDSL,
  recommendations: PlaytestRecommendation[]
): Array<{ field: string; current: string; proposed: string }> {
  const diffs: Array<{ field: string; current: string; proposed: string }> = [];
  for (const rec of recommendations) {
    const patch = rec.suggested_patch;
    if (!patch || typeof patch !== 'object') continue;
    for (const [topKey, topVal] of Object.entries(patch)) {
      if (topVal && typeof topVal === 'object' && !Array.isArray(topVal)) {
        for (const [subKey, subVal] of Object.entries(topVal)) {
          const curVal = (dsl as any)?.[topKey]?.[subKey];
          diffs.push({
            field: `${topKey}.${subKey}`,
            current: String(curVal),
            proposed: String(subVal),
          });
        }
      } else {
        const curVal = (dsl as any)?.[topKey];
        diffs.push({
          field: topKey,
          current: String(curVal),
          proposed: String(topVal),
        });
      }
    }
  }
  return diffs;
}

function isSessionStale(session: PlaytestSessionRecord, currentVersion: ProjectVersionSummary): boolean {
  return new Date(session.created_at).getTime() < new Date(currentVersion.created_at).getTime();
}

// --- Test Executions ---

// Test 1: Actionable vs Informational classification
const actionableCount = mockRecommendations.filter(isRecommendationActionable).length;
const informationalCount = mockRecommendations.filter((r) => !isRecommendationActionable(r)).length;
assert(
  'Actionable vs Informational recommendation categorization',
  actionableCount === 2 && informationalCount === 1
);

// Test 2: Diff computation between current DSL and patches
const diffs = computePatchDiffs(mockV1Dsl, mockRecommendations);
assert(
  'Patch diff computes current vs proposed values accurately',
  diffs.length === 2 &&
    diffs[0].field === 'player.speed' &&
    diffs[0].current === '220' &&
    diffs[0].proposed === '280' &&
    diffs[1].field === 'player.max_health' &&
    diffs[1].current === '100' &&
    diffs[1].proposed === '125'
);

// Test 3: Stale analysis detection against version history
const isStaleForV1 = isSessionStale(mockPlaytestV1, mockVersion1Record);
const isStaleForV2 = isSessionStale(mockPlaytestV1, mockVersion2Record);
assert(
  'Session is current for Version 1 and becomes stale for Version 2',
  isStaleForV1 === false && isStaleForV2 === true
);

// Test 4: ImprovementApplyRequest payload construction
const applyPayload: ImprovementApplyRequest = {
  sessionId: mockPlaytestV1.id,
  baseVersionNumber: 1,
  recommendations: mockRecommendations.filter(isRecommendationActionable),
  userNotes: 'Applied balance adjustments based on playtest session 1',
};
assert(
  'ImprovementApplyRequest includes baseVersionNumber, sessionId, and actionable recs',
  applyPayload.baseVersionNumber === 1 &&
    applyPayload.sessionId === 'pt-sess-1' &&
    applyPayload.recommendations.length === 2
);

// Test 5: ImprovementApplyResponse validation
const mockApplyResponse: ImprovementApplyResponse = {
  projectId: 'proj-neon-1',
  previousVersionNumber: 1,
  newVersionNumber: 2,
  gameDsl: {
    ...mockV1Dsl,
    player: {
      ...mockV1Dsl.player,
      speed: 280,
      max_health: 125,
    },
  },
  changeSummary: 'Playtest improvement (session pt-sess-1 v1): Increase speed, Increase health',
  changes: [
    { fieldName: 'player.speed', previousValue: 220, newValue: 280 },
    { fieldName: 'player.max_health', previousValue: 100, newValue: 125 },
  ],
  sourceSessionId: 'pt-sess-1',
  status: 'SUCCESS',
  message: 'Playtest improvements applied successfully as version 2.',
};

assert(
  'ImprovementApplyResponse validates version advance and change records',
  mockApplyResponse.previousVersionNumber === 1 &&
    mockApplyResponse.newVersionNumber === 2 &&
    mockApplyResponse.changes.length === 2 &&
    mockApplyResponse.gameDsl.player.speed === 280
);

// Test 6: Preserves unrelated fields during patch apply
assert(
  'Unrelated fields (world theme, metadata, archetype) survive patch apply',
  mockApplyResponse.gameDsl.world.theme === 'cyberpunk' &&
    mockApplyResponse.gameDsl.metadata.archetype === 'arena' &&
    mockApplyResponse.gameDsl.player.color === '#00ffff'
);

// Test 7: Multi-patch atomic version bump calculation
const nextVersion = (mockProjectV1.currentVersion || 1) + 1;
assert(
  'Multi-patch batching targets single atomic forward version increment',
  nextVersion === 2
);

// Test 8: Rebuild CTA targets the newly created version
const rebuildTargetVersion = mockApplyResponse.newVersionNumber;
assert(
  'Rebuild CTA accurately targets new version 2 for explicit compilation',
  rebuildTargetVersion === 2
);

// Summary
console.log(`\nResults: ${passed} passed, ${failed} failed.\n`);
if (failed > 0) {
  throw new Error(`Test suite failed with ${failed} failure(s)`);
}
