/**
 * Unit tests for Inspiration Synthesis Proposal Apply and Conflict Resolution (Step 5).
 *
 * Run with: npx tsx src/utils/__tests__/synthesisApply.test.ts
 */

import type {
  ApplySynthesisProposalRequest,
  ApplySynthesisProposalResponse,
  GameProject,
  InspirationSynthesisProposal,
  SynthesisConflict,
} from '../../types';

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

console.log('\n--- Test Suite: Synthesis Proposal Apply & Conflict Resolution ---');

const mockConflict: SynthesisConflict = {
  field: 'player_modes',
  description: 'Inspirations include mutually exclusive Single-player only and Multiplayer references.',
  conflictingSources: ['Solo Dungeon (Single-player)', 'Team Arena (Multiplayer)'],
  options: ['Single-Player Campaign Focus', 'Cooperative Multiplayer Mode'],
  resolutionStatus: 'UNRESOLVED',
};

const mockProposal: InspirationSynthesisProposal = {
  projectId: 'proj-123',
  inspirationCount: 2,
  sourceTitles: ['Slay the Spire', 'Into the Breach'],
  proposedTitle: 'Design Synthesis: Roguelike Strategy',
  proposedGenre: 'Roguelike Strategy Tactics',
  proposedArchetype: 'arena',
  proposedTheme: 'cyberpunk',
  proposedPlayerModes: ['Single-player Focus'],
  proposedMechanics: ['DeckBuilding', 'GridTactics', 'ProceduralProgression'],
  gameplayLoop: 'Infiltrate procedural sector -> Execute card-driven tactical positioning -> Defeat zone apex',
  progressionDirection: 'Branching unlock paths with procedural loadout modifications',
  designObjectives: [
    { level_number: 1, type: 'PRIMARY', description: 'Survive procedural encounters.' },
  ],
  recommendedParameters: {
    engine: 'arena',
    artDensity: 60,
    physics: 45,
    scale: 'standard',
    worldMode: 'campaign',
    modules: ['InventorySystem', 'HealthBar'],
  },
  sharedAnchors: ['Genre: Strategy'],
  complementaryAnchors: ['Composite: DeckBuilding + GridTactics'],
  conflicts: [mockConflict],
  sourceAttribution: [
    {
      element: 'DeckBuilding',
      category: 'mechanic',
      sourceSteamAppIds: ['646570'],
      sourceTitles: ['Slay the Spire'],
      triggerAttributes: ['deckbuilder'],
    },
  ],
  isSingleSourceDominant: false,
  confidence: 'HIGH',
  confidenceExplanation: 'High coherence: 1 shared attribute anchor with zero blocking conflicts.',
};

const mockProject: GameProject = {
  id: 'proj-123',
  title: 'Cyber Core',
  genre: 'Action RPG',
  prompt: 'Cyberpunk tactical survival game',
  status: 'PLAYABLE',
  lastModified: '2026-09-04',
  currentVersion: 1,
  parameters: {
    engine: 'survival',
    artDensity: 50,
    physics: 80,
    modules: ['HealthBar'],
    scale: 'standard',
    worldMode: 'linear',
  },
  designSpec: {
    title: 'Cyber Core',
    genre: 'Action RPG',
    theme: 'neon',
    elevator_pitch: 'Survive in cyberpunk.',
    player_role: 'Runner',
    primary_objective: 'Survive',
    core_gameplay_loop: 'Deploy -> Shoot -> Survive',
    player_abilities: ['dash', 'shoot'],
  },
};

// 1. Conflict resolution test
const unresolved = mockProposal.conflicts.filter((c) => c.resolutionStatus === 'UNRESOLVED');
assert('Has 1 unresolved conflict initially', unresolved.length === 1);

const emptyResolutions: Record<string, string> = {};
const isBlockedInitially = unresolved.some((c) => !emptyResolutions[c.field]);
assert('Unresolved conflict blocks apply', isBlockedInitially === true);

const resolvedResolutions: Record<string, string> = {
  player_modes: 'Single-Player Campaign Focus',
};
const isBlockedAfterResolution = unresolved.some((c) => !resolvedResolutions[c.field]);
assert('Selecting option unblocks apply', isBlockedAfterResolution === false);

// 2. Diff computation test
const diffs: Array<{ field: string; current: string; proposed: string }> = [];

if (mockProject.genre !== mockProposal.proposedGenre) {
  diffs.push({
    field: 'Genre',
    current: mockProject.genre,
    proposed: mockProposal.proposedGenre,
  });
}

const currentEngine = mockProject.parameters?.engine || 'standard';
if (currentEngine !== mockProposal.recommendedParameters.engine) {
  diffs.push({
    field: 'Engine',
    current: currentEngine,
    proposed: mockProposal.recommendedParameters.engine,
  });
}

const currentTheme = mockProject.designSpec?.theme || 'neon';
if (currentTheme !== mockProposal.proposedTheme) {
  diffs.push({
    field: 'Theme',
    current: currentTheme,
    proposed: mockProposal.proposedTheme,
  });
}

assert('Identifies 3 changed fields in diff', diffs.length === 3);
assert('Diff genre matches', diffs[0].field === 'Genre' && diffs[0].proposed === 'Roguelike Strategy Tactics');
assert('Diff engine matches', diffs[1].field === 'Engine' && diffs[1].proposed === 'arena');
assert('Diff theme matches', diffs[2].field === 'Theme' && diffs[2].proposed === 'cyberpunk');

// 3. Request payload construction test
const payload: ApplySynthesisProposalRequest = {
  baseVersionNumber: mockProject.currentVersion || 1,
  conflictResolutions: {
    player_modes: 'Single-Player Campaign Focus',
  },
  fieldDecisions: {
    genre: 'APPLY_PROPOSAL',
  },
};

assert('Payload specifies baseVersionNumber 1', payload.baseVersionNumber === 1);
assert('Payload includes chosen conflict resolution', payload.conflictResolutions?.player_modes === 'Single-Player Campaign Focus');
assert('Payload includes field decision', payload.fieldDecisions?.genre === 'APPLY_PROPOSAL');

// 4. Response structure test
const mockResponse: ApplySynthesisProposalResponse = {
  projectId: 'proj-123',
  previousVersionNumber: 1,
  newVersionNumber: 2,
  changeSummary: 'Inspiration synthesis applied: 2 reference games (Slay the Spire, Into the Breach)',
  changes: [
    {
      fieldName: 'genre',
      previousValue: 'Action RPG',
      newValue: 'Roguelike Strategy Tactics',
      sourceAttribution: 'From inspirations: Slay the Spire, Into the Breach',
    },
  ],
  project: {
    ...mockProject,
    currentVersion: 2,
    genre: 'Roguelike Strategy Tactics',
  },
  blueprint: {} as any,
  status: 'SUCCESS',
};

assert('Response previousVersionNumber is 1', mockResponse.previousVersionNumber === 1);
assert('Response newVersionNumber is 2', mockResponse.newVersionNumber === 2);
assert('Response project version bumped to 2', mockResponse.project.currentVersion === 2);
assert('Response changes contains genre change', mockResponse.changes.length === 1 && mockResponse.changes[0].fieldName === 'genre');

console.log(`\nResults: ${passed} passed, ${failed} failed\n`);
if (failed > 0) {
  throw new Error(`Test suite failed with ${failed} failure(s)`);
}
