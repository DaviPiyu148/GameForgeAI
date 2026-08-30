/**
 * Builder Presets — canonical one-click configuration shortcuts.
 *
 * Design rules:
 *   1. All preset values derive from or intentionally override the canonical
 *      `defaultBuildParams` defined in AppContext.tsx. They do NOT maintain a
 *      second copy of the defaults; only the fields that meaningfully differ
 *      from the default are specified here.
 *   2. Preset override semantics: DEFAULT + PRESET_OVERRIDES = FINAL_BUILDER_STATE.
 *      This is enforced by the caller via:
 *        updateBuildParams({ ...defaultBuildParams, ...preset.overrides })
 *   3. No new BuildParams fields are introduced here. Only values already
 *      supported by the Builder UI and the backend API are used.
 *
 * Canonical defaultBuildParams (from AppContext.tsx — do not duplicate here):
 *   engine:      'Top-Down Action'
 *   artDensity:  50
 *   physics:     80
 *   modules:     ['Procedural Generation', 'Enhanced NPC Behavior']
 *   scale:       'standard'
 *   world_mode:  'linear'
 */

import type { BuildParams } from '../types';

export interface BuilderPreset {
  /** Unique key used for active-state tracking */
  key: string;
  /** Display label on the preset chip */
  label: string;
  /** Material Symbol icon name */
  icon: string;
  /**
   * ONLY the fields that differ from defaultBuildParams.
   * The caller merges: { ...defaultBuildParams, ...overrides }
   */
  overrides: Partial<BuildParams>;
}

/**
 * The canonical default build parameters, mirrored from AppContext.tsx for
 * preset-matching comparison. This is the SINGLE authoritative reference for
 * the default builder state used in preset matching.
 *
 * IMPORTANT: Keep this in sync with `defaultBuildParams` in AppContext.tsx.
 * If AppContext defaults change, update this object too.
 */
export const CANONICAL_DEFAULTS: BuildParams = {
  engine: 'Top-Down Action',
  artDensity: 50,
  physics: 80,
  modules: ['Procedural Generation', 'Enhanced NPC Behavior'],
  scale: 'standard',
  world_mode: 'linear',
};

/**
 * The three official Builder presets.
 *
 * Quick Prototype: Fast single-level linear game. Good for testing a concept.
 * Campaign:        Sequential multi-level campaign. Full game experience.
 * Open World:      Generalized open-world architecture with districts/vehicles.
 */
export const BUILDER_PRESETS: BuilderPreset[] = [
  {
    key: 'quick_prototype',
    label: 'Quick Prototype',
    icon: 'bolt',
    overrides: {
      scale: 'prototype',
      world_mode: 'linear',
      artDensity: 40,
      physics: 60,
      modules: ['Procedural Generation'],
    },
  },
  {
    key: 'campaign',
    label: 'Campaign',
    icon: 'military_tech',
    overrides: {
      scale: 'campaign',
      world_mode: 'campaign',
      artDensity: 65,
      physics: 80,
      modules: ['Procedural Generation', 'Enhanced NPC Behavior', 'Combat & Dash Mobility'],
    },
  },
  {
    key: 'open_world',
    label: 'Open World',
    icon: 'explore',
    overrides: {
      scale: 'campaign',
      world_mode: 'open_world',
      artDensity: 70,
      physics: 85,
      modules: [
        'Procedural Generation',
        'Enhanced NPC Behavior',
        'Combat & Dash Mobility',
        'Resource & Score Economy',
      ],
    },
  },
];

/**
 * Derive the full BuildParams for a preset by merging overrides onto defaults.
 * This is the canonical merge function — always call this, never spread manually.
 */
export function applyPreset(preset: BuilderPreset): BuildParams {
  return { ...CANONICAL_DEFAULTS, ...preset.overrides };
}

/**
 * Determine which preset (if any) is currently active given the builder's state.
 * Returns the preset key or null if the current state doesn't match any preset.
 *
 * Comparison uses a fixed set of discriminating fields — fields that can
 * meaningfully differ between presets. This avoids expensive full-object
 * deep-equality on every render.
 */
export function detectActivePreset(params: BuildParams): string | null {
  const DISCRIMINATING: (keyof BuildParams)[] = [
    'scale', 'world_mode', 'artDensity', 'physics',
  ];

  for (const preset of BUILDER_PRESETS) {
    const full = applyPreset(preset);
    const matches = DISCRIMINATING.every((k) => params[k] === full[k]);
    if (matches) return preset.key;
  }
  return null;
}
