/**
 * Unit tests for gameDna utilities.
 *
 * Tests Step 1: Discovery -> Inspiration -> Studio
 *
 * Run with: npx tsx src/utils/__tests__/gameDna.test.ts
 */

import { extractGameDNA, computeProjectAlignment } from '../gameDna';
import type { GameDiscoveryItem } from '../../types';
import type { GameProject } from '../../types';

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

function makeGame(overrides: Partial<GameDiscoveryItem> = {}): GameDiscoveryItem {
  return {
    id: 'g-1',
    external_id: '570',
    source: 'steam',
    title: 'Test Game',
    description: 'A test game.',
    genres: ['Action', 'RPG'],
    tags: ['tag1', 'tag2'],
    player_modes: ['Single-player', 'Multi-player'],
    platforms: ['PC'],
    release_year: 2023,
    is_free: false,
    ...overrides,
  };
}

function makeProject(overrides: Partial<GameProject> = {}): GameProject {
  return {
    id: 'proj-1',
    title: 'My RPG Project',
    genre: 'RPG',
    status: 'PLAYABLE',
    lastModified: '2026-09-01T00:00:00Z',
    parameters: {
      engine: 'Top-Down Action',
      artDensity: 50,
      physics: 80,
      modules: [],
    },
    prompt: 'a cool rpg',
    ...overrides,
  };
}

console.log('\n--- Test Suite: extractGameDNA ---');

// Test 1: Uses display_genres over genres when available
{
  const game = makeGame({
    display_genres: ['Strategy', 'Roguelike'],
    genres: ['Action', 'RPG'],
  });
  const dna = extractGameDNA(game);
  assert(
    'Prefers display_genres over genres',
    dna.genres[0] === 'Strategy' && dna.genres[1] === 'Roguelike',
    `Got: ${JSON.stringify(dna.genres)}`
  );
}

// Test 2: Falls back to genres when display_genres is absent
{
  const game = makeGame({ display_genres: undefined, genres: ['Puzzle', 'Adventure'] });
  const dna = extractGameDNA(game);
  assert(
    'Falls back to genres when display_genres absent',
    dna.genres[0] === 'Puzzle',
    `Got: ${JSON.stringify(dna.genres)}`
  );
}

// Test 3: player_modes extracted
{
  const game = makeGame({ player_modes: ['Single-player', 'Co-op'] });
  const dna = extractGameDNA(game);
  assert(
    'Extracts player_modes correctly',
    dna.playerModes.includes('Single-player') && dna.playerModes.includes('Co-op'),
    `Got: ${JSON.stringify(dna.playerModes)}`
  );
}

// Test 4: Uses display_tags over tags
{
  const game = makeGame({
    display_tags: ['Deckbuilder', 'Turn-Based'],
    tags: ['old-tag'],
  });
  const dna = extractGameDNA(game);
  assert(
    'Prefers display_tags over tags',
    dna.tags[0] === 'Deckbuilder',
    `Got: ${JSON.stringify(dna.tags)}`
  );
}

// Test 5: Tags capped at 10
{
  const game = makeGame({
    display_tags: Array.from({ length: 20 }, (_, i) => `tag${i}`),
  });
  const dna = extractGameDNA(game);
  assert(
    'Tags capped at 10',
    dna.tags.length === 10,
    `Got length: ${dna.tags.length}`
  );
}

// Test 6: Empty game data produces empty arrays
{
  const game = makeGame({ genres: [], player_modes: [], tags: [] });
  const dna = extractGameDNA(game);
  assert(
    'All empty arrays when game has no metadata',
    dna.genres.length === 0 && dna.playerModes.length === 0 && dna.tags.length === 0,
    `Got: ${JSON.stringify(dna)}`
  );
}

// Test 7: Filters out empty string entries
{
  const game = makeGame({ genres: ['', 'Action', ''] });
  const dna = extractGameDNA(game);
  assert(
    'Filters empty string entries from genres',
    dna.genres.length === 1 && dna.genres[0] === 'Action',
    `Got: ${JSON.stringify(dna.genres)}`
  );
}

console.log('\n--- Test Suite: computeProjectAlignment ---');

// Test 8: Exact genre match (case-insensitive)
{
  const game = makeGame({ genres: ['RPG', 'Adventure'] });
  const dna = extractGameDNA(game);
  const project = makeProject({ genre: 'RPG' });
  const aligned = computeProjectAlignment(dna, project);
  assert(
    'Detects exact genre match',
    aligned.includes('RPG'),
    `Got: ${JSON.stringify(aligned)}`
  );
}

// Test 9: No match when genres differ
{
  const game = makeGame({ genres: ['Puzzle', 'Platformer'] });
  const dna = extractGameDNA(game);
  const project = makeProject({ genre: 'Top-Down Shooter' });
  const aligned = computeProjectAlignment(dna, project);
  assert(
    'Returns empty array when no genre intersection',
    aligned.length === 0,
    `Got: ${JSON.stringify(aligned)}`
  );
}

// Test 10: Returns empty array when activeProject is null
{
  const game = makeGame({ genres: ['RPG'] });
  const dna = extractGameDNA(game);
  const aligned = computeProjectAlignment(dna, null);
  assert(
    'Returns empty array for null activeProject',
    aligned.length === 0,
    `Got: ${JSON.stringify(aligned)}`
  );
}

// Test 11: Substring match (project genre "Top-Down Action" should not match game genre "RPG")
{
  const game = makeGame({ genres: ['RPG', 'Strategy'] });
  const dna = extractGameDNA(game);
  const project = makeProject({ genre: 'Top-Down Action' });
  const aligned = computeProjectAlignment(dna, project);
  assert(
    'No false match: Top-Down Action vs RPG/Strategy',
    aligned.length === 0,
    `Got: ${JSON.stringify(aligned)}`
  );
}

// Test 12: Save and Inspire are independent — extractGameDNA does not mutate inputs
{
  const game = makeGame({ genres: ['Action'] });
  const dnaBefore = { genres: [...game.genres] };
  extractGameDNA(game);
  assert(
    'extractGameDNA does not mutate original game.genres',
    JSON.stringify(game.genres) === JSON.stringify(dnaBefore.genres),
    `Genres after call: ${JSON.stringify(game.genres)}`
  );
}

// Test 13: Different games produce fresh DNA (no shared state)
{
  const gameA = makeGame({ genres: ['Platformer'] });
  const gameB = makeGame({ genres: ['Shooter'] });
  const dnaA = extractGameDNA(gameA);
  const dnaB = extractGameDNA(gameB);
  assert(
    'Different games produce independent DNA (game switching)',
    dnaA.genres[0] === 'Platformer' && dnaB.genres[0] === 'Shooter',
    `A: ${JSON.stringify(dnaA.genres)}, B: ${JSON.stringify(dnaB.genres)}`
  );
}

// Test 14: Project with empty genre produces empty alignment
{
  const game = makeGame({ genres: ['RPG'] });
  const dna = extractGameDNA(game);
  const project = makeProject({ genre: '' });
  const aligned = computeProjectAlignment(dna, project);
  assert(
    'Empty project genre -> empty alignment',
    aligned.length === 0,
    `Got: ${JSON.stringify(aligned)}`
  );
}

console.log(`\nResults: ${passed} passed, ${failed} failed`);
if (failed > 0) (globalThis as any).process.exit(1);

