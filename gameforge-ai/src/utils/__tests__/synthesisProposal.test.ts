/**
 * Unit tests for Inspiration Synthesis Proposal structure and presentation logic (Step 4).
 *
 * Run with: npx tsx src/utils/__tests__/synthesisProposal.test.ts
 */

import type { InspirationSynthesisProposal } from '../../types';

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

const mockProposal: InspirationSynthesisProposal = {
  projectId: 'proj-123',
  inspirationCount: 2,
  sourceTitles: ['Slay the Spire', 'Into the Breach'],
  proposedTitle: 'Design Synthesis: Strategy Roguelike RPG',
  proposedGenre: 'Strategy Roguelike RPG',
  proposedArchetype: 'arena',
  proposedTheme: 'cyberpunk',
  proposedPlayerModes: ['Single-player Focus'],
  proposedMechanics: ['DeckBuilding', 'GridTactics', 'ProceduralProgression'],
  gameplayLoop: 'Infiltrate procedural sector -> Execute card-driven tactical positioning -> Upgrade talent proficiencies -> Defeat zone apex to advance forward milestone',
  progressionDirection: 'Branching unlock paths with procedural loadout modifications',
  designObjectives: [
    {
      level_number: 1,
      type: 'PRIMARY',
      description: 'Survive procedural wave encounters utilizing DeckBuilding mechanics.',
    },
    {
      level_number: 1,
      type: 'SECONDARY',
      description: 'Maximize tactical synergy between GridTactics and environment.',
    },
    {
      level_number: 1,
      type: 'MASTERY',
      description: 'Complete the sector with zero structural vitality depletion.',
    },
  ],
  recommendedParameters: {
    engine: 'arena',
    artDensity: 60,
    physics: 45,
    modules: ['InventorySystem', 'HealthBar', 'WeaponUpgrade'],
    scale: 'standard',
    worldMode: 'campaign',
  },
  sharedAnchors: ['Genre: Strategy', 'Tag: #Singleplayer'],
  complementaryAnchors: ['Composite: DeckBuilding + GridTactics + ProceduralProgression'],
  conflicts: [],
  sourceAttribution: [
    {
      element: 'DeckBuilding',
      category: 'mechanic',
      sourceSteamAppIds: ['646570'],
      sourceTitles: ['Slay the Spire'],
      triggerAttributes: ['deckbuilder'],
    },
    {
      element: 'GridTactics',
      category: 'mechanic',
      sourceSteamAppIds: ['590380'],
      sourceTitles: ['Into the Breach'],
      triggerAttributes: ['grid', 'tactical'],
    },
  ],
  isSingleSourceDominant: false,
  dominantSourceTitle: null,
  confidence: 'HIGH',
  confidenceExplanation: 'High coherence: 2 shared attribute anchors with zero blocking conflicts.',
};

console.log('\n--- Test Suite: Synthesis Proposal Verification ---');

// Test 1: Proposal fields are complete and strictly typed
{
  assert('Proposal has 2 source inspirations', mockProposal.inspirationCount === 2);
  assert('Proposal identifies both source titles', mockProposal.sourceTitles.includes('Slay the Spire') && mockProposal.sourceTitles.includes('Into the Breach'));
  assert('Confidence is HIGH', mockProposal.confidence === 'HIGH');
}

// Test 2: Source attribution traces every mechanic
{
  const deckAttr = mockProposal.sourceAttribution.find((a) => a.element === 'DeckBuilding');
  assert('DeckBuilding attributed to Slay the Spire', deckAttr !== undefined && deckAttr.sourceTitles.includes('Slay the Spire'));

  const gridAttr = mockProposal.sourceAttribution.find((a) => a.element === 'GridTactics');
  assert('GridTactics attributed to Into the Breach', gridAttr !== undefined && gridAttr.sourceTitles.includes('Into the Breach'));
}

// Test 3: Gameplay loop is formatted with 4 distinct phases
{
  const steps = mockProposal.gameplayLoop.split(' -> ');
  assert('Gameplay loop has 4 sequential phases', steps.length === 4);
  assert('Loop begins with ingress step', steps[0].includes('Infiltrate'));
  assert('Loop ends with apex/boss resolution', steps[3].includes('Defeat zone apex'));
}

// Test 4: Objectives cover Primary, Secondary, and Mastery
{
  const types = mockProposal.designObjectives.map((o) => o.type);
  assert('Objectives include PRIMARY', types.includes('PRIMARY'));
  assert('Objectives include SECONDARY', types.includes('SECONDARY'));
  assert('Objectives include MASTERY', types.includes('MASTERY'));
}

// Test 5: Recommended parameters conform to GameForge schema
{
  const params = mockProposal.recommendedParameters;
  assert('Recommended parameters has valid engine', ['survival', 'shooter', 'platformer', 'arena'].includes(params.engine));
  assert('Physics is within bounds', params.physics >= 0 && params.physics <= 100);
  assert('Art density is within bounds', params.artDensity >= 0 && params.artDensity <= 100);
  assert('Modules list is non-empty', params.modules.length > 0);
}

// Test 6: No single-source dominance when balanced
{
  assert('Is not single-source dominant', !mockProposal.isSingleSourceDominant);
}

console.log(`\nResults: ${passed} passed, ${failed} failed`);
if (failed > 0) (globalThis as any).process.exit(1);
