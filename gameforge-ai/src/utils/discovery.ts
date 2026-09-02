import type { GameProject } from '../types';

/**
 * Constructs a semantic search seed for Discovery from a GameProject.
 * Prefers designSpec genre + theme + core_gameplay_loop when available
 * (semantically accurate after Remix iterations).
 * Falls back to the original build prompt when designSpec is absent.
 */
export function buildDiscoverySeed(project: GameProject): string {
  const { designSpec, prompt } = project;
  if (designSpec?.genre && designSpec?.theme) {
    const parts = [
      designSpec.genre,
      designSpec.theme,
      designSpec.core_gameplay_loop,
    ].filter(Boolean);
    return parts.join(' ').trim().substring(0, 200);
  }
  // Documented fallback: no designSpec available (e.g. pre-G12 or missing spec)
  return (prompt || '').trim().substring(0, 150);
}
