import Phaser from 'phaser';
import type { EntityBehavior, EntityDef, EntityType } from './types';

/**
 * Entity Runtime Behavior State.
 * Encapsulates bound DSL parameters and dynamic simulation variables
 * for deterministic runtime execution without arbitrary scripts.
 */
export interface EntityRuntimeState {
  id: string;
  type: EntityType;
  behavior: EntityBehavior;
  originX: number;
  originY: number;
  speed: number;
  damage: number;
  fireRate: number; // in seconds between shots
  patrolRadius: number;
  detectionRadius: number;
  lastFiredTime: number;
  patrolDirection: number; // 1 or -1
  guardState: 'GUARDING' | 'ENGAGING' | 'RETURNING';
  floatPhase: number;
  bounceInitialized: boolean;
}

export interface BehaviorContext {
  time: number;
  delta: number;
  player: Phaser.Physics.Arcade.Sprite;
  scene: Phaser.Scene;
  enemyBulletsGroup: Phaser.Physics.Arcade.Group;
}

/**
 * Centralized Entity Behavior System.
 * Dispatches and executes validated entity behaviors across the Phaser Arcade physics simulation.
 */
export class EntityBehaviorSystem {
  private entityStates = new Map<Phaser.Physics.Arcade.Sprite, EntityRuntimeState>();

  /**
   * Register a spawned sprite with its validated DSL entity definition.
   */
  public registerEntity(sprite: Phaser.Physics.Arcade.Sprite, def: EntityDef): void {
    const state: EntityRuntimeState = {
      id: def.id,
      type: def.type,
      behavior: def.behavior || 'patrol',
      originX: def.x,
      originY: def.y,
      speed: def.speed ?? 100,
      damage: def.damage ?? 15,
      fireRate: def.fire_rate ?? 1.5,
      patrolRadius: def.patrol_radius ?? 150,
      detectionRadius: def.detection_radius ?? 250,
      lastFiredTime: 0,
      patrolDirection: 1,
      guardState: 'GUARDING',
      floatPhase: ((def.x * 17 + def.y * 31) % 1000) / 1000 * (Math.PI * 2),
      bounceInitialized: false,
    };

    this.entityStates.set(sprite, state);

    // Initial physics setup per behavior
    if (state.behavior === 'stationary') {
      sprite.setImmovable(true);
      if (sprite.body) {
        sprite.setVelocity(0, 0);
      }
    } else if (state.behavior === 'bounce') {
      sprite.setBounce(1, 1);
      sprite.setCollideWorldBounds(true);
    }
  }

  /**
   * Remove destroyed sprite from state tracker.
   */
  public unregisterEntity(sprite: Phaser.Physics.Arcade.Sprite): void {
    this.entityStates.delete(sprite);
  }

  /**
   * Update all registered entities according to their configured behavior.
   */
  public update(ctx: BehaviorContext): void {
    for (const [sprite, state] of this.entityStates.entries()) {
      if (!sprite || !sprite.active || !sprite.body) {
        this.entityStates.delete(sprite);
        continue;
      }

      this.executeBehavior(sprite, state, ctx);
    }
  }

