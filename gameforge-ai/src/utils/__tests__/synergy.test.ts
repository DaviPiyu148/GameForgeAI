/**
 * Unit tests for synergy.ts deterministic calculations (Step 3).
 *
 * Run with: npx tsx src/utils/__tests__/synergy.test.ts
 */

import { computeInspirationSynergy } from '../synergy';
import type { ProjectInspirationRecord } from '../../types';

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

function makeInspiration(overrides: Partial<ProjectInspirationRecord> = {}): ProjectInspirationRecord {
  return {
    id: 'insp-1',
    projectId: 'proj-1',
    steamAppId: '100',
    title: 'Game A',
    coverUrl: 'https://cdn.example.com/cover.jpg',
    genres: ['Action', 'RPG'],
    tags: ['Roguelike', 'Singleplayer', 'Pixel Graphics'],
    playerModes: ['Single-player'],
    createdAt: '2026-09-01T12:00:00Z',
    ...overrides,
  };
}

console.log('\n--- Test Suite: computeInspirationSynergy ---');

// Test 1: Empty input returns empty collections
{
  const result = computeInspirationSynergy([]);
  assert('Empty array returns empty synergy', result.sharedGenres.length === 0 && result.sharedTags.length === 0 && result.totalInspirations === 0);
}

// Test 2: Single inspiration returns empty collections (no synergy fabricated)
{
  const game = makeInspiration({ genres: ['Action', 'RPG'] });
  const result = computeInspirationSynergy([game]);
  assert('Single inspiration has 0 shared items', result.sharedGenres.length === 0 && result.sharedTags.length === 0 && result.totalInspirations === 1);
}

// Test 3: 2 games with shared genre detected
{
  const g1 = makeInspiration({ steamAppId: '1', genres: ['Action', 'Strategy'] });
  const g2 = makeInspiration({ steamAppId: '2', genres: ['Strategy', 'Puzzle'] });
  const result = computeInspirationSynergy([g1, g2]);
  assert('Identifies shared genre Strategy', result.sharedGenres.includes('Strategy') && result.sharedGenres.length === 1);
}

// Test 4: Case-insensitive genre matching
{
  const g1 = makeInspiration({ steamAppId: '1', genres: ['roguelike'] });
  const g2 = makeInspiration({ steamAppId: '2', genres: ['Roguelike'] });
  const result = computeInspirationSynergy([g1, g2]);
  assert('Matches genres case-insensitively', result.sharedGenres.length === 1 && result.sharedGenres[0].toLowerCase() === 'roguelike');
}

// Test 5: Shared tags across 3 games
{
  const g1 = makeInspiration({ steamAppId: '1', tags: ['Deckbuilder', 'Turn-Based', '2D'] });
  const g2 = makeInspiration({ steamAppId: '2', tags: ['Deckbuilder', 'Sci-Fi'] });
  const g3 = makeInspiration({ steamAppId: '3', tags: ['Turn-Based', 'Deckbuilder', 'Indie'] });
  const result = computeInspirationSynergy([g1, g2, g3]);
  assert('Finds Deckbuilder in 3 games and Turn-Based in 2 games', result.sharedTags.includes('Deckbuilder') && result.sharedTags.includes('Turn-Based') && !result.sharedTags.includes('Sci-Fi'));
}

// Test 6: Shared player modes
{
  const g1 = makeInspiration({ steamAppId: '1', playerModes: ['Single-player', 'Co-op'] });
  const g2 = makeInspiration({ steamAppId: '2', playerModes: ['Multi-player', 'Co-op'] });
  const result = computeInspirationSynergy([g1, g2]);
  assert('Identifies shared Co-op mode', result.sharedPlayerModes.includes('Co-op') && result.sharedPlayerModes.length === 1);
}

// Test 7: Disjoint games produce zero false synergy
{
  const g1 = makeInspiration({ steamAppId: '1', genres: ['Racing'], tags: ['Cars'], playerModes: ['VR'] });
  const g2 = makeInspiration({ steamAppId: '2', genres: ['Cooking'], tags: ['Food'], playerModes: ['Mobile'] });
  const result = computeInspirationSynergy([g1, g2]);
  assert('Disjoint metadata produces no shared items', result.sharedGenres.length === 0 && result.sharedTags.length === 0 && result.sharedPlayerModes.length === 0);
}

// Test 8: Does not duplicate tags if game record contains internal duplicates
{
  const g1 = makeInspiration({ steamAppId: '1', tags: ['Action', 'Action', 'Action'] });
  const g2 = makeInspiration({ steamAppId: '2', tags: ['Puzzle'] });
  const result = computeInspirationSynergy([g1, g2]);
  assert('Internal duplicate within 1 game does not trigger shared threshold', result.sharedTags.length === 0);
}

console.log(`\nResults: ${passed} passed, ${failed} failed`);
if (failed > 0) (globalThis as any).process.exit(1);
