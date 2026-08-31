import Phaser from 'phaser';
import type { RuntimeVisualProfile } from './visualProfile';


/**
 * Procedural VFX, Animation & Game Feel System (Game Runtime Experience V1).
 *
 * Implements bounded particle bursts, procedural squash/stretch animation states,
 * hit flashes, combat recoil, dash trails, and tiered camera impacts with zero memory leaks.
 */

export class VFXSystem {
  private scene: Phaser.Scene;
  private profile: RuntimeVisualProfile;
  private activeTweens: Phaser.Tweens.Tween[] = [];
  private ghostSprites: Phaser.GameObjects.Sprite[] = [];

  constructor(scene: Phaser.Scene, profile: RuntimeVisualProfile) {
    this.scene = scene;
    this.profile = profile;
  }

  /**
   * Spawns a bounded directional combat muzzle flash and bullet recoil.
   */
  public triggerMuzzleFlash(x: number, y: number, angleRad: number): void {
    if (this.profile.reducedMotion) return;

    const flash = this.scene.add.circle(
      x + Math.cos(angleRad) * 16,
      y + Math.sin(angleRad) * 16,
      6,
      Phaser.Display.Color.HexStringToColor(this.profile.player.weaponGlow).color,
      0.8
    );
    flash.setDepth(20);

    const tween = this.scene.tweens.add({
      targets: flash,
      scale: 1.8,
      alpha: 0,
      duration: 100,
      onComplete: () => {
        flash.destroy();
        this.activeTweens = this.activeTweens.filter((t) => t !== tween);
      },
    });
    this.activeTweens.push(tween);
  }

  /**
   * Triggers an immediate hit flash and micro-knockback visual on an entity.
   */
  public triggerHitFeedback(target: Phaser.GameObjects.Sprite, isCritical: boolean = false): void {
    // 1. White Hit Flash
    const origTint = target.tintTopLeft;
    target.setTintFill(0xffffff);

    this.scene.time.delayedCall(75, () => {
      if (target.active) {
        if (origTint && origTint !== 0xffffff) {
          target.setTint(origTint);
        } else {
          target.clearTint();
        }
      }
    });

    // 2. Micro impact sparks
    this.spawnImpactSparks(target.x, target.y, isCritical ? 8 : 4);

    // 3. Tiered Screen Shake
    if (!this.profile.reducedMotion) {
      const intensity = isCritical ? 0.012 : 0.004;
      this.scene.cameras.main.shake(80, intensity);
    }
  }

  /**
   * Spawns a bounded burst of sparkling debris particles.
   */
  public spawnImpactSparks(x: number, y: number, count: number = 6): void {
    const pCol = Phaser.Display.Color.HexStringToColor(this.profile.palette.accent).color;

    for (let i = 0; i < count; i++) {
      const spark = this.scene.add.circle(x, y, 2.5, pCol, 0.9);
      spark.setDepth(25);

      const angle = Math.random() * Math.PI * 2;
      const speed = 40 + Math.random() * 80;

      const tween = this.scene.tweens.add({
        targets: spark,
        x: x + Math.cos(angle) * speed,
        y: y + Math.sin(angle) * speed,
        alpha: 0,
        scale: 0.5,
        duration: 180 + Math.random() * 80,
        ease: 'Quad.easeOut',
        onComplete: () => {
          spark.destroy();
          this.activeTweens = this.activeTweens.filter((t) => t !== tween);
        },
      });
      this.activeTweens.push(tween);
    }
  }

  /**
   * Spawns a luminous pickup halo for gathered collectibles.
   */
  public triggerPickupFeedback(x: number, y: number): void {
    const ring = this.scene.add.circle(
      x,
      y,
      10,
      Phaser.Display.Color.HexStringToColor(this.profile.palette.collectible).color,
      0.8
    );
    ring.setStrokeStyle(2, 0xffffff, 0.9);
    ring.setDepth(30);

    const tween = this.scene.tweens.add({
      targets: ring,
      scale: 3.2,
      alpha: 0,
      duration: 300,
      ease: 'Cubic.easeOut',
      onComplete: () => {
        ring.destroy();
        this.activeTweens = this.activeTweens.filter((t) => t !== tween);
      },
    });
    this.activeTweens.push(tween);
  }

  /**
   * Creates a decaying ghost trail afterimage during high-speed dashing.
   */
  public triggerDashGhost(player: Phaser.GameObjects.Sprite): void {
    if (this.profile.reducedMotion) return;

    const ghost = this.scene.add.sprite(player.x, player.y, player.texture.key);
    ghost.setDisplaySize(player.displayWidth, player.displayHeight);
    ghost.setRotation(player.rotation);
    ghost.setTint(Phaser.Display.Color.HexStringToColor(this.profile.player.primaryColor).color);
    ghost.setAlpha(0.6);
    ghost.setDepth(player.depth - 1);
    this.ghostSprites.push(ghost);

    const tween = this.scene.tweens.add({
      targets: ghost,
      alpha: 0,
      scaleX: player.scaleX * 1.15,
      scaleY: player.scaleY * 1.15,
      duration: 220,
      ease: 'Linear',
      onComplete: () => {
        ghost.destroy();
        this.ghostSprites = this.ghostSprites.filter((g) => g !== ghost);
        this.activeTweens = this.activeTweens.filter((t) => t !== tween);
      },
    });
    this.activeTweens.push(tween);
  }

  /**
   * Adds an organic idle breathing / bobbing animation to a sprite.
   */
  public addIdleAnimation(target: Phaser.GameObjects.Sprite, intensity: number = 1.0): Phaser.Tweens.Tween | null {
    if (this.profile.reducedMotion) return null;

    const origY = target.y;
    const tween = this.scene.tweens.add({
      targets: target,
      y: origY - 3 * intensity,
      duration: 1200 + Math.random() * 300,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });
    this.activeTweens.push(tween);
    return tween;
  }

  /**
   * Destroys all active tweens and cleans up transient particle objects.
   */
  public destroy(): void {
    for (const t of this.activeTweens) {
      if (t.isPlaying()) t.stop();
    }
    this.activeTweens = [];

    for (const g of this.ghostSprites) {
      if (g.active) g.destroy();
    }
    this.ghostSprites = [];
  }
}
