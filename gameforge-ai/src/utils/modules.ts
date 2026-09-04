/**
 * Canonical Builder Logic Modules and Normalization.
 *
 * GameForge AI supports exactly four canonical engine logic modules:
 * 1. Procedural Generation
 * 2. Enhanced NPC Behavior
 * 3. Combat & Dash Mobility
 * 4. Resource & Score Economy
 *
 * Any granular mechanics returned by Discovery or legacy drafts
 * (e.g. InventorySystem, ScoreTracker, ItemMagnet, WeaponUpgrade)
 * must be mapped and normalized into these canonical modules.
 */

export const CANONICAL_BUILDER_MODULES = [
  'Procedural Generation',
  'Enhanced NPC Behavior',
  'Combat & Dash Mobility',
  'Resource & Score Economy',
] as const;

export type CanonicalModule = typeof CANONICAL_BUILDER_MODULES[number];

/**
 * Normalizes an arbitrary list of module strings to a deduplicated,
 * canonically ordered array containing only supported Builder modules.
 */
export function normalizeLogicModules(rawModules?: string[] | null): CanonicalModule[] {
  if (!rawModules || !Array.isArray(rawModules)) {
    return ['Procedural Generation', 'Enhanced NPC Behavior'];
  }

  const result = new Set<CanonicalModule>();

  for (const raw of rawModules) {
    if (typeof raw !== 'string') continue;
    const trimmed = raw.trim();
    if (!trimmed) continue;

    // Direct match against canonical names
    if (CANONICAL_BUILDER_MODULES.includes(trimmed as CanonicalModule)) {
      result.add(trimmed as CanonicalModule);
      continue;
    }

    // Semantic keyword mapping from granular mechanics
    const lower = trimmed.toLowerCase();
    if (
      lower.includes('procedural') ||
      lower.includes('seed') ||
      lower.includes('layout') ||
      lower.includes('daynight') ||
      lower.includes('world')
    ) {
      result.add('Procedural Generation');
    } else if (
      lower.includes('npc') ||
      lower.includes('behavior') ||
      lower.includes('chase') ||
      lower.includes('patrol') ||
      lower.includes('enemy') ||
      lower.includes('ai')
    ) {
      result.add('Enhanced NPC Behavior');
    } else if (
      lower.includes('combat') ||
      lower.includes('dash') ||
      lower.includes('plasma') ||
      lower.includes('weapon') ||
      lower.includes('health') ||
      lower.includes('shooter') ||
      lower.includes('attack') ||
      lower.includes('bullet')
    ) {
      result.add('Combat & Dash Mobility');
    } else if (
      lower.includes('resource') ||
      lower.includes('score') ||
      lower.includes('inventory') ||
      lower.includes('craft') ||
      lower.includes('magnet') ||
      lower.includes('item') ||
      lower.includes('collect') ||
      lower.includes('economy')
    ) {
      result.add('Resource & Score Economy');
    }
  }

  // Preserve deterministic canonical ordering
  const ordered = CANONICAL_BUILDER_MODULES.filter((m) => result.has(m));
  return ordered.length > 0 ? ordered : ['Procedural Generation', 'Enhanced NPC Behavior'];
}
