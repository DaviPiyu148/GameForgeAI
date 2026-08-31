import Phaser from 'phaser';
import type { RuntimeVisualProfile } from './visualProfile';


/**
 * Procedural Environment & Background System (Game Runtime Experience V1).
 *
 * Renders thematic procedural backgrounds, non-colliding decorative props
 * scaled by artDensity, subtle 2-layer parallax, and distinctive landmarks.
 */

export class EnvironmentSystem {
  private scene: Phaser.Scene;
  private profile: RuntimeVisualProfile;
  private bgContainer!: Phaser.GameObjects.Container;
  private decorContainer!: Phaser.GameObjects.Container;
  private parallaxStars: Phaser.GameObjects.Arc[] = [];
  private seed: number;

  constructor(scene: Phaser.Scene, profile: RuntimeVisualProfile, seed: number = 18492031) {
    this.scene = scene;
    this.profile = profile;
    this.seed = seed;
  }

  /**
   * Deterministic PRNG helper for consistent prop placement across runs.
   */
  private prng(): number {
    this.seed = (this.seed * 9301 + 49297) % 233280;
    return this.seed / 233280;
  }

  /**
   * Builds the procedural environment: background texture, decorative props, and landmarks.
   */
  public buildEnvironment(width: number, height: number): void {
    this.bgContainer = this.scene.add.container(0, 0);
    this.decorContainer = this.scene.add.container(0, 0);

    // Keep background and decor beneath gameplay layers
    this.bgContainer.setDepth(-100);
    this.decorContainer.setDepth(-50);

    const mode = this.profile.environment.backgroundMode;
    const g = this.scene.add.graphics();
    this.bgContainer.add(g);

    if (mode === 'RUINS') {
      // Dungeon Stone Pavement & Cracks
      g.lineStyle(1, 0x000000, 0.2);
      for (let y = 0; y < height; y += 60) {
        g.lineBetween(0, y, width, y);
        for (let x = (y % 120 === 0 ? 0 : 30); x < width; x += 60) {
          g.lineBetween(x, y, x, y + 60);
        }
      }
    } else if (mode === 'SPACE') {
      // Space Nebula Gradients & Star Field
      const starCount = this.profile.reducedMotion ? 30 : 70;
      for (let i = 0; i < starCount; i++) {
        const sx = this.prng() * width;
        const sy = this.prng() * height;
        const sSize = 1 + this.prng() * 2;
        const star = this.scene.add.circle(sx, sy, sSize, 0xffffff, 0.4 + this.prng() * 0.5);
        this.bgContainer.add(star);
        this.parallaxStars.push(star);
      }
    } else if (mode === 'CITY' || mode === 'GRID') {
      // Cyberpunk Grid / City Blueprint
      const gridCol = Phaser.Display.Color.HexStringToColor(this.profile.palette.primary).color;
      g.lineStyle(1, gridCol, 0.05);
      for (let x = 0; x < width; x += 48) {
        g.lineBetween(x, 0, x, height);
      }
      for (let y = 0; y < height; y += 48) {
        g.lineBetween(0, y, width, y);
      }
    } else if (mode === 'DESERT') {
      // Wasteland Topography Strata
      g.lineStyle(1, 0x3d2817, 0.15);
      for (let y = 0; y < height; y += 30) {
        g.beginPath();
        g.moveTo(0, y);
        for (let x = 0; x < width; x += 80) {
          g.lineTo(x, y + Math.sin(x * 0.02) * 8);
        }
        g.strokePath();
      }
    } else {
      // Arena Floor Border Accents
      const borderCol = Phaser.Display.Color.HexStringToColor(this.profile.palette.accent).color;
      g.lineStyle(2, borderCol, 0.1);
      g.strokeRect(40, 40, width - 80, height - 80);
    }

    // Spawn Non-Colliding Environmental Props based on artDensity
    this.spawnEnvironmentalProps(width, height);

    // Spawn Distinctive Landmarks
    this.spawnLandmarks(width, height);
  }

  /**
   * Spawns bounded non-colliding decorative props according to propDensity.
   */
  private spawnEnvironmentalProps(width: number, height: number): void {
    const density = this.profile.environment.propDensity;
    const propCount = density === 'high' ? 24 : density === 'medium' ? 14 : 6;
    const motifs = this.profile.environment.propMotifs;

    for (let i = 0; i < propCount; i++) {
      const px = 60 + this.prng() * (width - 120);
      const py = 60 + this.prng() * (height - 120);
      const motif = motifs[Math.floor(this.prng() * motifs.length)] || 'crate';

      const propG = this.scene.add.graphics();
      this.decorContainer.add(propG);

      const tint = Phaser.Display.Color.HexStringToColor(this.profile.palette.surface).color;
      const accent = Phaser.Display.Color.HexStringToColor(this.profile.palette.accent).color;

      if (motif === 'pillar' || motif === 'terminal') {
        propG.fillStyle(tint, 0.6);
        propG.fillRect(px, py, 20, 32);
        propG.lineStyle(1, accent, 0.4);
        propG.strokeRect(px, py, 20, 32);
      } else if (motif === 'torch' || motif === 'beacon') {
        propG.fillStyle(0x333333, 0.7);
        propG.fillRect(px, py, 8, 24);
        // Flame / Glow dot
        const glow = this.scene.add.circle(px + 4, py - 2, 4, accent, 0.6);
        this.decorContainer.add(glow);
      } else {
        // Debris / Crates / Ruin stones
        propG.fillStyle(tint, 0.5);
        propG.fillRect(px, py, 16, 16);
      }
    }
  }

  /**
   * Spawns a major visual landmark to give the space identifiable geometry.
   */
  private spawnLandmarks(width: number, height: number): void {
    const lx = width * 0.75;
    const ly = height * 0.35;

    const landmarkG = this.scene.add.graphics();
    this.decorContainer.add(landmarkG);

    const col = Phaser.Display.Color.HexStringToColor(this.profile.palette.primary).color;
    landmarkG.lineStyle(2, col, 0.2);

    if (this.profile.themeKey === 'dungeon') {
      // Ancient Runestone / Shrine Circle
      landmarkG.strokeCircle(lx, ly, 45);
      landmarkG.strokeCircle(lx, ly, 25);
    } else if (this.profile.themeKey === 'space') {
      // Solar Array / Communications Pylon
      landmarkG.strokeRect(lx - 25, ly - 35, 50, 70);
      landmarkG.lineBetween(lx - 25, ly, lx + 25, ly);
    } else {
      // Cyber Terminal / Generator Platform
      landmarkG.strokeRect(lx - 30, ly - 30, 60, 60);
      landmarkG.strokeCircle(lx, ly, 15);
    }
  }

  /**
   * Updates lightweight parallax stars on camera movement.
   */
  public updateParallax(scrollX: number, scrollY: number): void {
    if (this.profile.reducedMotion || this.parallaxStars.length === 0) return;
    for (let i = 0; i < this.parallaxStars.length; i++) {
      const star = this.parallaxStars[i];
      star.x = (star.x - scrollX * 0.0005) % this.scene.cameras.main.width;
      star.y = (star.y - scrollY * 0.0005) % this.scene.cameras.main.height;
    }
  }

  /**
   * Cleans up background and decor containers on scene shutdown.
   */
  public destroy(): void {
    this.parallaxStars = [];
    if (this.bgContainer) this.bgContainer.destroy();
    if (this.decorContainer) this.decorContainer.destroy();
  }
}
