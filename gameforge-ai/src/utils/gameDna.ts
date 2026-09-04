/**
 * gameDna.ts — Pure, deterministic Game DNA extraction utilities.
 *
 * Step 1 of Discovery -> Inspiration -> Studio.
 *
 * RULES:
 * - Only reads fields that actually exist on GameDiscoveryItem.
 * - No LLM calls. No free-form inference.
 * - Returns only non-empty sections; callers must not render empty sections.
 */

import type { GameDiscoveryItem, GameProject } from '../types';

export interface GameDNA {
  /** Normalised genres, ready to display. Empty array if none. */
  genres: string[];
  /** Player modes (e.g. 'Single-player', 'Multi-player'). */
  playerModes: string[];
  /** Selected display tags (up to 10). */
  tags: string[];
}

/**
 * Extracts structured DNA from a game record.
 * Only fields that are genuinely available and non-empty are populated.
 */
export function extractGameDNA(game: GameDiscoveryItem): GameDNA {
  const genres = (game.display_genres ?? game.genres ?? []).filter(Boolean);
  const playerModes = (game.player_modes ?? []).filter(Boolean);
  const tags = (game.display_tags ?? game.tags ?? []).slice(0, 10).filter(Boolean);

  return { genres, playerModes, tags };
}

/**
 * ProjectAlignment - only intersection of verified game and project data.
 * Returns an array of matched genre strings (no free-form sentences).
 * Empty array if there is no overlap.
 *
 * Comparison is case-insensitive.
 */
export function computeProjectAlignment(
  gameDna: GameDNA,
  activeProject: GameProject | null
): string[] {
  if (!activeProject) return [];

  // Project has a single `genre` field (e.g. "Top-Down Action")
  const projectGenreLower = (activeProject.genre ?? '').toLowerCase().trim();
  if (!projectGenreLower) return [];

  const matched: string[] = [];

  for (const g of gameDna.genres) {
    const gLower = g.toLowerCase().trim();
    // Match if the project genre contains the game genre token or vice-versa
    if (projectGenreLower.includes(gLower) || gLower.includes(projectGenreLower)) {
      matched.push(g);
    }
  }

  return matched;
}
