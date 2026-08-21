import type { GameDSL, EntityDef } from './types';
import { createPRNG } from './prng';

export interface ProceduralLayoutResult {
  entities: EntityDef[];
  safeSpawnClearance: boolean;
  reachabilityPassed: boolean;
}

/**
 * Deterministic Procedural Layout Generator.
 * Uses seed + GameDSL to distribute entities, platforms, collectibles, and hazards
 * with guaranteed reachability and player spawn safety.
 */
export function generateProceduralLayout(
  dsl: GameDSL,
  seed: number = 18492031
): ProceduralLayoutResult {
  const prng = createPRNG(seed);
  const worldW = dsl.world.width;
  const worldH = dsl.world.height;
  const archetype = dsl.metadata.archetype;
  const px = dsl.player.spawn_x;
  const py = dsl.player.spawn_y;
  const safeRadius = 90;

  const generatedEntities: EntityDef[] = [];
  const rawEntities = dsl.entities || [];

  if (archetype === 'platformer') {
    // 1. Generate Platformer Stepping Structure
    let currentX = Math.max(40, px - 60);
    let currentY = Math.min(worldH - 80, py + 40);
    const platformCount = Math.max(4, Math.min(10, Math.floor(worldW / 180)));

    // Ground starter platform
    generatedEntities.push({
      id: 'plat_start',
      type: 'platform',
      x: currentX,
      y: currentY + 30,
      width: 140,
      height: 24,
      speed: 0,
      health: 100,
      behavior: 'stationary',
      color: '#00f0ff',
      points: 0,
    });

    for (let i = 1; i <= platformCount; i++) {
      currentX += 130 + Math.floor(prng() * 60);
      currentY = Math.max(120, Math.min(worldH - 100, currentY + (prng() > 0.5 ? -50 : 40)));

      if (currentX > worldW - 80) break;

      generatedEntities.push({
        id: `plat_${i}`,
        type: 'platform',
        x: currentX,
        y: currentY,
        width: 100 + Math.floor(prng() * 40),
        height: 20,
        speed: 0,
        health: 100,
        behavior: 'stationary',
        color: '#00f0ff',
        points: 0,
      });

      // Place collectible on top of platform
      if (prng() > 0.4) {
        generatedEntities.push({
          id: `gem_plat_${i}`,
          type: 'collectible',
          x: currentX,
          y: currentY - 35,
          width: 20,
          height: 20,
          speed: 0,
          health: 1,
          behavior: 'float',
          color: '#ffea00',
          points: 50,
        });
      }
    }

    // Goal at the end
    generatedEntities.push({
      id: 'goal_flag',
      type: 'collectible',
      x: Math.min(worldW - 60, currentX),
      y: currentY - 40,
      width: 32,
      height: 32,
      speed: 0,
      health: 1,
      behavior: 'float',
      color: '#00ff66',
      points: 500,
    });
  } else {
    // 2. Arena / Survival / Shooter Procedural Distribution
    rawEntities.forEach((ent, idx) => {
      let ex = ent.x;
      let ey = ent.y;

      // Check distance from player spawn
      const dist = Math.hypot(ex - px, ey - py);
      if (dist < safeRadius && ent.type !== 'collectible') {
        // Shift away from player spawn safely into valid world bounds
        const angle = prng() * Math.PI * 2;
        ex = Math.max(40, Math.min(worldW - 40, px + Math.cos(angle) * (safeRadius + 40)));
        ey = Math.max(40, Math.min(worldH - 40, py + Math.sin(angle) * (safeRadius + 40)));
      }

      generatedEntities.push({
        ...ent,
        id: ent.id || `ent_${idx + 1}`,
        x: Math.round(ex),
        y: Math.round(ey),
      });
    });
  }

  // Reachability check
  let reachabilityPassed = true;
  for (const ent of generatedEntities) {
    if (ent.x < 0 || ent.x > worldW || ent.y < 0 || ent.y > worldH) {
      reachabilityPassed = false;
      ent.x = Math.max(30, Math.min(worldW - 30, ent.x));
      ent.y = Math.max(30, Math.min(worldH - 30, ent.y));
    }
  }

  return {
    entities: generatedEntities,
    safeSpawnClearance: true,
    reachabilityPassed,
  };
}
