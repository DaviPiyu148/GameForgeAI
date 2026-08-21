import Phaser from 'phaser';
import type { GameDSL, GameState, PlaytestSummary } from './types';
import { generateProceduralTextures } from './textures';
import { RuleEngine } from './rules';
import { generateProceduralLayout } from './procedural';
import { TelemetryTracker } from './telemetry';
import { EntityBehaviorSystem } from './behaviors';

export interface GameSceneData {
  dsl: GameDSL;
  seed?: number;
  onStateChange?: (state: GameState, score: number, health: number) => void;
  onPlaytestComplete?: (summary: PlaytestSummary) => void;
}

export class GameScene extends Phaser.Scene {
  private dsl!: GameDSL;
  private seed!: number;
  private ruleEngine!: RuleEngine;
  private telemetry = new TelemetryTracker();
  private behaviorSystem = new EntityBehaviorSystem();
  private onStateChange?: (state: GameState, score: number, health: number) => void;
  private onPlaytestComplete?: (summary: PlaytestSummary) => void;

  // Game state
  private gameState: GameState = 'READY';
  private score: number = 0;
  private health: number = 100;
  private maxHealth: number = 100;
  private stamina: number = 100;
  private maxStamina: number = 100;
  private playerSpeed: number = 250;
  private dashCooldownTimer: number = 0;
  private lastFiredTime: number = 0;
  private lastDamageTime: number = 0;
  private damageCooldownMs: number = 500;
  private currentWave: number = 1;
  private maxWaves: number = 3;
  private survivalTimer: number = 0;
  private lastSurvivalCheckedSecond: number = 0;

  // Physics objects
  private player!: Phaser.Physics.Arcade.Sprite;
  private platformsGroup!: Phaser.Physics.Arcade.StaticGroup;
  private collectiblesGroup!: Phaser.Physics.Arcade.Group;
  private enemiesGroup!: Phaser.Physics.Arcade.Group;
  private hazardsGroup!: Phaser.Physics.Arcade.StaticGroup;
  private bulletsGroup!: Phaser.Physics.Arcade.Group;
  private enemyBulletsGroup!: Phaser.Physics.Arcade.Group;

  // Controls
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private wasdKeys!: {
    W: Phaser.Input.Keyboard.Key;
    A: Phaser.Input.Keyboard.Key;
    S: Phaser.Input.Keyboard.Key;
    D: Phaser.Input.Keyboard.Key;
    SPACE: Phaser.Input.Keyboard.Key;
    SHIFT: Phaser.Input.Keyboard.Key;
    F: Phaser.Input.Keyboard.Key;
  };

  // HUD
  private hudContainer!: Phaser.GameObjects.Container;
  private hpLabel!: Phaser.GameObjects.Text;
  private healthBarBg!: Phaser.GameObjects.Rectangle;
  private healthBarFill!: Phaser.GameObjects.Rectangle;
  private staminaBarFill!: Phaser.GameObjects.Rectangle;
  private scoreText!: Phaser.GameObjects.Text;
  private stageText!: Phaser.GameObjects.Text;
  private waveText!: Phaser.GameObjects.Text;
  private objectiveText!: Phaser.GameObjects.Text;
  private bannerText!: Phaser.GameObjects.Text;

  // Multi-Level Campaign Support
  private currentLevelIndex: number = 0;
  private totalLevels: number = 1;

  constructor() {
    super({ key: 'GameScene' });
  }

  public init(data: GameSceneData): void {
    this.dsl = data.dsl;
    this.seed = data.seed ?? 18492031;
    this.ruleEngine = new RuleEngine(this.dsl.rules);
    this.onStateChange = data.onStateChange;
    this.onPlaytestComplete = data.onPlaytestComplete;

    this.currentLevelIndex = 0;
    this.totalLevels = (this.dsl.levels && this.dsl.levels.length > 0) ? this.dsl.levels.length : 1;

    this.score = 0;
    this.maxHealth = this.dsl.player.max_health || 100;
    this.health = this.maxHealth;
    this.maxStamina = this.dsl.player.stamina || 100;
    this.stamina = this.maxStamina;
    this.playerSpeed = this.dsl.player.speed || 250;
    this.dashCooldownTimer = 0;
    this.lastFiredTime = 0;
    this.lastDamageTime = 0;
    this.damageCooldownMs = 500;
    this.currentWave = 1;
    this.maxWaves = this.dsl.world.wave_count || 3;
    this.survivalTimer = 0;
    this.lastSurvivalCheckedSecond = 0;
    this.gameState = 'PLAYING';

    this.telemetry.startSession();
  }

