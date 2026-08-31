import Phaser from 'phaser';
import type { RuntimeVisualProfile } from './visualProfile';


/**
 * Procedural Texture Generator & Texture Cache (Game Runtime Experience V1).
 *
 * Generates rich vector silhouettes directly into Phaser's TextureManager.
 * Keyed by: profile + role + variant + theme. Cached so identical assets
 * are generated exactly once and reused across levels.
 */

export function generateDynamicTextures(scene: Phaser.Scene, profile: RuntimeVisualProfile): void {
  const p = profile.palette;

  // ───────────────────────────────────────────────────────────────────────────
  // 1. Player Silhouettes
  // ───────────────────────────────────────────────────────────────────────────
  const playerKey = `tex_player_${profile.player.silhouette}_${profile.themeKey}`;
  if (!scene.textures.exists(playerKey)) {
    const canvas = scene.textures.createCanvas(playerKey, 36, 36);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 36, 36);

      ctx.fillStyle = profile.player.primaryColor;
      ctx.strokeStyle = profile.player.accentColor;
      ctx.lineWidth = 2;
      ctx.shadowColor = profile.player.primaryColor;
      ctx.shadowBlur = 6;

      if (profile.player.silhouette === 'knight') {
        // Crested Warrior / Knight Silhouette
        ctx.beginPath();
        ctx.moveTo(18, 4);
        ctx.lineTo(28, 12);
        ctx.lineTo(26, 28);
        ctx.lineTo(18, 34);
        ctx.lineTo(10, 28);
        ctx.lineTo(8, 12);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        // Visor slit
        ctx.fillStyle = profile.player.accentColor;
        ctx.fillRect(13, 14, 10, 3);
      } else if (profile.player.silhouette === 'operative') {
        // Angular Cyber Operative with shoulder pauldrons
        ctx.beginPath();
        ctx.moveTo(18, 3);
        ctx.lineTo(31, 24);
        ctx.lineTo(24, 32);
        ctx.lineTo(18, 27);
        ctx.lineTo(12, 32);
        ctx.lineTo(5, 24);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        // Core holographic node
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(18, 16, 3, 0, Math.PI * 2);
        ctx.fill();
      } else if (profile.player.silhouette === 'crawler') {
        // Armored Buggy / Wasteland Crawler
        ctx.fillRect(8, 8, 20, 20);
        ctx.strokeRect(8, 8, 20, 20);
        // Treads
        ctx.fillStyle = profile.player.accentColor;
        ctx.fillRect(4, 6, 4, 24);
        ctx.fillRect(28, 6, 4, 24);
        // Turret hatch
        ctx.beginPath();
        ctx.arc(18, 18, 5, 0, Math.PI * 2);
        ctx.fill();
      } else if (profile.player.silhouette === 'runner') {
        // Sleek Arcade Wedge
        ctx.beginPath();
        ctx.moveTo(18, 2);
        ctx.lineTo(32, 30);
        ctx.lineTo(18, 24);
        ctx.lineTo(4, 30);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else {
        // Default Starship / Pilot
        ctx.beginPath();
        ctx.moveTo(18, 2);
        ctx.lineTo(32, 28);
        ctx.lineTo(18, 22);
        ctx.lineTo(4, 28);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(18, 14, 4, 0, Math.PI * 2);
        ctx.fill();
      }

      canvas.refresh();
    }
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 2. Enemy Role Variants (Basic, Fast, Ranged, Heavy, Elite, Boss)
  // ───────────────────────────────────────────────────────────────────────────
  const roles = [
    { id: 'basic', size: 28, shape: 'diamond', col: profile.enemy.basicColor },
    { id: 'fast', size: 22, shape: 'chevron', col: profile.enemy.fastColor },
    { id: 'ranged', size: 26, shape: 'orb', col: profile.enemy.rangedColor },
    { id: 'heavy', size: 36, shape: 'hexagon', col: profile.enemy.heavyColor },
    { id: 'elite', size: 32, shape: 'spiked', col: profile.enemy.eliteColor },
    { id: 'boss', size: 64, shape: 'monolith', col: profile.enemy.bossColor },
  ];

  roles.forEach((r) => {
    const enemyKey = `tex_enemy_${r.id}_${profile.themeKey}`;
    if (!scene.textures.exists(enemyKey)) {
      const canvas = scene.textures.createCanvas(enemyKey, r.size, r.size);
      if (canvas) {
        const ctx = canvas.getContext();
        ctx.clearRect(0, 0, r.size, r.size);

        ctx.fillStyle = r.col;
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = r.id === 'boss' ? 3 : 1.5;
        ctx.shadowColor = r.col;
        ctx.shadowBlur = r.id === 'boss' ? 12 : 6;

        const half = r.size / 2;

        if (r.shape === 'chevron') {
          // Fast Scout: Swept forward dagger
          ctx.beginPath();
          ctx.moveTo(half, 2);
          ctx.lineTo(r.size - 2, r.size - 4);
          ctx.lineTo(half, half + 4);
          ctx.lineTo(2, r.size - 4);
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
        } else if (r.shape === 'orb') {
          // Ranged Artillery: Energy orb with crosshairs
          ctx.beginPath();
          ctx.arc(half, half, half - 3, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
          // Targeting pupil
          ctx.fillStyle = '#ffffff';
          ctx.beginPath();
          ctx.arc(half, half, 3, 0, Math.PI * 2);
          ctx.fill();
        } else if (r.shape === 'hexagon') {
          // Heavy Brute: Thick faceted armored hexagon
          ctx.beginPath();
          for (let a = 0; a < 6; a++) {
            const angle = (a * Math.PI) / 3;
            const x = half + (half - 3) * Math.cos(angle);
            const y = half + (half - 3) * Math.sin(angle);
            if (a === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
        } else if (r.shape === 'spiked') {
          // Elite Unit: Star burst silhouette
          ctx.beginPath();
          for (let a = 0; a < 8; a++) {
            const rRad = a % 2 === 0 ? half - 2 : half / 2;
            const angle = (a * Math.PI) / 4;
            const x = half + rRad * Math.cos(angle);
            const y = half + rRad * Math.sin(angle);
            if (a === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
        } else if (r.shape === 'monolith') {
          // Boss: Imposing crowned fortress crest
          ctx.beginPath();
          ctx.moveTo(half, 4);
          ctx.lineTo(r.size - 6, 16);
          ctx.lineTo(r.size - 10, r.size - 8);
          ctx.lineTo(half + 10, r.size - 4);
          ctx.lineTo(half, r.size - 12);
          ctx.lineTo(half - 10, r.size - 4);
          ctx.lineTo(10, r.size - 8);
          ctx.lineTo(6, 16);
          ctx.closePath();
          ctx.fill();
          ctx.stroke();

          // Menacing eye core
          ctx.fillStyle = '#ffffff';
          ctx.beginPath();
          ctx.arc(half, 24, 6, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = '#ffe600';
          ctx.beginPath();
          ctx.arc(half, 24, 3, 0, Math.PI * 2);
          ctx.fill();
        } else {
          // Basic Drone: Sharp faceted diamond
          ctx.beginPath();
          ctx.moveTo(half, 2);
          ctx.lineTo(r.size - 2, half);
          ctx.lineTo(half, r.size - 2);
          ctx.lineTo(2, half);
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
        }

        canvas.refresh();
      }
    }
  });

  // ───────────────────────────────────────────────────────────────────────────
  // 3. Thematic Collectible Gem / Relic (24x24)
  // ───────────────────────────────────────────────────────────────────────────
  const colKey = `tex_collectible_${profile.themeKey}`;
  if (!scene.textures.exists(colKey)) {
    const canvas = scene.textures.createCanvas(colKey, 24, 24);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 24, 24);

      ctx.fillStyle = p.collectible;
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.shadowColor = p.collectible;
      ctx.shadowBlur = 8;

      if (profile.themeKey === 'dungeon') {
        // Gold Coin / Relic Seal
        ctx.beginPath();
        ctx.arc(12, 12, 9, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(10, 8, 4, 8);
      } else {
        // Luminous Octagonal Shard / Data Cube
        ctx.beginPath();
        ctx.moveTo(12, 2);
        ctx.lineTo(20, 7);
        ctx.lineTo(22, 16);
        ctx.lineTo(16, 22);
        ctx.lineTo(8, 22);
        ctx.lineTo(2, 16);
        ctx.lineTo(4, 7);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(12, 12, 3, 0, Math.PI * 2);
        ctx.fill();
      }

      canvas.refresh();
    }
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 4. Projectile Variants (Glow Laser / Magic Bolt)
  // ───────────────────────────────────────────────────────────────────────────
  const bulletKey = `tex_bullet_${profile.themeKey}`;
  if (!scene.textures.exists(bulletKey)) {
    const canvas = scene.textures.createCanvas(bulletKey, 10, 18);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 10, 18);

      ctx.fillStyle = profile.player.weaponGlow;
      ctx.shadowColor = profile.player.weaponGlow;
      ctx.shadowBlur = 8;

      // Rounded streak
      ctx.beginPath();
      ctx.ellipse(5, 9, 4, 8, 0, 0, Math.PI * 2);
      ctx.fill();

      // White hot core
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.ellipse(5, 9, 2, 4, 0, 0, Math.PI * 2);
      ctx.fill();

      canvas.refresh();
    }
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 5. Procedural Vehicles (Car, Speeder, Armored)
  // ───────────────────────────────────────────────────────────────────────────
  const vehicleTypes = ['car', 'bike', 'hovercraft'];
  vehicleTypes.forEach((vtype) => {
    const vKey = `tex_vehicle_${vtype}_${profile.themeKey}`;
    if (!scene.textures.exists(vKey)) {
      const canvas = scene.textures.createCanvas(vKey, 48, 28);
      if (canvas) {
        const ctx = canvas.getContext();
        ctx.clearRect(0, 0, 48, 28);

        ctx.fillStyle = p.primary;
        ctx.strokeStyle = p.accent;
        ctx.lineWidth = 2;
        ctx.shadowColor = p.primary;
        ctx.shadowBlur = 6;

        if (vtype === 'bike') {
          // Sleek Long Speeder Bike
          ctx.beginPath();
          ctx.moveTo(4, 14);
          ctx.lineTo(16, 8);
          ctx.lineTo(40, 9);
          ctx.lineTo(46, 14);
          ctx.lineTo(40, 19);
          ctx.lineTo(16, 20);
          ctx.closePath();
          ctx.fill();
          ctx.stroke();

          // Engine Thrusters
          ctx.fillStyle = p.accent;
          ctx.fillRect(2, 11, 4, 6);
        } else {
          // Armored Cruiser / Interceptor
          ctx.beginPath();
          ctx.moveTo(6, 6);
          ctx.lineTo(34, 5);
          ctx.lineTo(44, 14);
          ctx.lineTo(34, 23);
          ctx.lineTo(6, 22);
          ctx.closePath();
          ctx.fill();
          ctx.stroke();

          // Windshield
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(22, 9, 10, 10);
        }

        canvas.refresh();
      }
    }
  });

  // Ensure default fallback aliases exist
  if (!scene.textures.exists('tex_player')) {
    const pTex = scene.textures.get(playerKey);
    if (pTex) scene.textures.addCanvas('tex_player', pTex.getSourceImage() as HTMLCanvasElement);
  }
  if (!scene.textures.exists('tex_enemy')) {
    const eTex = scene.textures.get(`tex_enemy_basic_${profile.themeKey}`);
    if (eTex) scene.textures.addCanvas('tex_enemy', eTex.getSourceImage() as HTMLCanvasElement);
  }
  if (!scene.textures.exists('tex_collectible')) {
    const cTex = scene.textures.get(colKey);
    if (cTex) scene.textures.addCanvas('tex_collectible', cTex.getSourceImage() as HTMLCanvasElement);
  }
}
