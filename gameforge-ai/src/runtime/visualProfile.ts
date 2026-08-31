import type { GameDSL, LevelDef } from './types';

/**
 * Runtime Visual Profile System (Game Runtime Experience V1).
 *
 * Provides a single centralized abstraction deriving visual style, color palettes,
 * background modes, shape language, HUD presentation, and particle profiles
 * deterministically from existing GameDSL metadata and level definitions.
 */

export type ThemePresetKey = 'cyberpunk' | 'dungeon' | 'space' | 'wasteland' | 'arcade' | 'neutral';

export type BackgroundMode =
  | 'GRID'
  | 'STARS'
  | 'CITY'
  | 'RUINS'
  | 'INDUSTRIAL'
  | 'ABSTRACT'
  | 'DESERT'
  | 'SPACE'
  | 'ARENA';


export interface VisualPalette {
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  backgroundTint: number;
  surface: string;
  text: string;
  hazard: string;
  collectible: string;
  boss: string;
}

export interface PlayerStyle {
  silhouette: 'operative' | 'knight' | 'starship' | 'runner' | 'crawler';
  primaryColor: string;
  accentColor: string;
  weaponGlow: string;
  hasEngineTrail: boolean;
}

export interface EnemyStyle {
  shapeLanguage: 'angular' | 'crested' | 'faceted' | 'spiked' | 'robotic';
  basicColor: string;
  fastColor: string;
  rangedColor: string;
  heavyColor: string;
  eliteColor: string;
  bossColor: string;
}

export interface EnvironmentStyle {
  backgroundMode: BackgroundMode;
  propDensity: 'low' | 'medium' | 'high';
  propMotifs: string[];
  ambientColor: string;
  hasParallaxStars: boolean;
  hasAmbientDust: boolean;
}

export interface HudStyle {
  borderStyle: 'terminal' | 'runic' | 'minimal' | 'bold';
  accentColor: string;
  healthColor: string;
  staminaColor: string;
  fontFamily: string;
}

export interface RuntimeVisualProfile {
  themeKey: ThemePresetKey;
  palette: VisualPalette;
  player: PlayerStyle;
  enemy: EnemyStyle;
  environment: EnvironmentStyle;
  hud: HudStyle;
  reducedMotion: boolean;
}

export const THEME_PRESETS: Record<ThemePresetKey, {
  palette: VisualPalette;
  playerSilhouette: PlayerStyle['silhouette'];
  enemyShapeLanguage: EnemyStyle['shapeLanguage'];
  backgroundMode: BackgroundMode;
  propMotifs: string[];
  hudStyle: HudStyle['borderStyle'];
}> = {
  cyberpunk: {
    palette: {
      primary: '#00f0ff',
      secondary: '#ff0055',
      accent: '#ffe600',
      background: '#0a0518',
      backgroundTint: 0x0a0518,
      surface: '#150a2a',
      text: '#00f0ff',
      hazard: '#ff0055',
      collectible: '#00ffcc',
      boss: '#ff0077',
    },
    playerSilhouette: 'operative',
    enemyShapeLanguage: 'angular',
    backgroundMode: 'CITY',
    propMotifs: ['terminal', 'hologram', 'vent', 'cables'],
    hudStyle: 'terminal',
  },
  dungeon: {
    palette: {
      primary: '#ffb84d',
      secondary: '#ff3300',
      accent: '#990000',
      background: '#120d0a',
      backgroundTint: 0x120d0a,
      surface: '#221612',
      text: '#ffcca0',
      hazard: '#cc3300',
      collectible: '#ffd700',
      boss: '#990000',
    },
    playerSilhouette: 'knight',
    enemyShapeLanguage: 'crested',
    backgroundMode: 'RUINS',
    propMotifs: ['torch', 'pillar', 'rubble', 'altar'],
    hudStyle: 'runic',
  },
  space: {
    palette: {
      primary: '#66e3ff',
      secondary: '#bd00ff',
      accent: '#ff3366',
      background: '#020412',
      backgroundTint: 0x020412,
      surface: '#080d24',
      text: '#e0f7ff',
      hazard: '#ff3366',
      collectible: '#66e3ff',
      boss: '#bd00ff',
    },
    playerSilhouette: 'starship',
    enemyShapeLanguage: 'faceted',
    backgroundMode: 'SPACE',
    propMotifs: ['satellite', 'beacon', 'solar_panel', 'crate'],
    hudStyle: 'minimal',
  },
  wasteland: {
    palette: {
      primary: '#ffd166',
      secondary: '#ef476f',
      accent: '#06d6a0',
      background: '#1a140e',
      backgroundTint: 0x1a140e,
      surface: '#2b2117',
      text: '#ffd166',
      hazard: '#ef476f',
      collectible: '#06d6a0',
      boss: '#ef476f',
    },
    playerSilhouette: 'crawler',
    enemyShapeLanguage: 'spiked',
    backgroundMode: 'DESERT',
    propMotifs: ['barricade', 'debris', 'barrel', 'scrap'],
    hudStyle: 'bold',
  },
  arcade: {
    palette: {
      primary: '#39ff14',
      secondary: '#ff073a',
      accent: '#ffe600',
      background: '#050014',
      backgroundTint: 0x050014,
      surface: '#150030',
      text: '#39ff14',
      hazard: '#ff073a',
      collectible: '#ffe600',
      boss: '#ff073a',
    },
    playerSilhouette: 'runner',
    enemyShapeLanguage: 'robotic',
    backgroundMode: 'ARENA',
    propMotifs: ['bumper', 'light_post', 'stripe_pad', 'circuit'],
    hudStyle: 'bold',
  },
  neutral: {
    palette: {
      primary: '#00f0ff',
      secondary: '#ff0055',
      accent: '#ffbb00',
      background: '#050510',
      backgroundTint: 0x050510,
      surface: '#101020',
      text: '#ffffff',
      hazard: '#ff0055',
      collectible: '#00ffcc',
      boss: '#ff0077',
    },
    playerSilhouette: 'starship',
    enemyShapeLanguage: 'angular',
    backgroundMode: 'GRID',
    propMotifs: ['node', 'crate', 'marker', 'terminal'],
    hudStyle: 'minimal',
  },
};