  public create(): void {
    const worldW = this.dsl.world.width;
    const worldH = this.dsl.world.height;
    const isPlatformer = this.dsl.metadata.archetype === 'platformer';

    // 1. Textures & Bounds
    generateProceduralTextures(this);
    this.physics.world.setBounds(0, 0, worldW, worldH);
    this.cameras.main.setBounds(0, 0, worldW, worldH);

    // Background
    const bgCol = Phaser.Display.Color.HexStringToColor(this.dsl.world.background_color || '#0a0b10').color;
    this.add.rectangle(worldW / 2, worldH / 2, worldW, worldH, bgCol);
    this.createGridOverlay(worldW, worldH);

    // 2. Physics Groups
    this.platformsGroup = this.physics.add.staticGroup();
    this.hazardsGroup = this.physics.add.staticGroup();
    this.collectiblesGroup = this.physics.add.group();
    this.enemiesGroup = this.physics.add.group();
    this.bulletsGroup = this.physics.add.group();
    this.enemyBulletsGroup = this.physics.add.group();

    // 3. Player Spawn (Respects Level 1 spawn if multi-stage)
    const activeLevel = (this.dsl.levels && this.dsl.levels.length > 0) ? this.dsl.levels[0] : null;
    const initialSpawnX = activeLevel?.spawn_x ?? this.dsl.player.spawn_x ?? 400;
    const initialSpawnY = activeLevel?.spawn_y ?? this.dsl.player.spawn_y ?? 300;

    this.player = this.physics.add.sprite(initialSpawnX, initialSpawnY, 'tex_player');
    this.player.setDisplaySize(this.dsl.player.width, this.dsl.player.height);
    this.player.setCollideWorldBounds(true);

    if (isPlatformer) {
      this.player.setGravityY(this.dsl.world.gravity || 800);
    } else {
      (this.player.body as Phaser.Physics.Arcade.Body).setAllowGravity(false);
    }

    this.player.setDamping(true);
    this.player.setDrag(isPlatformer ? 0.001 : 0.0005);

    // Camera follow player
    this.cameras.main.startFollow(this.player, true, 0.08, 0.08);

    // 4. Populate Entities & Procedural Layout
    const initialEntities = activeLevel?.entities || this.dsl.entities || [];
    this.populateEntities(initialEntities);
    if (!activeLevel) {
      const layout = generateProceduralLayout(this.dsl, this.seed);
      this.populateEntities(layout.entities);
    }

    // 5. Collisions & Overlaps
    this.physics.add.collider(this.player, this.platformsGroup);
    this.physics.add.collider(this.enemiesGroup, this.platformsGroup);
    this.physics.add.overlap(this.player, this.collectiblesGroup, this.handleCollect, undefined, this);
    this.physics.add.overlap(this.player, this.enemiesGroup, this.handlePlayerEnemyCollision, undefined, this);
    this.physics.add.overlap(this.player, this.hazardsGroup, this.handleHazardTouch, undefined, this);
    this.physics.add.overlap(this.player, this.enemyBulletsGroup, this.handlePlayerEnemyBulletCollision, undefined, this);
    this.physics.add.overlap(this.bulletsGroup, this.enemiesGroup, this.handleBulletEnemyCollision, undefined, this);
    this.physics.add.collider(this.bulletsGroup, this.platformsGroup, (b) => b.destroy());
    this.physics.add.collider(this.enemyBulletsGroup, this.platformsGroup, (b) => b.destroy());

    // 6. Keyboard & Mouse Controls
    if (this.input.keyboard) {
      this.cursors = this.input.keyboard.createCursorKeys();
      this.wasdKeys = {
        W: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.W),
        A: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.A),
        S: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.S),
        D: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.D),
        SPACE: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE),
        SHIFT: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SHIFT),
        F: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.F),
      };

      // Add key captures for browser scrolling prevention during gameplay
      this.input.keyboard.addCapture([
        Phaser.Input.Keyboard.KeyCodes.SPACE,
        Phaser.Input.Keyboard.KeyCodes.UP,
        Phaser.Input.Keyboard.KeyCodes.DOWN,
        Phaser.Input.Keyboard.KeyCodes.LEFT,
        Phaser.Input.Keyboard.KeyCodes.RIGHT,
      ]);
    }

    // 7. Heads-Up Display (HUD)
    this.createHUD();

    // 8. Trigger Initial Wave Rule Event
    this.ruleEngine.trigger('on_wave_start', this.getGameContext(), { wave: 1 });

    // Notify state
    if (this.onStateChange) {
      this.onStateChange(this.gameState, this.score, this.health);
    }
  }

  private populateEntities(entities: any[]): void {
    for (const ent of entities) {
      if (ent.type === 'platform') {
        const plat = this.platformsGroup.create(ent.x, ent.y, 'tex_platform') as Phaser.Physics.Arcade.Sprite;
        plat.setDisplaySize(ent.width, ent.height);
        plat.refreshBody();
      } else if (ent.type === 'hazard') {
        const haz = this.hazardsGroup.create(ent.x, ent.y, 'tex_hazard') as Phaser.Physics.Arcade.Sprite;
        haz.setDisplaySize(ent.width, ent.height);
        haz.setData('damage', ent.damage || 20);
        haz.refreshBody();
      } else if (ent.type === 'collectible') {
        const col = this.collectiblesGroup.create(ent.x, ent.y, 'tex_collectible') as Phaser.Physics.Arcade.Sprite;
        col.setDisplaySize(ent.width, ent.height);
        col.setData('points', ent.points || 50);
        col.setData('id', ent.id);
        (col.body as Phaser.Physics.Arcade.Body).setAllowGravity(false);
        if (ent.behavior === 'float') {
          this.tweens.add({
            targets: col,
            y: ent.y - 8,
            duration: 1200,
            yoyo: true,
            repeat: -1,
            ease: 'Sine.easeInOut',
          });
        }
      } else if (ent.type === 'enemy') {
        const enemy = this.enemiesGroup.create(ent.x, ent.y, 'tex_enemy') as Phaser.Physics.Arcade.Sprite;
        enemy.setDisplaySize(ent.width, ent.height);
        enemy.setData('id', ent.id);
        enemy.setData('speed', ent.speed || 100);
        enemy.setData('health', ent.health || 30);
        enemy.setData('damage', ent.damage || 15);
        enemy.setData('behavior', ent.behavior || 'patrol');
        enemy.setData('loot_drop', ent.loot_drop || null);
        enemy.setData('originX', ent.x);
        enemy.setCollideWorldBounds(true);

        // Register entity with centralized behavior system
        this.behaviorSystem.registerEntity(enemy, ent);
      }
    }
  }

  public update(time: number, delta: number): void {
    if (this.gameState !== 'PLAYING') return;

    this.survivalTimer += delta / 1000;
    this.dashCooldownTimer = Math.max(0, this.dashCooldownTimer - delta / 1000);
    this.stamina = Math.min(this.maxStamina, this.stamina + (delta / 1000) * 15);

    // Periodic survival/time-limit check
    const currentSec = Math.floor(this.survivalTimer);
    if (currentSec > this.lastSurvivalCheckedSecond) {
      this.lastSurvivalCheckedSecond = currentSec;
      this.ruleEngine.trigger('on_time_limit', this.getGameContext(), { time: currentSec });
    }

    const isPlatformer = this.dsl.metadata.archetype === 'platformer';
    let vx = 0;
    let vy = 0;

    const leftDown = !!(this.cursors?.left?.isDown || this.wasdKeys?.A?.isDown);
    const rightDown = !!(this.cursors?.right?.isDown || this.wasdKeys?.D?.isDown);
    const upDown = !!(this.cursors?.up?.isDown || this.wasdKeys?.W?.isDown);
    const downDown = !!(this.cursors?.down?.isDown || this.wasdKeys?.S?.isDown);
    const spaceDown = !!(this.cursors?.space?.isDown || this.wasdKeys?.SPACE?.isDown);
    const shiftDown = !!(this.cursors?.shift?.isDown || this.wasdKeys?.SHIFT?.isDown);
    const fDown = !!(this.wasdKeys?.F?.isDown);

    // Directional Input
    if (leftDown) vx -= 1;
    if (rightDown) vx += 1;

    // Unified Dash Execution
    let currentSpd = this.playerSpeed;
    const wantsDash = spaceDown || shiftDown;
    if (wantsDash && this.dashCooldownTimer <= 0 && this.stamina >= 30) {
      this.dashCooldownTimer = this.dsl.player.dash_cooldown || 1.2;
      this.stamina -= 30;
      currentSpd = this.dsl.player.dash_speed || 600;
      this.cameras.main.shake(80, 0.004);
      this.spawnDashParticles(this.player.x, this.player.y);
      this.telemetry.record('OBJECTIVE_COMPLETED', { action: 'dash' });
      this.ruleEngine.trigger('on_dash', this.getGameContext(), { speed: currentSpd });
    }

    if (isPlatformer) {
      if (upDown && (this.player.body as Phaser.Physics.Arcade.Body).touching.down) {
        this.player.setVelocityY(-(this.dsl.player.jump_power || 500));
      }
      this.player.setVelocityX(vx * currentSpd);
    } else {
      if (upDown) vy -= 1;
      if (downDown) vy += 1;

      if (vx !== 0 && vy !== 0) {
        vx *= 0.7071;
        vy *= 0.7071;
      }

      this.player.setVelocity(vx * currentSpd, vy * currentSpd);
    }

    // Shooting Action (Honors player.attack_type and player.attack_cooldown)
    const attackType = this.dsl.player.attack_type ?? 'ranged';
    const cooldownMs = (this.dsl.player.attack_cooldown ?? 0.25) * 1000;
    if (attackType === 'ranged' && (this.input.activePointer.isDown || fDown) && time - this.lastFiredTime > cooldownMs) {
      this.fireBullet();
      this.lastFiredTime = time;
    }

    // Update centralized entity behaviors
    this.behaviorSystem.update({
      time,
      delta,
      player: this.player,
      scene: this,
      enemyBulletsGroup: this.enemyBulletsGroup,
    });

    // Update HUD
    this.updateHUD();
  }

  private fireBullet(): void {
    const ptr = this.input.activePointer;
    const targetX = ptr.worldX || this.player.x + 100;
    const targetY = ptr.worldY || this.player.y;
    const angle = Phaser.Math.Angle.Between(this.player.x, this.player.y, targetX, targetY);

    const bullet = this.bulletsGroup.get(this.player.x, this.player.y) as Phaser.Physics.Arcade.Sprite;
    if (bullet) {
      bullet.setActive(true);
      bullet.setVisible(true);
      bullet.setDisplaySize(10, 10);
      bullet.setVelocity(Math.cos(angle) * 500, Math.sin(angle) * 500);

      this.time.delayedCall(1500, () => {
        if (bullet.active) bullet.destroy();
      });
    }
  }

  private handleCollect(_p: any, colObj: any): void {
    const col = colObj as Phaser.Physics.Arcade.Sprite;
    const pts = col.getData('points') || 50;
    const entId = col.getData('id') || '';
    this.score += pts;
    this.spawnFloatingText(col.x, col.y, `+${pts}`, '#00ffcc');
    this.telemetry.record('ITEM_COLLECTED', { points: pts });
    this.telemetry.record('SCORE_CHANGED', { score: this.score });

    // Rule triggers
    this.ruleEngine.trigger('on_collect', this.getGameContext(), { amount: pts, id: entId });
    if (entId === 'goal_flag' || entId.includes('goal')) {
      this.ruleEngine.trigger('on_reach_goal', this.getGameContext(), { goal_id: entId });
    }

    col.destroy();

    // Check stage progression / win condition
    if (this.enemiesGroup.countActive() === 0 && this.collectiblesGroup.countActive() === 0) {
      this.checkStageProgression();
    }
  }

  private handlePlayerEnemyCollision(_p: any, enemyObj: any): void {
    const now = this.time.now;
    if (now - this.lastDamageTime < this.damageCooldownMs) {
      return; // Invincibility frame window active
    }
    this.lastDamageTime = now;

    const enemy = enemyObj as Phaser.Physics.Arcade.Sprite;
    const dmg = enemy.getData('damage') || 15;
    this.health = Math.max(0, this.health - dmg);

    // Visual invincibility flash
    this.player.setAlpha(0.5);
    this.time.delayedCall(this.damageCooldownMs, () => {
      if (this.player && this.player.active) {
        this.player.setAlpha(1.0);
      }
    });

    this.cameras.main.shake(120, 0.008);
    this.spawnFloatingText(this.player.x, this.player.y, `-${dmg} HP`, '#ff0055');
    this.telemetry.record('PLAYER_DAMAGE', { damage: dmg });
    this.ruleEngine.trigger('on_collide_enemy', this.getGameContext(), { damage: dmg });

    // Knockback
    const angle = Phaser.Math.Angle.Between(enemy.x, enemy.y, this.player.x, this.player.y);
    this.player.setVelocity(Math.cos(angle) * 350, Math.sin(angle) * 350);

    if (this.health <= 0) {
      this.ruleEngine.trigger('on_player_death', this.getGameContext(), { score: this.score });
      this.triggerEndGame('LOST');
    }
  }

  private handlePlayerEnemyBulletCollision(_p: any, bulletObj: any): void {
    const bullet = bulletObj as Phaser.Physics.Arcade.Sprite;
    const dmg = bullet.getData('damage') || 15;
    bullet.destroy();

    const now = this.time.now;
    if (now - this.lastDamageTime < this.damageCooldownMs) {
      return; // Invincibility frame window active
    }
    this.lastDamageTime = now;

    this.health = Math.max(0, this.health - dmg);

    // Visual invincibility flash
    this.player.setAlpha(0.5);
    this.time.delayedCall(this.damageCooldownMs, () => {
      if (this.player && this.player.active) {
        this.player.setAlpha(1.0);
      }
    });

    this.cameras.main.shake(130, 0.009);
    this.spawnFloatingText(this.player.x, this.player.y, `-${dmg} HP`, '#ff0055');
    this.telemetry.record('PLAYER_DAMAGE', { damage: dmg, ranged: true });
    this.ruleEngine.trigger('on_collide_enemy', this.getGameContext(), { damage: dmg });

    if (this.health <= 0) {
      this.ruleEngine.trigger('on_player_death', this.getGameContext(), { score: this.score });
      this.triggerEndGame('LOST');
    }
  }

  private handleHazardTouch(_p: any, hazObj: any): void {
    const now = this.time.now;
    if (now - this.lastDamageTime < this.damageCooldownMs) {
      return; // Invincibility frame window active
    }
    this.lastDamageTime = now;

    const haz = hazObj as Phaser.Physics.Arcade.Sprite;
    const dmg = haz.getData('damage') || 20;
    this.health = Math.max(0, this.health - dmg);

    // Visual invincibility flash
    this.player.setAlpha(0.5);
    this.time.delayedCall(this.damageCooldownMs, () => {
      if (this.player && this.player.active) {
        this.player.setAlpha(1.0);
      }
    });

    this.cameras.main.shake(140, 0.01);
    this.spawnFloatingText(this.player.x, this.player.y, `-${dmg} HP`, '#ffaa00');
    this.telemetry.record('PLAYER_DAMAGE', { damage: dmg, hazard: true });
    this.ruleEngine.trigger('on_hazard_touch', this.getGameContext(), { damage: dmg });

    if (this.health <= 0) {
      this.ruleEngine.trigger('on_player_death', this.getGameContext(), { score: this.score });
      this.triggerEndGame('LOST');
    }
  }

  private handleBulletEnemyCollision(bulletObj: any, enemyObj: any): void {
    const bullet = bulletObj as Phaser.Physics.Arcade.Sprite;
    const enemy = enemyObj as Phaser.Physics.Arcade.Sprite;
    bullet.destroy();

    const attackDmg = this.dsl.player.attack_damage ?? 25;
    const hp = (enemy.getData('health') || 30) - attackDmg;
    enemy.setData('health', hp);
    this.spawnFloatingText(enemy.x, enemy.y, `-${attackDmg}`, '#ffea00');

    if (hp <= 0) {
      this.spawnParticleBurst(enemy.x, enemy.y, '#ff0055');
      this.telemetry.record('ENEMY_DEFEATED', { damageDealt: attackDmg });
      this.score += 100;
      this.telemetry.record('SCORE_CHANGED', { score: this.score });

      // Trigger enemy defeat rule
      this.ruleEngine.trigger('on_enemy_defeat', this.getGameContext(), { enemy_id: enemy.getData('id') });

      // Entity Loot Drop Mechanics
      const lootDrop = enemy.getData('loot_drop');
      if (lootDrop === 'health') {
        this.health = Math.min(this.maxHealth, this.health + 20);
        this.spawnFloatingText(enemy.x, enemy.y - 20, '+20 HP', '#00ff66');
      } else if (lootDrop === 'points') {
        this.score += 100;
        this.spawnFloatingText(enemy.x, enemy.y - 20, '+100 PTS', '#ffea00');
      } else if (lootDrop === 'powerup') {
        this.applySpeedBoost(4000, 1.4);
        this.spawnFloatingText(enemy.x, enemy.y - 20, 'SPEED BOOST!', '#00f0ff');
      }

      // Unregister from behavior system
      this.behaviorSystem.unregisterEntity(enemy);
      enemy.destroy();

      if (this.enemiesGroup.countActive() === 0 && this.collectiblesGroup.countActive() === 0) {
        this.checkStageProgression();
      }
    }
  }

  private advanceToNextLevel(): void {
    if (this.currentLevelIndex >= this.totalLevels - 1) {
      this.triggerEndGame('WON');
      return;
    }

    this.currentLevelIndex += 1;
    const nextLevel = this.dsl.levels?.[this.currentLevelIndex];
    const stageTitle = nextLevel?.title || `Stage ${this.currentLevelIndex + 1}`;

    this.spawnFloatingText(this.player.x, this.player.y - 40, `★ STAGE COMPLETE! ★`, '#00ff66');
    this.spawnFloatingText(this.player.x, this.player.y - 15, `Entering: ${stageTitle}`, '#00f0ff');
    this.cameras.main.flash(300, 0, 240, 255);

    // Clear current stage entities
    this.enemiesGroup.clear(true, true);
    this.collectiblesGroup.clear(true, true);
    this.hazardsGroup.clear(true, true);
    this.platformsGroup.clear(true, true);
    this.bulletsGroup.clear(true, true);
    this.enemyBulletsGroup.clear(true, true);

    // Respawn player at stage spawn
    const spawnX = nextLevel?.spawn_x ?? this.dsl.player.spawn_x ?? 400;
    const spawnY = nextLevel?.spawn_y ?? this.dsl.player.spawn_y ?? 300;
    this.player.setPosition(spawnX, spawnY);
    this.player.setVelocity(0, 0);

    // Spawn new stage entities
    if (nextLevel?.entities) {
      this.populateEntities(nextLevel.entities);
    }

    this.currentWave = 1;
    this.maxWaves = nextLevel?.world?.wave_count || this.dsl.world.wave_count || 1;

    this.telemetry.record('OBJECTIVE_COMPLETED', { stage: this.currentLevelIndex + 1, title: stageTitle });

    // Update HUD
    if (this.stageText) {
      this.stageText.setText(`STAGE: ${this.currentLevelIndex + 1}/${this.totalLevels}`);
    }
    if (this.objectiveText) {
      const stageGoal = nextLevel?.objective?.description || this.dsl.design_spec?.primary_objective || 'SURVIVE';
      this.objectiveText.setText(`GOAL: ${stageGoal}`);
    }
  }

  private checkStageProgression(): void {
    if (this.dsl.levels && this.dsl.levels.length > 0 && this.currentLevelIndex < this.totalLevels - 1) {
      this.advanceToNextLevel();
    } else if (this.currentWave < this.maxWaves) {
      this.nextWave();
    } else {
      this.triggerEndGame('WON');
    }
  }

  private nextWave(): void {
    this.currentWave += 1;
    this.spawnFloatingText(this.player.x, this.player.y - 40, `WAVE ${this.currentWave}!`, '#00f0ff');
    this.telemetry.record('OBJECTIVE_COMPLETED', { wave: this.currentWave });
    this.ruleEngine.trigger('on_wave_start', this.getGameContext(), { wave: this.currentWave });

    const waveBehaviors = ['chase', 'patrol', 'bounce', 'ranged_attack', 'guard', 'flee'] as const;

    // Spawn next wave enemies
    for (let i = 0; i < this.currentWave * 2; i++) {
      const x = Phaser.Math.Between(80, this.dsl.world.width - 80);
      const y = Phaser.Math.Between(80, this.dsl.world.height - 80);
      const enemy = this.enemiesGroup.create(x, y, 'tex_enemy') as Phaser.Physics.Arcade.Sprite;
      enemy.setDisplaySize(28, 28);
      const behavior = waveBehaviors[i % waveBehaviors.length];
      const hp = 30 + this.currentWave * 10;
      const dmg = 15 + this.currentWave * 2;
      const spd = 120 + this.currentWave * 15;

      enemy.setData('id', `wave_${this.currentWave}_enemy_${i}`);
      enemy.setData('health', hp);
      enemy.setData('damage', dmg);
      enemy.setData('speed', spd);
      enemy.setData('behavior', behavior);
      enemy.setData('originX', x);
      enemy.setCollideWorldBounds(true);

      // Register wave enemy with behavior system
      this.behaviorSystem.registerEntity(enemy, {
        id: `wave_${this.currentWave}_enemy_${i}`,
        type: 'enemy',
        x,
        y,
        width: 28,
        height: 28,
        speed: spd,
        health: hp,
        behavior,
        damage: dmg,
        fire_rate: Math.max(0.8, 2.0 - this.currentWave * 0.2),
        patrol_radius: 160,
        detection_radius: 280,
        color: '#ff0055',
        points: 100,
      });
    }
  }

  private triggerEndGame(outcome: 'WON' | 'LOST', customMessage?: string): void {
    if (this.gameState === 'WON' || this.gameState === 'LOST') return;
    this.gameState = outcome;
    const defaultMessage = outcome === 'WON' ? '★ PROTOTYPE CLEARED ★' : '✖ MISSION FAILED ✖';
    this.bannerText.setText(customMessage && customMessage.trim() ? customMessage.trim() : defaultMessage);
    this.bannerText.setColor(outcome === 'WON' ? '#00ff66' : '#ff0055');
    this.bannerText.setVisible(true);

    this.telemetry.record(outcome === 'WON' ? 'GAME_WON' : 'GAME_LOST');
    const summary = this.telemetry.endSession(outcome);

    if (this.onStateChange) {
      this.onStateChange(this.gameState, this.score, this.health);
    }
    if (this.onPlaytestComplete) {
      this.onPlaytestComplete(summary);
    }
  }

  private createHUD(): void {
    this.hudContainer = this.add.container(16, 16).setScrollFactor(0);

    const ui = this.dsl.ui;
    const showHealth = ui?.show_health ?? true;
    const showScore = ui?.show_score ?? true;
    const showStamina = ui?.show_stamina ?? true;
    const showWave = ui?.show_wave ?? true;
    const showObjectives = ui?.show_objectives ?? true;

    // Health Bar
    this.healthBarBg = this.add.rectangle(70, 10, 120, 14, 0x222233).setOrigin(0, 0.5);
    this.healthBarFill = this.add.rectangle(70, 10, 120, 12, 0x00ff66).setOrigin(0, 0.5);
    this.hpLabel = this.add.text(0, 2, 'HEALTH', { fontSize: '11px', color: '#8899aa', fontFamily: 'monospace' });

    this.healthBarBg.setVisible(showHealth);
    this.healthBarFill.setVisible(showHealth);
    this.hpLabel.setVisible(showHealth);

    // Stamina Bar
    this.staminaBarFill = this.add.rectangle(70, 24, 120, 6, 0x00f0ff).setOrigin(0, 0.5);
    this.staminaBarFill.setVisible(showStamina);

    // Score & Stage/Wave Text
    this.scoreText = this.add.text(0, 36, `SCORE: 0`, { fontSize: '13px', color: '#ffea00', fontFamily: 'monospace', fontStyle: 'bold' });
    this.scoreText.setVisible(showScore);

    let nextY = 54;
    if (this.totalLevels > 1) {
      this.stageText = this.add.text(0, nextY, `STAGE: 1/${this.totalLevels}`, { fontSize: '12px', color: '#ff00ff', fontFamily: 'monospace', fontStyle: 'bold' });
      nextY += 16;
    }

    this.waveText = this.add.text(0, nextY, `WAVE: 1/${this.maxWaves}`, { fontSize: '12px', color: '#00f0ff', fontFamily: 'monospace' });
    this.waveText.setVisible(showWave);
    nextY += 16;

    // Objective / Status Text
    const primaryGoal = this.dsl.design_spec?.primary_objective || ui?.status_text || 'PLAY PROTOTYPE';
    this.objectiveText = this.add.text(0, nextY, `GOAL: ${primaryGoal}`, { fontSize: '11px', color: '#a0aec0', fontFamily: 'monospace' });
    this.objectiveText.setVisible(showObjectives);

    // Status Banner
    this.bannerText = this.add.text(
      (this.cameras.main.width - 32) / 2,
      this.cameras.main.height / 2 - 32,
      '',
      { fontSize: '24px', color: '#00ff66', fontFamily: 'monospace', fontStyle: 'bold' }
    ).setOrigin(0.5).setVisible(false);

    const hudElements = [
      this.healthBarBg,
      this.healthBarFill,
      this.staminaBarFill,
      this.hpLabel,
      this.scoreText,
      this.waveText,
      this.objectiveText,
      this.bannerText,
    ];
    if (this.stageText) {
      hudElements.push(this.stageText);
    }

    this.hudContainer.add(hudElements);
  }

  private updateHUD(): void {
    const hpRatio = Math.max(0, this.health / this.maxHealth);
    this.healthBarFill.width = 120 * hpRatio;
    this.healthBarFill.fillColor = hpRatio > 0.4 ? 0x00ff66 : 0xff0055;

    const stamRatio = Math.max(0, this.stamina / this.maxStamina);
    this.staminaBarFill.width = 120 * stamRatio;

    this.scoreText.setText(`SCORE: ${this.score}`);
    this.waveText.setText(`WAVE: ${this.currentWave}/${this.maxWaves}`);
  }

  private spawnFloatingText(x: number, y: number, text: string, color: string): void {
    const txt = this.add.text(x, y, text, { fontSize: '14px', color, fontStyle: 'bold', fontFamily: 'monospace' }).setOrigin(0.5);
    this.tweens.add({
      targets: txt,
      y: y - 25,
      alpha: 0,
      duration: 800,
      onComplete: () => txt.destroy(),
    });
  }

  private spawnDashParticles(x: number, y: number): void {
    for (let i = 0; i < 6; i++) {
      const p = this.add.circle(x, y, 4, 0x00f0ff, 0.8);
      this.tweens.add({
        targets: p,
        x: x + Phaser.Math.Between(-20, 20),
        y: y + Phaser.Math.Between(-20, 20),
        alpha: 0,
        scale: 0.2,
        duration: 400,
        onComplete: () => p.destroy(),
      });
    }
  }

  private spawnParticleBurst(x: number, y: number, colorHex: string): void {
    const col = Phaser.Display.Color.HexStringToColor(colorHex).color;
    for (let i = 0; i < 10; i++) {
      const p = this.add.circle(x, y, 3, col, 1);
      const angle = Phaser.Math.FloatBetween(0, Math.PI * 2);
      const spd = Phaser.Math.Between(40, 120);
      this.tweens.add({
        targets: p,
        x: x + Math.cos(angle) * spd,
        y: y + Math.sin(angle) * spd,
        alpha: 0,
        scale: 0.1,
        duration: 600,
        onComplete: () => p.destroy(),
      });
    }
  }

  private createGridOverlay(w: number, h: number): void {
    const graphics = this.add.graphics();
    graphics.lineStyle(1, 0xffffff, 0.04);
    for (let x = 0; x < w; x += 40) {
      graphics.lineBetween(x, 0, x, h);
    }
    for (let y = 0; y < h; y += 40) {
      graphics.lineBetween(0, y, w, y);
    }
  }

  private applySpeedBoost(durationMs: number, multiplier: number): void {
    this.playerSpeed *= multiplier;
    this.time.delayedCall(durationMs, () => {
      this.playerSpeed /= multiplier;
    });
  }

  private getGameContext() {
    return {
      score: this.score,
      health: this.health,
      maxHealth: this.maxHealth,
      playerSpeed: this.playerSpeed,
      isWon: this.gameState === 'WON',
      isLost: this.gameState === 'LOST',
      addScore: (pts: number) => {
        this.score += pts;
        this.ruleEngine.trigger('on_score_target', this.getGameContext(), { score: this.score });
      },
      damagePlayer: (dmg: number) => {
        this.health = Math.max(0, this.health - dmg);
        if (this.health <= 0) {
          this.ruleEngine.trigger('on_player_death', this.getGameContext(), { score: this.score });
          this.triggerEndGame('LOST');
        }
      },
      healPlayer: (amount: number) => {
        this.health = Math.min(this.maxHealth, this.health + amount);
      },
      setGameWon: (reason: string) => {
        this.triggerEndGame('WON', reason);
      },
      setGameLost: (reason: string) => {
        this.triggerEndGame('LOST', reason);
      },
      applySpeedBoost: (durationMs: number, multiplier: number) => {
        this.applySpeedBoost(durationMs, multiplier);
      },
      spawnBonusEntity: () => {
        const col = this.collectiblesGroup.create(
          Phaser.Math.Between(100, this.dsl.world.width - 100),
          Phaser.Math.Between(100, this.dsl.world.height - 100),
          'tex_collectible'
        ) as Phaser.Physics.Arcade.Sprite;
        col.setDisplaySize(20, 20);
        col.setData('points', 75);
        (col.body as Phaser.Physics.Arcade.Body).setAllowGravity(false);
      },
      spawnWave: (_waveNum?: number) => {
        this.nextWave();
      },
      grantPowerup: (type: string) => {
        if (type === 'speed') {
          this.applySpeedBoost(5000, 1.5);
        } else if (type === 'heal') {
          this.health = Math.min(this.maxHealth, this.health + 30);
        }
        this.spawnFloatingText(this.player.x, this.player.y - 30, `POWERUP: ${type.toUpperCase()}`, '#ffea00');
        this.time.delayedCall(5000, () => {
          this.ruleEngine.trigger('on_powerup_expire', this.getGameContext(), { type });
        });
      },
      activateCheckpoint: (id: string) => {
        this.spawnFloatingText(this.player.x, this.player.y - 30, `CHECKPOINT: ${id}`, '#00ff66');
        this.ruleEngine.trigger('on_checkpoint', this.getGameContext(), { checkpoint_id: id });
      },
      spawnParticles: (colorHex?: string, _count?: number) => {
        this.spawnParticleBurst(this.player.x, this.player.y, colorHex || '#00f0ff');
      },
      knockbackTarget: (intensity?: number) => {
        const force = intensity || 300;
        this.player.setVelocityY(-force);
      },
      triggerScreenShake: (intensity?: number) => {
        this.cameras.main.shake(150, intensity || 0.01);
      },
    };
  }
}