  /**
   * Deterministic behavior execution dispatcher.
   */
  private executeBehavior(
    sprite: Phaser.Physics.Arcade.Sprite,
    state: EntityRuntimeState,
    ctx: BehaviorContext
  ): void {
    const { time, player, scene, enemyBulletsGroup } = ctx;
    const body = sprite.body as Phaser.Physics.Arcade.Body;

    switch (state.behavior) {
      case 'stationary': {
        sprite.setVelocity(0, 0);
        body.setImmovable(true);
        break;
      }

      case 'bounce': {
        if (!state.bounceInitialized) {
          sprite.setBounce(1, 1);
          sprite.setCollideWorldBounds(true);
          // Deterministic initial trajectory angle
          const angle = ((state.originX * 13 + state.originY * 7) % 360) * (Math.PI / 180);
          const spd = Math.max(80, state.speed);
          sprite.setVelocity(Math.cos(angle) * spd, Math.sin(angle) * spd);
          state.bounceInitialized = true;
        } else {
          // Prevent physics velocity decay after multiple collisions
          const targetSpeed = Math.max(80, state.speed);
          const currentSpeed = body.velocity.length();
          if (currentSpeed > 0 && Math.abs(currentSpeed - targetSpeed) > 10) {
            const factor = targetSpeed / currentSpeed;
            sprite.setVelocity(body.velocity.x * factor, body.velocity.y * factor);
          } else if (currentSpeed === 0) {
            // Unstick if stuck in corner
            const randAngle = ((time * 3) % 360) * (Math.PI / 180);
            sprite.setVelocity(Math.cos(randAngle) * targetSpeed, Math.sin(randAngle) * targetSpeed);
          }
        }
        break;
      }

      case 'float': {
        // Smooth deterministic vertical hover oscillation around spawn Y
        const hoverOffset = Math.sin((time / 1000) * 2.8 + state.floatPhase) * 18;
        const targetY = state.originY + hoverOffset;
        const vy = (targetY - sprite.y) * 5;
        const clampedVy = Phaser.Math.Clamp(vy, -state.speed, state.speed);
        sprite.setVelocity(0, clampedVy);
        break;
      }

      case 'patrol': {
        const minX = state.originX - state.patrolRadius;
        const maxX = state.originX + state.patrolRadius;

        // Turn around at patrol boundaries
        if (sprite.x >= maxX) {
          state.patrolDirection = -1;
        } else if (sprite.x <= minX) {
          state.patrolDirection = 1;
        }

        // Turn around if hitting an obstacle
        if (body.blocked.left || body.touching.left) {
          state.patrolDirection = 1;
        } else if (body.blocked.right || body.touching.right) {
          state.patrolDirection = -1;
        }

        sprite.setVelocityX(state.patrolDirection * state.speed);
        break;
      }

      case 'chase': {
        const dist = Phaser.Math.Distance.Between(sprite.x, sprite.y, player.x, player.y);
        if (dist <= state.detectionRadius) {
          const angle = Phaser.Math.Angle.Between(sprite.x, sprite.y, player.x, player.y);
          sprite.setVelocity(Math.cos(angle) * state.speed, Math.sin(angle) * state.speed);
        } else {
          // Decelerate smoothly when player escapes sensor
          sprite.setVelocity(body.velocity.x * 0.9, body.velocity.y * 0.9);
        }
        break;
      }

      case 'flee': {
        const dist = Phaser.Math.Distance.Between(sprite.x, sprite.y, player.x, player.y);
        if (dist <= state.detectionRadius) {
          // Move directly away from player
          const angle = Phaser.Math.Angle.Between(player.x, player.y, sprite.x, sprite.y);
          sprite.setVelocity(Math.cos(angle) * state.speed, Math.sin(angle) * state.speed);
        } else if (dist > state.detectionRadius * 1.3) {
          // Safe distance reached, slow to idle
          sprite.setVelocity(body.velocity.x * 0.85, body.velocity.y * 0.85);
        }
        break;
      }

      case 'guard': {
        const distToPlayer = Phaser.Math.Distance.Between(sprite.x, sprite.y, player.x, player.y);
        const distToOrigin = Phaser.Math.Distance.Between(sprite.x, sprite.y, state.originX, state.originY);
        const maxLeash = state.patrolRadius * 1.5;

        // Leash enforcement: Return to post if entity strays too far
        if (distToOrigin > maxLeash) {
          state.guardState = 'RETURNING';
        }

        if (state.guardState === 'RETURNING') {
          const angle = Phaser.Math.Angle.Between(sprite.x, sprite.y, state.originX, state.originY);
          sprite.setVelocity(Math.cos(angle) * state.speed, Math.sin(angle) * state.speed);
          if (distToOrigin <= 16) {
            state.guardState = 'GUARDING';
            sprite.setVelocity(0, 0);
          }
        } else if (distToPlayer <= state.detectionRadius) {
          state.guardState = 'ENGAGING';
          const angle = Phaser.Math.Angle.Between(sprite.x, sprite.y, player.x, player.y);
          sprite.setVelocity(Math.cos(angle) * state.speed, Math.sin(angle) * state.speed);
        } else if (state.guardState === 'ENGAGING') {
          // Player left detection radius, disengage and return
          state.guardState = 'RETURNING';
        } else {
          // Guarding station idle
          sprite.setVelocity(0, 0);
        }
        break;
      }

      case 'ranged_attack': {
        const dist = Phaser.Math.Distance.Between(sprite.x, sprite.y, player.x, player.y);
        const idealMin = 100;
        const idealMax = Math.min(260, state.detectionRadius * 0.9);

        // Tactical positioning (kite / maintain safe standoff distance)
        if (dist < idealMin) {
          // Back up if player is too close
          const angle = Phaser.Math.Angle.Between(player.x, player.y, sprite.x, sprite.y);
          sprite.setVelocity(Math.cos(angle) * (state.speed * 0.7), Math.sin(angle) * (state.speed * 0.7));
        } else if (dist > idealMax) {
          // Advance if player is beyond comfortable standoff range
          const angle = Phaser.Math.Angle.Between(sprite.x, sprite.y, player.x, player.y);
          sprite.setVelocity(Math.cos(angle) * (state.speed * 0.5), Math.sin(angle) * (state.speed * 0.5));
        } else {
          // In combat sweet spot: slow down to aim and shoot
          sprite.setVelocity(body.velocity.x * 0.8, body.velocity.y * 0.8);
        }

        // Fire projectile if player in detection radius and cooldown ready
        const cooldownMs = state.fireRate * 1000;
        if (dist <= state.detectionRadius && time - state.lastFiredTime > cooldownMs) {
          state.lastFiredTime = time;
          this.fireEnemyProjectile(sprite, player, state.damage, enemyBulletsGroup, scene);
        }
        break;
      }
    }
  }

  /**
   * Spawns a projectile directed from the enemy toward the player.
   */
  private fireEnemyProjectile(
    enemy: Phaser.Physics.Arcade.Sprite,
    player: Phaser.Physics.Arcade.Sprite,
    damage: number,
    enemyBulletsGroup: Phaser.Physics.Arcade.Group,
    scene: Phaser.Scene
  ): void {
    const angle = Phaser.Math.Angle.Between(enemy.x, enemy.y, player.x, player.y);
    const bullet = enemyBulletsGroup.get(enemy.x, enemy.y) as Phaser.Physics.Arcade.Sprite;

    if (bullet) {
      bullet.setActive(true);
      bullet.setVisible(true);
      bullet.setTexture('tex_enemy_bullet');
      bullet.setDisplaySize(10, 10);
      bullet.setData('damage', damage);
      bullet.setVelocity(Math.cos(angle) * 300, Math.sin(angle) * 300);

      // Auto-cleanup after 2000ms
      scene.time.delayedCall(2000, () => {
        if (bullet && bullet.active) {
          bullet.destroy();
        }
      });
    }
  }
}