/**
 * Deterministically resolves a full RuntimeVisualProfile from GameDSL, active level, and options.
 */
export function resolveVisualProfile(
  dsl: GameDSL,
  activeLevel?: LevelDef | null,
  options?: { reducedMotion?: boolean; artDensityOverride?: number }
): RuntimeVisualProfile {
  const rawTheme = (activeLevel?.world?.theme || dsl.world.theme || 'neon').toLowerCase();
  let themeKey: ThemePresetKey = 'neutral';

  if (rawTheme.includes('cyber') || rawTheme.includes('neon') || rawTheme.includes('city') || rawTheme.includes('urban')) {
    themeKey = 'cyberpunk';
  } else if (rawTheme.includes('dungeon') || rawTheme.includes('fantasy') || rawTheme.includes('cave')) {
    themeKey = 'dungeon';
  } else if (rawTheme.includes('space') || rawTheme.includes('colony') || rawTheme.includes('void')) {
    themeKey = 'space';
  } else if (rawTheme.includes('waste') || rawTheme.includes('desert') || rawTheme.includes('zombie')) {
    themeKey = 'wasteland';
  } else if (rawTheme.includes('retro') || rawTheme.includes('arcade') || rawTheme.includes('minimal')) {
    themeKey = 'arcade';
  }

  const preset = THEME_PRESETS[themeKey];
  const bgHex = activeLevel?.world?.background_color || dsl.world.background_color || preset.palette.background;
  const bgTint = parseInt(bgHex.replace('#', '0x'), 16) || preset.palette.backgroundTint;

  const playerCol = dsl.player.color || preset.palette.primary;
  const weaponCol = dsl.player.weapon_color || preset.palette.accent;

  // Calculate prop density from artDensity parameter
  const rawDensity = options?.artDensityOverride ?? (dsl.world.hazard_density !== undefined ? 50 : 50);
  const propDensity: 'low' | 'medium' | 'high' = rawDensity >= 70 ? 'high' : rawDensity >= 35 ? 'medium' : 'low';

  return {
    themeKey,
    palette: {
      ...preset.palette,
      background: bgHex,
      backgroundTint: bgTint,
      primary: playerCol,
      accent: weaponCol,
    },
    player: {
      silhouette: preset.playerSilhouette,
      primaryColor: playerCol,
      accentColor: weaponCol,
      weaponGlow: weaponCol,
      hasEngineTrail: themeKey === 'space' || themeKey === 'cyberpunk',
    },
    enemy: {
      shapeLanguage: preset.enemyShapeLanguage,
      basicColor: preset.palette.secondary,
      fastColor: preset.palette.primary,
      rangedColor: preset.palette.accent,
      heavyColor: preset.palette.surface,
      eliteColor: '#ff00ff',
      bossColor: preset.palette.boss,
    },
    environment: {
      backgroundMode: preset.backgroundMode,
      propDensity,
      propMotifs: preset.propMotifs,
      ambientColor: bgHex,
      hasParallaxStars: themeKey === 'space' || themeKey === 'cyberpunk',
      hasAmbientDust: themeKey === 'dungeon' || themeKey === 'wasteland',
    },
    hud: {
      borderStyle: preset.hudStyle,
      accentColor: preset.palette.primary,
      healthColor: '#00ff88',
      staminaColor: preset.palette.primary,
      fontFamily: 'Space Grotesk, JetBrains Mono, monospace',
    },
    reducedMotion: options?.reducedMotion ?? false,
  };
}
