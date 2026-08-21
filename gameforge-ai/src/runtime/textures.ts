import Phaser from 'phaser';

/**
 * Generates procedural crisp vector-style textures directly into Phaser's TextureManager.
 * This guarantees zero external asset dependencies, zero network requests, and zero copyrighted art.
 */
export function generateProceduralTextures(scene: Phaser.Scene): void {
  // 1. Player Ship / Hero Avatar (32x32)
  if (!scene.textures.exists('tex_player')) {
    const canvas = scene.textures.createCanvas('tex_player', 32, 32);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 32, 32);

      // Cyan neon ship polygon
      ctx.fillStyle = '#00f0ff';
      ctx.shadowColor = '#00f0ff';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(16, 2);
      ctx.lineTo(30, 28);
      ctx.lineTo(16, 22);
      ctx.lineTo(2, 28);
      ctx.closePath();
      ctx.fill();

      // Cockpit glow
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(16, 14, 4, 0, Math.PI * 2);
      ctx.fill();

      canvas.refresh();
    }
  }

  // 2. Enemy Drone / Hazard Creature (24x24)
  if (!scene.textures.exists('tex_enemy')) {
    const canvas = scene.textures.createCanvas('tex_enemy', 24, 24);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 24, 24);

      // Red neon diamond / skull drone
      ctx.fillStyle = '#ff0055';
      ctx.shadowColor = '#ff0055';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(12, 1);
      ctx.lineTo(23, 12);
      ctx.lineTo(12, 23);
      ctx.lineTo(1, 12);
      ctx.closePath();
      ctx.fill();

      // Enemy core
      ctx.fillStyle = '#ffe600';
      ctx.beginPath();
      ctx.arc(12, 12, 3, 0, Math.PI * 2);
      ctx.fill();

      canvas.refresh();
    }
  }

  // 3. Collectible Energy Gem / Coin (20x20)
  if (!scene.textures.exists('tex_collectible')) {
    const canvas = scene.textures.createCanvas('tex_collectible', 20, 20);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 20, 20);

      // Gold glowing circle/star
      ctx.fillStyle = '#ffe600';
      ctx.shadowColor = '#ffe600';
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(10, 10, 8, 0, Math.PI * 2);
      ctx.fill();

      // Inner ring
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(10, 10, 5, 0, Math.PI * 2);
      ctx.stroke();

      canvas.refresh();
    }
  }

  // 4. Laser Projectile (8x16)
  if (!scene.textures.exists('tex_bullet')) {
    const canvas = scene.textures.createCanvas('tex_bullet', 8, 16);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 8, 16);

      ctx.fillStyle = '#00ffaa';
      ctx.shadowColor = '#00ffaa';
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.roundRect(1, 1, 6, 14, 3);
      ctx.fill();

      canvas.refresh();
    }
  }

  // 4b. Enemy Plasma Projectile (10x10)
  if (!scene.textures.exists('tex_enemy_bullet')) {
    const canvas = scene.textures.createCanvas('tex_enemy_bullet', 10, 10);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 10, 10);

      ctx.fillStyle = '#ff0055';
      ctx.shadowColor = '#ff0055';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.arc(5, 5, 4, 0, Math.PI * 2);
      ctx.fill();

      // Bright inner core
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(5, 5, 2, 0, Math.PI * 2);
      ctx.fill();

      canvas.refresh();
    }
  }

  // 5. Solid Platform Block (64x24)
  if (!scene.textures.exists('tex_platform')) {
    const canvas = scene.textures.createCanvas('tex_platform', 64, 24);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 64, 24);

      // Platform body
      ctx.fillStyle = '#1e2238';
      ctx.fillRect(0, 0, 64, 24);

      // Top neon border
      ctx.fillStyle = '#4ce0d2';
      ctx.shadowColor = '#4ce0d2';
      ctx.shadowBlur = 6;
      ctx.fillRect(0, 0, 64, 4);

      // Subtle tech outline
      ctx.strokeStyle = '#383d63';
      ctx.lineWidth = 1;
      ctx.strokeRect(0, 0, 64, 24);

      canvas.refresh();
    }
  }

  // 6. Hazard Spikes (32x24)
  if (!scene.textures.exists('tex_hazard')) {
    const canvas = scene.textures.createCanvas('tex_hazard', 32, 24);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 32, 24);

      ctx.fillStyle = '#ff3300';
      ctx.shadowColor = '#ff3300';
      ctx.shadowBlur = 6;

      // Draw 2 triangular spikes
      ctx.beginPath();
      ctx.moveTo(0, 24);
      ctx.lineTo(8, 2);
      ctx.lineTo(16, 24);
      ctx.lineTo(24, 2);
      ctx.lineTo(32, 24);
      ctx.closePath();
      ctx.fill();

      canvas.refresh();
    }
  }

  // 7. Goal Beacon / Exit Portal (36x48)
  if (!scene.textures.exists('tex_goal')) {
    const canvas = scene.textures.createCanvas('tex_goal', 36, 48);
    if (canvas) {
      const ctx = canvas.getContext();
      ctx.clearRect(0, 0, 36, 48);

      // Portal arch
      ctx.strokeStyle = '#00ffaa';
      ctx.shadowColor = '#00ffaa';
      ctx.shadowBlur = 12;
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(18, 18, 14, Math.PI, 0);
      ctx.lineTo(32, 46);
      ctx.lineTo(4, 46);
      ctx.closePath();
      ctx.stroke();

      // Energy core
      ctx.fillStyle = 'rgba(0, 255, 170, 0.4)';
      ctx.beginPath();
      ctx.arc(18, 24, 10, 0, Math.PI * 2);
      ctx.fill();

      canvas.refresh();
    }
  }
}
