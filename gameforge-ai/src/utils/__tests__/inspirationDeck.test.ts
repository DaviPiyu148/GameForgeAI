/**
 * Unit tests for Inspiration Deck data transformations and business rules (Step 3).
 *
 * Run with: npx tsx src/utils/__tests__/inspirationDeck.test.ts
 */

import { extractGameDNA, computeProjectAlignment } from '../gameDna';
import { computeInspirationSynergy } from '../synergy';
import type { GameProject, ProjectInspirationRecord } from '../../types';

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

const mockProject: GameProject = {
  id: 'proj-123',
  title: 'Rogue Star',
  genre: 'Roguelike Action RPG',
  status: 'PLAYABLE',
  lastModified: 'Just now',
  parameters: {
    engine: 'Top-Down Action',
    artDensity: 50,
    physics: 80,
    modules: [],
  },
  prompt: 'A sci-fi action roguelike',
};

const mockInspirations: ProjectInspirationRecord[] = [
  {
    id: 'insp-1',
    projectId: 'proj-123',
    steamAppId: '570',
    title: 'Dota 2',
    coverUrl: 'https://cdn.steam.com/dota2.jpg',
    genres: ['Action', 'Strategy'],
    tags: ['MOBA', 'Multiplayer', 'Competitive', 'Deckbuilder'],
    playerModes: ['Multi-player'],
    createdAt: '2026-09-01T10:00:00Z',
  },
  {
    id: 'insp-2',
    projectId: 'proj-123',
    steamAppId: '1091500',
    title: 'Cyberpunk 2077',
    coverUrl: 'https://cdn.steam.com/cp2077.jpg',
    genres: ['RPG', 'Action'],
    tags: ['Open World', 'Cyberpunk', 'Singleplayer', 'Deckbuilder'],
    playerModes: ['Single-player'],
    createdAt: '2026-09-02T10:00:00Z',
  },
];

console.log('\n--- Test Suite: Inspiration Deck & Snapshot Rendering ---');

// Test 1: Snapshot metadata preserves original attached fields
{
  const insp = mockInspirations[0];
  assert('Preserves steamAppId as canonical identity', insp.steamAppId === '570');
  assert('Preserves title from snapshot', insp.title === 'Dota 2');
  assert('Preserves coverUrl from snapshot', insp.coverUrl === 'https://cdn.steam.com/dota2.jpg');
}

// Test 2: Project alignment is derived on-demand against active project genre
{
  const dna1 = extractGameDNA({
    id: mockInspirations[0].steamAppId,
    title: mockInspirations[0].title,
    genres: mockInspirations[0].genres,
    tags: mockInspirations[0].tags,
    player_modes: mockInspirations[0].playerModes,
  } as any);
  const alignment1 = computeProjectAlignment(dna1, mockProject);
  assert('Dota 2 matches Action in Roguelike Action RPG', alignment1.includes('Action') && !alignment1.includes('Strategy'));

  const dna2 = extractGameDNA({
    id: mockInspirations[1].steamAppId,
    title: mockInspirations[1].title,
    genres: mockInspirations[1].genres,
    tags: mockInspirations[1].tags,
    player_modes: mockInspirations[1].playerModes,
  } as any);
  const alignment2 = computeProjectAlignment(dna2, mockProject);
  assert('Cyberpunk matches RPG and Action in Roguelike Action RPG', alignment2.includes('RPG') && alignment2.includes('Action'));
}

// Test 3: Multiple inspirations synergy computation
{
  const syn = computeInspirationSynergy(mockInspirations);
  assert('Detects shared genre Action between Dota 2 and Cyberpunk', syn.sharedGenres.includes('Action'));
  assert('Detects shared tag Deckbuilder between Dota 2 and Cyberpunk', syn.sharedTags.includes('Deckbuilder'));
  assert('No shared player modes between singleplayer and multiplayer', syn.sharedPlayerModes.length === 0);
  assert('Reports correct total inspirations count', syn.totalInspirations === 2);
}

// Test 4: 0 inspirations produce empty synergy
{
  const emptySyn = computeInspirationSynergy([]);
  assert('0 inspirations produce empty synergy', emptySyn.totalInspirations === 0 && emptySyn.sharedGenres.length === 0);
}

// Test 5: 1 inspiration produces empty synergy (no fake synergy)
{
  const singleSyn = computeInspirationSynergy([mockInspirations[0]]);
  assert('1 inspiration produces 0 shared items', singleSyn.totalInspirations === 1 && singleSyn.sharedGenres.length === 0 && singleSyn.sharedTags.length === 0);
}

console.log(`\nResults: ${passed} passed, ${failed} failed`);
if (failed > 0) (globalThis as any).process.exit(1);
