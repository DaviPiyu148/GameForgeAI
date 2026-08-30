/**
 * Deterministic procedural cover configuration for GameForge project cards.
 *
 * Produces a stable visual identity for each project based on its authoritative
 * identity fields (id, engine, world_mode, genre). The same project always gets
 * the same cover across renders, reloads, and duplicates (a duplicate gets its
 * own identity from its new UUID).
 *
 * Design constraints:
 *   - No network calls, no Math.random(), no Date.now(), no render-order index.
 *   - Falls back gracefully for any missing/unknown field values.
 *   - Uses only Material Symbols already loaded by the app (subset: gaming-themed).
 */

import type { GameProject } from '../types';

export interface CoverConfig {
  /** CSS gradient string, e.g. "linear-gradient(135deg, #0f1a2e 0%, #1a3a5c 100%)" */
  gradient: string;
  /** Material Symbol icon name */
  icon: string;
  /** Human-readable genre/mode label for the cover */
  label: string;
  /** Accent CSS color for the icon */
  accentColor: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Palette table (curated, fixed, never random-selected)
// Each entry: [gradientFrom, gradientTo, accentColor]
// ─────────────────────────────────────────────────────────────────────────────
const PALETTES: [string, string, string][] = [
  ['#0d1b2a', '#1b3a5c', '#4CE0D2'],  // Deep ocean / cyan (GameForge primary)
  ['#1a0d2e', '#3d1a5c', '#c084fc'],  // Deep purple / violet
  ['#2a0d0d', '#5c1a1a', '#f87171'],  // Deep crimson / red
  ['#0d2a1a', '#1a5c3d', '#34d399'],  // Deep forest / emerald
  ['#2a1a0d', '#5c3d1a', '#fbbf24'],  // Deep ember / amber
  ['#0d2a2a', '#1a5c5c', '#22d3ee'],  // Deep teal / sky
  ['#1a2a0d', '#3d5c1a', '#a3e635'],  // Deep olive / lime
  ['#2a0d1a', '#5c1a3d', '#f472b6'],  // Deep rose / pink
  ['#0d1a2a', '#1a3d5c', '#60a5fa'],  // Midnight blue / azure
  ['#1a1a0d', '#5c5c1a', '#e2cb72'],  // Deep gold / khaki
];

// Engine → icon mapping. Values must be Material Symbols names present in the app's font.
const ENGINE_ICONS: Record<string, string> = {
  'Top-Down Action':    'sports_martial_arts',
  'Arena Survival':     'crisis_alert',
  '2D Platformer':      'directions_run',
  'Data Collector':     'hub',
};

// World-mode → icon override (takes priority over engine for Open World)
const WORLD_MODE_ICONS: Record<string, string> = {
  open_world: 'explore',
  campaign:   'military_tech',
  linear:     '',           // empty → fall through to engine icon
};

// Genre keyword → icon heuristics (highest-level override)
const GENRE_ICONS: [RegExp, string][] = [
  [/racing|race|speed|drift/i,          'speed'],
  [/rpg|role.?play|fantasy|quest/i,     'auto_stories'],
  [/strategy|tactical|tower|defense/i,  'strategy'],
  [/horror|survival|zombie|escape/i,    'skull'],
  [/puzzle|match|logic|brain/i,         'extension'],
  [/sport|soccer|football|basket/i,     'sports_soccer'],
  [/shoot|shooter|fps|gun/i,            'target'],
  [/platform|jump|run|obstacle/i,       'directions_run'],
  [/collect|gather|farm|resource/i,     'grocery'],
  [/stealth|spy|infiltrat/i,            'visibility_off'],
  [/space|galaxy|star|cosmic/i,         'rocket_launch'],
  [/city|build|sim|simulat/i,           'location_city'],
  [/dungeon|rogue|crawl/i,              'castle'],
  [/rhythm|music|beat/i,                'music_note'],
  [/open.?world|sandbox|free.?roam/i,   'explore'],
];

/**
 * Stable integer hash of a string (djb2 variant, always non-negative).
 */
function stableHash(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h) ^ s.charCodeAt(i);
  }
  return Math.abs(h);
}

/**
 * Select a palette deterministically from the project's UUID.
 * The UUID is the most stable identifier — same project = same palette.
 */
function pickPalette(id: string): [string, string, string] {
  return PALETTES[stableHash(id) % PALETTES.length];
}

/**
 * Derive the best icon for a project based on genre → world_mode → engine priority.
 */
function pickIcon(project: GameProject): string {
  // 1. Genre heuristic (highest priority)
  const genreStr = [project.genre, project.title].filter(Boolean).join(' ');
  for (const [pattern, icon] of GENRE_ICONS) {
    if (pattern.test(genreStr)) return icon;
  }

  // 2. World mode (catches "open_world" and "campaign" regardless of engine)
  const worldMode = project.parameters?.world_mode ?? project.parameters?.worldMode ?? '';
  const worldIcon = WORLD_MODE_ICONS[worldMode];
  if (worldIcon) return worldIcon;

  // 3. Engine
  const engine = project.parameters?.engine ?? '';
  if (ENGINE_ICONS[engine]) return ENGINE_ICONS[engine];

  // 4. Fallback
  return 'videogame_asset';
}

/**
 * Derive a concise display label for the cover from world_mode / scale.
 */
function pickLabel(project: GameProject): string {
  const worldMode = project.parameters?.world_mode ?? project.parameters?.worldMode ?? '';
  const scale = project.parameters?.scale ?? '';

  if (worldMode === 'open_world') return 'OPEN WORLD';
  if (worldMode === 'campaign')   return 'CAMPAIGN';
  if (scale === 'campaign')       return 'EXPANDED';
  if (scale === 'prototype')      return 'PROTOTYPE';
  return project.genre ?? 'GAME';
}

/**
 * Generate a deterministic CoverConfig for a GameProject.
 * Safe for any project shape — missing fields produce valid fallback output.
 */
export function generateProjectCover(project: GameProject): CoverConfig {
  const [from, to, accentColor] = pickPalette(project.id ?? 'fallback');
  const gradient = `linear-gradient(135deg, ${from} 0%, ${to} 100%)`;
  const icon = pickIcon(project);
  const label = pickLabel(project);
  return { gradient, icon, label, accentColor };
}
