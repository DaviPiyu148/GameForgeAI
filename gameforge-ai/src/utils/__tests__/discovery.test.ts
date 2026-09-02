/**
 * Unit tests for buildDiscoverySeed pure helper (Creator Loop V1).
 *
 * Run with: npx tsx src/utils/__tests__/discovery.test.ts
 */

import { buildDiscoverySeed } from '../discovery';
import type { GameProject } from '../../types';
import type { GameDesignSpec } from '../../runtime/types';

let passed = 0;
let failed = 0;

function assert(label: string, condition: boolean, details?: string) {
  if (condition) {
    console.log(`  ✓ ${label}`);
    passed++;
  } else {
    console.error(`  ✗ ${label}`);
    if (details) console.error(`      ${details}`);
    failed++;
  }
}

function createBaseProject(overrides: Partial<GameProject> = {}): GameProject {
  return {
    id: 'proj-123',
    title: 'Cyber Heist',
    genre: 'Top-Down Action',
    status: 'PLAYABLE',
    lastModified: '2026-09-02T12:00:00Z',
    parameters: {
      engine: 'Top-Down Action',
      artDensity: 50,
      physics: 80,
      modules: ['Procedural Generation'],
    },
    prompt: 'A neon cyberpunk stealth heist game with hacking and security guards.',
    ...overrides,
  };
}

console.log('\n--- Test Suite: buildDiscoverySeed ---');

// Test 1: Full designSpec present with genre, theme, and core loop
{
  const spec: GameDesignSpec = {
    title: 'Neon Infiltration',
    elevator_pitch: 'Infiltrate megacorps.',
    genre: 'Stealth Action',
    theme: 'cyberpunk',
    visual_style: 'Dark Neon',
    camera: 'top_down',
    core_gameplay_loop: 'Sneak past cameras, hack terminals, escape with loot.',
    player_role: 'Hacker Operative',
    primary_objective: 'Infiltrate vault',
    secondary_objectives: ['No alerts'],
    player_abilities: ['Dash', 'Hack'],
    enemy_archetypes: [{ name: 'Guard' }],
    hazards: [{ name: 'Laser Grid' }],
    collectibles: [{ name: 'Data Chip' }],
    progression: { style: 'linear' },
    difficulty_curve: 'escalating',
    win_conditions: ['Reach extraction'],
    loss_conditions: ['Health 0'],
    level_structure: { count: 3 },
    estimated_session_length: '5-10 minutes',
    selected_modules: ['Enhanced NPC Behavior'],
    rationale: ['High tension stealth loop.'],
  };

  const project = createBaseProject({ designSpec: spec });
  const seed = buildDiscoverySeed(project);
  assert(
    'Uses genre, theme, and core_gameplay_loop when designSpec is complete',
    seed === 'Stealth Action cyberpunk Sneak past cameras, hack terminals, escape with loot.',
    `Got: "${seed}"`
  );
}

// Test 2: designSpec present with genre and theme, but missing/empty core_gameplay_loop
{
  const spec: GameDesignSpec = {
    title: 'Neon Infiltration',
    elevator_pitch: '',
    genre: 'Cozy Farming',
    theme: 'dungeon',
    core_gameplay_loop: '',
    player_role: '',
    primary_objective: '',
  };

  const project = createBaseProject({ designSpec: spec });
  const seed = buildDiscoverySeed(project);
  assert(
    'Handles empty core_gameplay_loop cleanly without extra spaces',
    seed === 'Cozy Farming dungeon',
    `Got: "${seed}"`
  );
}

// Test 3: designSpec missing theme/genre fallback to prompt
{
  const project = createBaseProject({
    prompt: 'A retro platformer with bouncy mushrooms and crystal caves.',
    designSpec: {
      title: 'Cave Jumper',
      elevator_pitch: '',
      genre: '',
      theme: 'retro_arcade',
      core_gameplay_loop: 'Jump and collect crystals',
      player_role: '',
      primary_objective: '',
    },
  });

  const seed = buildDiscoverySeed(project);
  assert(
    'Falls back to prompt when designSpec.genre is empty',
    seed === 'A retro platformer with bouncy mushrooms and crystal caves.',
    `Got: "${seed}"`
  );
}

// Test 4: designSpec is undefined
{
  const project = createBaseProject({
    prompt: 'Space exploration dogfighting simulator with trading.',
    designSpec: undefined,
  });

  const seed = buildDiscoverySeed(project);
  assert(
    'Falls back to prompt when designSpec is undefined',
    seed === 'Space exploration dogfighting simulator with trading.',
    `Got: "${seed}"`
  );
}

// Test 5: Length truncation for very long designSpec strings (200 char bound)
{
  const longLoop = 'A'.repeat(300);
  const spec: GameDesignSpec = {
    title: 'Long Spec',
    elevator_pitch: '',
    genre: 'RPG',
    theme: 'space',
    core_gameplay_loop: longLoop,
    player_role: '',
    primary_objective: '',
  };

  const project = createBaseProject({ designSpec: spec });
  const seed = buildDiscoverySeed(project);
  assert(
    'Truncates long designSpec composite to 200 characters max',
    seed.length <= 200 && seed.startsWith('RPG space AAAA'),
    `Length: ${seed.length}, seed: "${seed}"`
  );
}

// Test 6: Length truncation for very long prompt fallback (150 char bound)
{
  const longPrompt = 'B'.repeat(300);
  const project = createBaseProject({
    prompt: longPrompt,
    designSpec: undefined,
  });

  const seed = buildDiscoverySeed(project);
  assert(
    'Truncates long prompt fallback to 150 characters max',
    seed.length === 150 && seed === 'B'.repeat(150),
    `Length: ${seed.length}`
  );
}

// Test 7: Handles completely empty prompt with no designSpec
{
  const project = createBaseProject({
    prompt: '',
    designSpec: undefined,
  });

  const seed = buildDiscoverySeed(project);
  assert(
    'Returns empty string without error on empty project prompt',
    seed === '',
    `Got: "${seed}"`
  );
}

console.log(`\nResults: ${passed} passed, ${failed} failed`);
