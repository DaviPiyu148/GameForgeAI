import Phaser from 'phaser';
import type {
  ActorDef,
  EntityDef,
  GameDSL,
  GameState,
  LevelDef,
  PlaytestSummary,
  POIDef,
  RegionDef,
  ThreatResponseUnitDef,
} from './types';
import { generateProceduralTextures } from './textures';
import { resolveVisualProfile, type RuntimeVisualProfile } from './visualProfile';
import { generateDynamicTextures } from './proceduralTextures';

import { EnvironmentSystem } from './environmentSystem';
import { VFXSystem } from './vfxSystem';
import { RuleEngine } from './rules';
import { generateProceduralLayout } from './procedural';
import { TelemetryTracker } from './telemetry';
import { EntityBehaviorSystem } from './behaviors';
import { WorldManager } from './WorldManager';
import { RegionManager } from './RegionManager';
import { VehicleManager } from './VehicleManager';
import { ActivityManager } from './ActivityManager';
import { FactionManager } from './FactionManager';
import { ThreatManager } from './ThreatManager';
import { WorldEventManager } from './WorldEventManager';
import { createPRNG } from './prng';
import {
  RuntimeConfigCompiler,
  type RuntimeGameConfig,
  type RuntimeStageConfig,
} from './RuntimeConfig';
import { RuntimeStateMachine } from './RuntimeStateMachine';
import { ObjectiveEvaluator } from './ObjectiveEvaluator';
import { WaveController } from './WaveController';
import type { ArchetypePolicy } from './ArchetypePolicy';

export interface GameSceneData {
  dsl: GameDSL;
  seed?: number;
  onStateChange?: (state: GameState, score: number, health: number) => void;
  onPlaytestComplete?: (summary: PlaytestSummary) => void;
}

export class GameScene extends Phaser.Scene {
  private dsl!: GameDSL;
  private seed!: number;
  private prng!: () => number;
  private runtimeConfig!: RuntimeGameConfig;
  private currentStageConfig!: RuntimeStageConfig;
  private archetypePolicy!: ArchetypePolicy;
  private stateMachine!: RuntimeStateMachine;
  private objectiveEvaluator!: ObjectiveEvaluator;
  private waveController?: WaveController;
  private ruleEngine!: RuleEngine;
  private telemetry = new TelemetryTracker();
  private behaviorSystem = new EntityBehaviorSystem();
  private onStateChange?: (state: GameState, score: number, health: number) => void;
  private onPlaytestComplete?: (summary: PlaytestSummary) => void;

  private compilationError?: string;
  private threatUnitCounter = 0;

  // Open World Modular Subsystems
  private worldManager: WorldManager | null = null;
  private regionManager: RegionManager | null = null;
  private vehicleManager: VehicleManager | null = null;
  private activityManager: ActivityManager | null = null;
  private factionManager: FactionManager | null = null;
  private threatManager: ThreatManager | null = null;
  private worldEventManager: WorldEventManager | null = null;
  private poisGroup!: Phaser.Physics.Arcade.StaticGroup;
  private actorsGroup!: Phaser.Physics.Arcade.Group;
  private openWorldLabelsGroup!: Phaser.GameObjects.Group;
  private eKey?: Phaser.Input.Keyboard.Key;
  private regionBannerText?: Phaser.GameObjects.Text;

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
  private lastMeleeAttackTime: number = 0;
  private lastDamageTime: number = 0;
  private damageCooldownMs: number = 500;
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
  private backgroundRect!: Phaser.GameObjects.Rectangle;
  private isTransitioning: boolean = false;

  // Boss Runtime Support (Phase 5)
  private currentBossSprite: Phaser.Physics.Arcade.Sprite | null = null;
  private bossHealthBarBg?: Phaser.GameObjects.Rectangle;
  private bossHealthBarFill?: Phaser.GameObjects.Rectangle;
  private bossLabelText?: Phaser.GameObjects.Text;

  // Visual Experience Systems
  private visualProfile!: RuntimeVisualProfile;
  private environmentSystem!: EnvironmentSystem;
  private vfxSystem!: VFXSystem;

  constructor() {
    super({ key: 'GameScene' });
  }

  public init(data: GameSceneData): void {
    this.dsl = data.dsl;
    this.seed = data.seed ?? 18492031;
    this.prng = createPRNG(this.seed);
    this.onStateChange = data.onStateChange;
    this.onPlaytestComplete = data.onPlaytestComplete;

    // Compile and validate runtime configuration
    const compilation = RuntimeConfigCompiler.compile(this.dsl, this.seed);
    if (!compilation.success || !compilation.config) {
      this.compilationError = compilation.error || 'Failed to compile runtime game configuration.';
      this.stateMachine = new RuntimeStateMachine('LOST');
      return;
    }

    this.runtimeConfig = compilation.config;
    this.currentLevelIndex = 0;
    this.totalLevels = this.runtimeConfig.stages.length;
    this.currentStageConfig = this.runtimeConfig.stages[0];
    this.archetypePolicy = this.runtimeConfig.archetypePolicy;

    this.stateMachine = new RuntimeStateMachine('LOADING');
    this.ruleEngine = new RuleEngine(this.currentStageConfig.rules);

    this.score = 0;
    this.maxHealth = this.dsl.player.max_health || 100;
    this.health = this.maxHealth;
    this.maxStamina = this.dsl.player.stamina || 100;
    this.stamina = this.maxStamina;
    this.playerSpeed = this.dsl.player.speed || 250;
    this.dashCooldownTimer = 0;
    this.lastFiredTime = 0;
    this.lastMeleeAttackTime = 0;
    this.lastDamageTime = 0;
    this.damageCooldownMs = 500;
    this.maxWaves = this.currentStageConfig.maxWaves;
    this.survivalTimer = 0;
    this.lastSurvivalCheckedSecond = 0;
    this.gameState = 'PLAYING';

    this.telemetry.startSession();

    // Reset GameObject references to avoid retaining destroyed objects across restarts
    this.objectiveText = undefined as any;
    this.stageText = undefined as any;
    this.scoreText = undefined as any;
    this.waveText = undefined as any;
    this.bannerText = undefined as any;
    this.healthBarBg = undefined as any;
    this.healthBarFill = undefined as any;
    this.staminaBarFill = undefined as any;
    this.hpLabel = undefined as any;
    this.regionBannerText = undefined as any;
    this.backgroundRect = undefined as any;
    this.bossHealthBarBg = undefined;
    this.bossHealthBarFill = undefined;
    this.bossLabelText = undefined;
    this.openWorldLabelsGroup = undefined as any;
  }

  public create(): void {
    if (this.compilationError) {
      this.renderRuntimeError(this.compilationError);
      return;
    }

    const isPlatformer = this.archetypePolicy.isPlatformer;
    const stage = this.currentStageConfig;
    const worldW = stage.worldBounds.width;
    const worldH = stage.worldBounds.height;

    // 1. Textures & Visual Systems Initialization
    const activeLevel: LevelDef | null = this.dsl.levels?.[this.currentLevelIndex] ?? null;
    this.visualProfile = resolveVisualProfile(this.dsl, activeLevel);
    generateProceduralTextures(this);
    generateDynamicTextures(this, this.visualProfile);

    this.vfxSystem = new VFXSystem(this, this.visualProfile);
    this.environmentSystem = new EnvironmentSystem(this, this.visualProfile, this.seed);

    this.physics.world.setBounds(0, 0, worldW, worldH);
    this.cameras.main.setBounds(0, 0, worldW, worldH);

    // Background
    const rawBg = stage.backgroundColor || this.visualProfile.palette.backgroundTint;
    const bgCol = typeof rawBg === 'number' ? rawBg : Phaser.Display.Color.HexStringToColor(String(rawBg)).color;
    this.backgroundRect = this.add.rectangle(worldW / 2, worldH / 2, worldW, worldH, bgCol);
    this.environmentSystem.buildEnvironment(worldW, worldH);

    // 2. Physics Groups
    this.platformsGroup = this.physics.add.staticGroup();
    this.hazardsGroup = this.physics.add.staticGroup();
    this.collectiblesGroup = this.physics.add.group();
    this.enemiesGroup = this.physics.add.group();
    this.bulletsGroup = this.physics.add.group();
    this.enemyBulletsGroup = this.physics.add.group();
    this.poisGroup = this.physics.add.staticGroup();
    this.actorsGroup = this.physics.add.group();
    this.openWorldLabelsGroup = this.add.group();

    // 3. Player Spawn
    const spawnX = stage.playerSpawn.x;
    const spawnY = stage.playerSpawn.y;

    const playerTexKey = `tex_player_${this.visualProfile.player.silhouette}_${this.visualProfile.themeKey}`;
    this.player = this.physics.add.sprite(spawnX, spawnY, this.textures.exists(playerTexKey) ? playerTexKey : 'tex_player');
    this.player.setDisplaySize(this.dsl.player.width || 32, this.dsl.player.height || 32);
    this.player.setCollideWorldBounds(true);

    this.playSpawnInTween(this.player);

    if (isPlatformer) {
      this.player.setGravityY(stage.gravityY);
      this.player.setDamping(false);
      this.player.setDrag(100, 0);
    } else {
      (this.player.body as Phaser.Physics.Arcade.Body).setAllowGravity(false);
      this.player.setDamping(false);
      this.player.setDrag(0, 0);
    }

    // Camera follow player
    this.cameras.main.startFollow(this.player, true, 0.08, 0.08);

    // Expose scene for test/runtime inspection in DEV or E2E mode
    if (typeof window !== 'undefined' && (import.meta.env.DEV || import.meta.env.VITE_E2E === 'true')) {
      (window as any).__gameScene = this;
    }

    // 4. Populate Entities & Setup Subsystems
    if (this.dsl.open_world) {
      this.setupOpenWorld();
    } else {
      this.applyStageConfig(stage);
      if (!this.dsl.levels || this.dsl.levels.length === 0) {
        const layout = generateProceduralLayout(this.dsl, this.seed);
        this.populateEntities(layout.entities);
      }
    }

    // 5. Initialize Authoritative Objective Engine
    this.setupObjectiveEngine(stage);

    // 6. Initialize Wave Controller if waves allowed by archetype
    if (this.archetypePolicy.allowsEnemyWaves) {
      this.waveController = new WaveController(stage.maxWaves, {
        onWaveStartNotification: (waveNum) => {
          this.spawnFloatingText(this.player.x, this.player.y - 40, `WAVE ${waveNum}!`, '#00f0ff');
          this.telemetry.record('OBJECTIVE_COMPLETED', { wave: waveNum });
          this.ruleEngine.trigger('on_wave_start', this.getGameContext(), { wave: waveNum });
        },
        onWaveSpawnEnemies: (cfg) => {
          this.spawnWaveEnemies(cfg.waveNumber);
        },
        onAllWavesCompleted: () => {
          this.handleStageObjectiveComplete();
        },
      });
      this.waveController.startInitialWave();
    }

    // 7. Collisions & Overlaps
    this.physics.add.collider(this.player, this.platformsGroup);
    this.physics.add.collider(this.enemiesGroup, this.platformsGroup);
    this.physics.add.collider(this.actorsGroup, this.platformsGroup);
    this.physics.add.overlap(this.player, this.collectiblesGroup, this.handleCollect, undefined, this);
    this.physics.add.overlap(this.player, this.enemiesGroup, this.handlePlayerEnemyCollision, undefined, this);
    this.physics.add.overlap(this.player, this.hazardsGroup, this.handleHazardTouch, undefined, this);
    this.physics.add.overlap(this.player, this.enemyBulletsGroup, this.handlePlayerEnemyBulletCollision, undefined, this);
    this.physics.add.overlap(this.bulletsGroup, this.enemiesGroup, this.handleBulletEnemyCollision, undefined, this);
    this.physics.add.collider(this.bulletsGroup, this.platformsGroup, (b) => b.destroy());
    this.physics.add.collider(this.enemyBulletsGroup, this.platformsGroup, (b) => b.destroy());

    // 8. Keyboard & Controls
    if (this.input.keyboard) {
      this.cursors = this.input.keyboard.createCursorKeys();
      this.eKey = this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.E);
      this.wasdKeys = {
        W: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.W),
        A: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.A),
        S: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.S),
        D: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.D),
        SPACE: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE),
        SHIFT: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SHIFT),
        F: this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.F),
      };

      this.input.keyboard.addCapture([
        Phaser.Input.Keyboard.KeyCodes.SPACE,
        Phaser.Input.Keyboard.KeyCodes.UP,
        Phaser.Input.Keyboard.KeyCodes.DOWN,
        Phaser.Input.Keyboard.KeyCodes.LEFT,
        Phaser.Input.Keyboard.KeyCodes.RIGHT,
        Phaser.Input.Keyboard.KeyCodes.W,
        Phaser.Input.Keyboard.KeyCodes.A,
        Phaser.Input.Keyboard.KeyCodes.S,
        Phaser.Input.Keyboard.KeyCodes.D,
        Phaser.Input.Keyboard.KeyCodes.E,
        Phaser.Input.Keyboard.KeyCodes.F,
      ]);
    }

    // 9. HUD
    this.createHUD();

    // Mark lifecycle state active
    this.stateMachine.setActive();

    if (this.onStateChange) {
      this.onStateChange(this.gameState, this.score, this.health);
    }
  }

  private renderRuntimeError(errorMsg: string): void {
    const w = this.cameras.main.width || 800;
    const h = this.cameras.main.height || 600;
    this.add.rectangle(w / 2, h / 2, w, h, 0x0a0005);
    this.add.text(w / 2, h / 2 - 40, '⚠️ RUNTIME CONFIGURATION ERROR', {
      fontSize: '18px',
      color: '#ff0055',
      fontFamily: 'monospace',
      fontStyle: 'bold',
    }).setOrigin(0.5);

    this.add.text(w / 2, h / 2 + 10, errorMsg, {
      fontSize: '13px',
      color: '#ffaaaa',
      fontFamily: 'monospace',
      wordWrap: { width: w - 80 },
      align: 'center',
    }).setOrigin(0.5);
  }

  private setupObjectiveEngine(stage: RuntimeStageConfig): void {
    const collectibleCount = stage.entities.filter((e) => e.type === 'collectible').length;
    const enemyCount = stage.entities.filter((e) => e.type === 'enemy').length;

    this.objectiveEvaluator = new ObjectiveEvaluator(
      stage.objective,
      { collectibles: collectibleCount, enemies: enemyCount },
      {
        onComplete: (def) => {
          this.spawnFloatingText(this.player.x, this.player.y - 40, `★ OBJECTIVE COMPLETE: ${def.type.toUpperCase()} ★`, '#00ff66');
          this.handleStageObjectiveComplete();
        },
        onFailed: (_def, reason) => {
          this.triggerEndGame('LOST', `✖ ${reason.toUpperCase()} ✖`);
        },
      }
    );
  }

  private handleStageObjectiveComplete(): void {
    if (this.stateMachine.isTerminal() || this.isTransitioning) return;

    if (this.currentLevelIndex < this.totalLevels - 1) {
      this.advanceToNextLevel();
    } else {
      this.triggerEndGame('WON');
    }
  }

  private setupOpenWorld(): void {
    const ow = this.dsl.open_world;
    if (!ow) return;

    this.worldManager = new WorldManager(ow.time_system, ow.initial_state);
    this.regionManager = new RegionManager(
      ow.regions,
      ow.connections || [],
      ow.regions[0]?.id,
      (newRegion, prevRegion) => {
        this.handleRegionTransition(newRegion, prevRegion);
      }
    );
    this.vehicleManager = new VehicleManager(
      this,
      (veh) => {
        this.telemetry.record('VEHICLE_ENTERED', { vehicleId: veh.id, name: veh.name });
        this.spawnFloatingText(this.player.x, this.player.y - 30, `ENTERED: ${veh.name.toUpperCase()}`, '#00ffff');
        this.cameras.main.shake(100, 0.005);
      },
      (veh) => {
        this.telemetry.record('VEHICLE_EXITED', { vehicleId: veh.id });
        this.spawnFloatingText(this.player.x, this.player.y - 30, 'EXITED VEHICLE', '#ffffff');
      }
    );
    this.activityManager = new ActivityManager(
      ow.activities,
      (act) => {
        this.telemetry.record('ACTIVITY_STARTED', { activityId: act.id, title: act.title });
        this.spawnFloatingText(this.player.x, this.player.y - 40, `MISSION: ${act.title.toUpperCase()}`, '#ffea00');
        if (this.objectiveText?.active && this.objectiveText?.scene) {
          this.objectiveText.setText(`MISSION: ${act.title}`);
        }
      },
      (act, consequences) => {
        this.telemetry.record('ACTIVITY_COMPLETED', { activityId: act.id, title: act.title });
        this.score += 500;
        this.spawnFloatingText(this.player.x, this.player.y - 50, `★ MISSION COMPLETED: ${act.title} ★`, '#00ff66');
        this.cameras.main.shake(150, 0.008);

        if (consequences?.reputation_changes && this.factionManager) {
          for (const [fId, rep] of Object.entries(consequences.reputation_changes)) {
            this.factionManager.modifyReputation(fId, rep);
          }
        }
        if (consequences?.threat_change && this.threatManager) {
          this.threatManager.escalateThreat(consequences.threat_change);
        }
        if (consequences?.state_mutations && this.worldManager) {
          for (const [k, v] of Object.entries(consequences.state_mutations)) {
            this.worldManager.setState(k, v);
          }
        }
      },
      (act, reason) => {
        this.telemetry.record('ACTIVITY_FAILED', { activityId: act.id });
        this.spawnFloatingText(this.player.x, this.player.y - 40, `MISSION FAILED: ${act.title} (${reason || 'FAILED'})`, '#ff0055');
      }
    );
    this.factionManager = new FactionManager(ow.factions, (fId, newRep, delta) => {
      this.telemetry.record('FACTION_REPUTATION_CHANGED', { factionId: fId, reputation: newRep, delta });
    });
    this.threatManager = new ThreatManager(
      ow.threat_system,
      (newLevel, oldLevel) => {
        this.telemetry.record('ALERT_CHANGED', { threatLevel: newLevel, oldLevel });
        const col = newLevel > 2 ? '#ff0055' : '#ffaa00';
        this.spawnFloatingText(this.player.x, this.player.y - 40, `THREAT LEVEL ${newLevel}!`, col);
      },
      (unitDef) => {
        this.spawnThreatResponseUnits(unitDef);
      }
    );
    this.worldEventManager = new WorldEventManager(
      ow.events || [],
      (evt) => {
        this.telemetry.record('WORLD_EVENT_STARTED', { eventId: evt.id, name: evt.name });
        this.spawnFloatingText(this.player.x, this.player.y - 50, `⚡ EVENT: ${evt.name.toUpperCase()} ⚡`, '#ff00ff');
        if (evt.threat_modifier && this.threatManager) {
          this.threatManager.escalateThreat(evt.threat_modifier);
        }
      },
      (evt) => {
        this.telemetry.record('WORLD_EVENT_ENDED', { eventId: evt.id });
        if (evt.threat_modifier && this.threatManager) {
          this.threatManager.escalateThreat(-evt.threat_modifier);
        }
      }
    );

    const initialRegion = this.regionManager.getCurrentRegion();
    this.populateOpenWorldRegion(initialRegion.id);
    this.showRegionBanner(initialRegion.name, initialRegion.danger_level);
  }

  private handleRegionTransition(newRegion: RegionDef, _prevRegion: RegionDef): void {
    if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;

    this.telemetry.record('REGION_ENTERED', { regionId: newRegion.id, name: newRegion.name });
    this.showRegionBanner(newRegion.name, newRegion.danger_level);

    // Update physical and camera bounds to active region dimensions
    this.physics.world.setBounds(0, 0, newRegion.width, newRegion.height);
    this.cameras.main.setBounds(0, 0, newRegion.width, newRegion.height);

    const bgCol = newRegion.background_color
      ? Phaser.Display.Color.HexStringToColor(newRegion.background_color).color
      : Phaser.Display.Color.HexStringToColor('#0c0e1a').color;
    if (this.backgroundRect) {
      this.backgroundRect.setFillStyle(bgCol);
      this.backgroundRect.setSize(newRegion.width, newRegion.height);
      this.backgroundRect.setPosition(newRegion.width / 2, newRegion.height / 2);
    }

    this.populateOpenWorldRegion(newRegion.id);
  }

  private populateOpenWorldRegion(regionId: string): void {
    const ow = this.dsl.open_world;
    if (!ow) return;

    // Clean up previous region entities and detached text labels (P1-006 fix)
    this.poisGroup.clear(true, true);
    this.actorsGroup.clear(true, true);
    this.openWorldLabelsGroup.clear(true, true);

    // 1. Spawn POIs
    for (const poi of ow.pois) {
      if (poi.region_id !== regionId) continue;
      const pSpr = this.poisGroup.create(poi.x, poi.y, 'tex_poi') as Phaser.Physics.Arcade.Sprite;
      pSpr.setDisplaySize(32, 32);
      pSpr.setData('poiDef', poi);
      pSpr.refreshBody();

      const label = this.add.text(poi.x, poi.y - 24, poi.name, {
        fontSize: '10px',
        color: '#ffff00',
        fontFamily: 'monospace',
        backgroundColor: '#00000088',
      }).setOrigin(0.5);
      this.openWorldLabelsGroup.add(label);
    }

    // 2. Spawn Vehicles
    this.vehicleManager?.spawnVehicles(ow.vehicles, regionId);

    // 3. Spawn Living Actors
    for (const actor of ow.actors) {
      if (actor.region_id !== regionId) continue;
      const aSpr = this.actorsGroup.create(actor.x, actor.y, 'tex_actor') as Phaser.Physics.Arcade.Sprite;
      const w = actor.width || 24;
      const h = actor.height || 24;
      aSpr.setDisplaySize(w, h);
      aSpr.setData('actorDef', actor);
      aSpr.setData('id', actor.id);
      aSpr.setData('speed', actor.speed || 100);
      aSpr.setData('health', actor.health || 50);
      aSpr.setData('behavior', actor.behavior);
      aSpr.setCollideWorldBounds(true);

      const isHostile = actor.faction_id ? (this.factionManager?.isHostile(actor.faction_id) ?? false) : false;
      if (isHostile) {
        aSpr.setTint(0xff0033);
        aSpr.setData('behavior', 'chase');
      } else if (actor.color) {
        aSpr.setTint(Phaser.Display.Color.HexStringToColor(actor.color).color);
      }

      this.behaviorSystem.registerEntity(aSpr, {
        id: actor.id,
        type: 'enemy',
        x: actor.x,
        y: actor.y,
        width: w,
        height: h,
        speed: actor.speed || 100,
        health: actor.health || 50,
        behavior: isHostile ? 'chase' : actor.behavior,
        color: isHostile ? '#ff0033' : (actor.color || '#aaaaaa'),
        points: 50,
        patrol_radius: 120,
        detection_radius: 200,
      });

      const label = this.add.text(actor.x, actor.y - 18, actor.name, {
        fontSize: '9px',
        color: isHostile ? '#ff0055' : '#00f0ff',
        fontFamily: 'monospace',
      }).setOrigin(0.5);
      this.openWorldLabelsGroup.add(label);
    }
  }

  private showRegionBanner(name: string, dangerLevel: number = 1): void {
    if (!this.regionBannerText) {
      this.regionBannerText = this.add.text(
        this.cameras.main.width / 2,
        80,
        '',
        { fontSize: '18px', color: '#00f0ff', fontFamily: 'monospace', fontStyle: 'bold', backgroundColor: '#000000aa', padding: { x: 12, y: 6 } }
      ).setOrigin(0.5).setScrollFactor(0).setDepth(600);
    }

    if (this.regionBannerText?.active && this.regionBannerText?.scene) {
      this.regionBannerText.setText(`📍 ${name.toUpperCase()} (DANGER: ${dangerLevel}/10)`);
      this.regionBannerText.setAlpha(1);
      this.regionBannerText.setVisible(true);
    }

    this.tweens.add({
      targets: this.regionBannerText,
      alpha: 0,
      delay: 2500,
      duration: 1000,
      onComplete: () => {
        if (this.regionBannerText) this.regionBannerText.setVisible(false);
      },
    });
  }

  private spawnThreatResponseUnits(unitDef: ThreatResponseUnitDef): void {
    for (let i = 0; i < unitDef.count; i++) {
      this.threatUnitCounter++;
      const offset = (i + 1) * 40;
      const x = Math.max(50, Math.min(this.dsl.world.width - 50, this.player.x + (i % 2 === 0 ? offset : -offset)));
      const y = Math.max(50, Math.min(this.dsl.world.height - 50, this.player.y + offset));

      const enemy = this.enemiesGroup.create(x, y, 'tex_enemy') as Phaser.Physics.Arcade.Sprite;
      enemy.setDisplaySize(28, 28);
      enemy.setTint(0xff0033);
      enemy.setData('id', `threat_response_${this.threatUnitCounter}_${i}`);
      enemy.setData('health', 40);
      enemy.setData('damage', 18);
      enemy.setData('speed', 160);
      enemy.setData('behavior', unitDef.behavior);
      enemy.setCollideWorldBounds(true);

      this.behaviorSystem.registerEntity(enemy, {
        id: `threat_resp_${this.threatUnitCounter}_${i}`,
        type: 'enemy',
        x,
        y,
        width: 28,
        height: 28,
        speed: 160,
        health: 40,
        behavior: unitDef.behavior,
        color: '#ff0033',
        points: 50,
      });
    }
  }

  private applyStageConfig(stage: RuntimeStageConfig): void {
    const lvl: LevelDef | null = this.dsl.levels?.[stage.stageIndex] ?? null;
    this.visualProfile = resolveVisualProfile(this.dsl, lvl);
    generateDynamicTextures(this, this.visualProfile);

    const bgColorHex = stage.backgroundColor || this.visualProfile.palette.background;
    if (this.backgroundRect) {
      this.backgroundRect.setFillStyle(Phaser.Display.Color.HexStringToColor(bgColorHex).color);
      this.backgroundRect.setSize(stage.worldBounds.width, stage.worldBounds.height);
      this.backgroundRect.setPosition(stage.worldBounds.width / 2, stage.worldBounds.height / 2);
    }

    this.environmentSystem?.destroy();
    this.environmentSystem = new EnvironmentSystem(this, this.visualProfile, this.seed + stage.stageNumber);
    this.environmentSystem.buildEnvironment(stage.worldBounds.width, stage.worldBounds.height);

    if (this.player) {
      this.player.setPosition(stage.playerSpawn.x, stage.playerSpawn.y);
      this.player.setVelocity(0, 0);
    }

    this.populateEntities(stage.entities);

    if (this.objectiveText?.active && this.objectiveText?.scene) {
      this.objectiveText.setText(`GOAL: ${this.objectiveEvaluator?.getHUDLabel() || stage.objective.description}`);
    }
    if (this.stageText?.active && this.stageText?.scene) {
      const stageLabel = stage.isFinale ? `FINAL LEVEL: ${stage.stageNumber}/${this.totalLevels}` : `LEVEL: ${stage.stageNumber}/${this.totalLevels}`;
      this.stageText.setText(stageLabel);
    }
  }

  private playSpawnInTween(sprite: Phaser.Physics.Arcade.Sprite): void {
    const targetScaleX = sprite.scaleX;
    const targetScaleY = sprite.scaleY;
    sprite.setScale(0);
    this.tweens.add({
      targets: sprite,
      scaleX: targetScaleX,
      scaleY: targetScaleY,
      duration: 300,
      ease: 'Back.easeOut',
    });
  }

  private populateEntities(entities: EntityDef[]): void {
    for (const ent of entities) {
      if (ent.type === 'platform') {
        const p = this.platformsGroup.create(ent.x, ent.y, 'tex_platform') as Phaser.Physics.Arcade.Sprite;
        p.setDisplaySize(ent.width, ent.height);
        p.refreshBody();
      } else if (ent.type === 'collectible') {
        const col = this.collectiblesGroup.create(ent.x, ent.y, 'tex_collectible') as Phaser.Physics.Arcade.Sprite;
        col.setDisplaySize(ent.width, ent.height);
        col.setData('points', ent.points);
        col.setData('id', ent.id);
        (col.body as Phaser.Physics.Arcade.Body).setAllowGravity(false);
      } else if (ent.type === 'hazard') {
        const haz = this.hazardsGroup.create(ent.x, ent.y, 'tex_hazard') as Phaser.Physics.Arcade.Sprite;
        haz.setDisplaySize(ent.width, ent.height);
        haz.setData('damage', ent.damage || 20);
        haz.refreshBody();
      } else if (ent.type === 'enemy') {
        const enemy = this.enemiesGroup.create(ent.x, ent.y, 'tex_enemy') as Phaser.Physics.Arcade.Sprite;
        enemy.setDisplaySize(ent.width, ent.height);
        enemy.setData('id', ent.id);
        enemy.setData('health', ent.health);
        enemy.setData('maxHealth', ent.health);
        enemy.setData('damage', ent.damage || 15);
        enemy.setData('speed', ent.speed);
        enemy.setData('behavior', ent.behavior);
        enemy.setData('loot_drop', ent.loot_drop);
        enemy.setData('is_boss', ent.is_boss);
        enemy.setData('points', ent.points);
        enemy.setCollideWorldBounds(true);

        this.behaviorSystem.registerEntity(enemy, ent);

        if (ent.is_boss) {
          this.setupBoss(enemy, ent);
        }
      }
    }
  }

  private setupBoss(bossSprite: Phaser.Physics.Arcade.Sprite, ent: EntityDef): void {
    this.currentBossSprite = bossSprite;
    const camW = this.cameras.main.width;
    const hudY = 32;

    this.bossHealthBarBg = this.add.rectangle(camW / 2, hudY, 204, 18, 0x111122).setScrollFactor(0).setDepth(500);
    this.bossHealthBarFill = this.add.rectangle(camW / 2 - 100, hudY, 200, 14, 0xff0055).setOrigin(0, 0.5).setScrollFactor(0).setDepth(501);

    const bossName = (ent.id || 'BOSS').toUpperCase().replace(/_/g, ' ');
    this.bossLabelText = this.add.text(camW / 2, hudY - 14, `⚠ ${bossName} ⚠`, {
      fontSize: '11px',
      color: '#ff0055',
      fontFamily: 'monospace',
      fontStyle: 'bold',
    }).setOrigin(0.5).setScrollFactor(0).setDepth(502);

    this.spawnFloatingText(bossSprite.x, bossSprite.y - 40, `BOSS ENCOUNTER: ${bossName}`, '#ff0055');
  }

  private destroyBossUI(): void {
    this.bossHealthBarBg?.destroy();
    this.bossHealthBarFill?.destroy();
    this.bossLabelText?.destroy();
    this.bossHealthBarBg = undefined;
    this.bossHealthBarFill = undefined;
    this.bossLabelText = undefined;
    this.currentBossSprite = null;
  }

  public update(time: number, delta: number): void {
    if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;

    const deltaSec = delta / 1000;
    this.survivalTimer += deltaSec;
    this.dashCooldownTimer = Math.max(0, this.dashCooldownTimer - deltaSec);
    this.stamina = Math.min(this.maxStamina, this.stamina + deltaSec * 15);

    // Update authoritative stage objective evaluator
    this.objectiveEvaluator?.update(deltaSec, this.player.x, this.player.y);

    // Periodic survival/time-limit check
    const currentSec = Math.floor(this.survivalTimer);
    if (currentSec > this.lastSurvivalCheckedSecond) {
      this.lastSurvivalCheckedSecond = currentSec;
      this.ruleEngine.trigger('on_time_limit', this.getGameContext(), { time: currentSec });
    }

    // Parallax update
    this.environmentSystem?.updateParallax(this.cameras.main.scrollX, this.cameras.main.scrollY);

    const isPlatformer = this.archetypePolicy.isPlatformer;
    let vx = 0;
    let vy = 0;

    const leftDown = !!(this.cursors?.left?.isDown || this.wasdKeys?.A?.isDown);
    const rightDown = !!(this.cursors?.right?.isDown || this.wasdKeys?.D?.isDown);
    const upDown = !!(this.cursors?.up?.isDown || this.wasdKeys?.W?.isDown);
    const downDown = !!(this.cursors?.down?.isDown || this.wasdKeys?.S?.isDown);
    const spaceDown = !!(this.cursors?.space?.isDown || this.wasdKeys?.SPACE?.isDown);
    const shiftDown = !!(this.cursors?.shift?.isDown || this.wasdKeys?.SHIFT?.isDown);
    const fDown = !!(this.wasdKeys?.F?.isDown);

    if (leftDown) vx -= 1;
    if (rightDown) vx += 1;
    if (!isPlatformer) {
      if (upDown) vy -= 1;
      if (downDown) vy += 1;
    }

    // Open World Subsystems Update
    if (this.dsl.open_world) {
      this.worldManager?.update(deltaSec);
      this.threatManager?.update(deltaSec);
      this.worldEventManager?.update(deltaSec);
      this.activityManager?.update(deltaSec);

      // Handle 'E' Key Interaction
      if (this.eKey && Phaser.Input.Keyboard.JustDown(this.eKey)) {
        if (this.vehicleManager?.isInVehicle()) {
          this.vehicleManager.exitVehicle(this.player);
        } else {
          const nearbyVeh = this.vehicleManager?.getNearbyVehicle(this.player.x, this.player.y, 64);
          if (nearbyVeh) {
            this.vehicleManager?.enterVehicle(nearbyVeh, this.player);
          } else {
            let interacted = false;
            this.poisGroup.getChildren().forEach((pObj) => {
              const pSpr = pObj as Phaser.Physics.Arcade.Sprite;
              if (Phaser.Math.Distance.Between(this.player.x, this.player.y, pSpr.x, pSpr.y) < 64) {
                const poiDef = pSpr.getData('poiDef') as POIDef;
                if (poiDef) {
                  interacted = true;
                  this.spawnFloatingText(poiDef.x, poiDef.y - 30, `STATION: ${poiDef.name.toUpperCase()}`, '#00ffcc');
                  this.activityManager?.recordPOIInteraction(poiDef.id);
                }
              }
            });

            if (!interacted) {
              this.actorsGroup.getChildren().forEach((aObj) => {
                const aSpr = aObj as Phaser.Physics.Arcade.Sprite;
                if (Phaser.Math.Distance.Between(this.player.x, this.player.y, aSpr.x, aSpr.y) < 64) {
                  const actorDef = aSpr.getData('actorDef') as ActorDef;
                  if (actorDef) {
                    const msg = actorDef.dialogue || `Hello traveler! Safe travels in ${this.regionManager?.getCurrentRegion().name || 'the district'}.`;
                    this.spawnFloatingText(aSpr.x, aSpr.y - 30, msg, '#ffffff');
                    if (actorDef.gives_activity_id) {
                      this.activityManager?.startActivity(actorDef.gives_activity_id, this.factionManager ?? undefined, this.worldManager ?? undefined);
                    }
                    this.activityManager?.recordActorInteraction(actorDef.id);
                  }
                }
              });
            }
          }
        }
      }

      // Edge Traversal for Region Transitions
      if (this.regionManager && !this.isTransitioning) {
        const curReg = this.regionManager.getCurrentRegion();
        const worldW = curReg.width;
        const worldH = curReg.height;
        const connected = this.regionManager.getConnectedRegionIds();

        if (connected.length > 0) {
          let targetRegionId: string | null = null;
          let nextSpawnX = this.player.x;
          let nextSpawnY = this.player.y;

          if (this.player.x < 24) {
            targetRegionId = connected[0];
            nextSpawnX = worldW - 48;
          } else if (this.player.x > worldW - 24) {
            targetRegionId = connected[connected.length > 1 ? 1 : 0];
            nextSpawnX = 48;
          } else if (this.player.y < 24) {
            targetRegionId = connected[0];
            nextSpawnY = worldH - 48;
          } else if (this.player.y > worldH - 24) {
            targetRegionId = connected[connected.length > 1 ? 1 : 0];
            nextSpawnY = 48;
          }

          if (targetRegionId && targetRegionId !== curReg.id) {
            const traversalMode = this.vehicleManager?.isInVehicle() ? 'vehicle' : 'on_foot';
            const res = this.regionManager.transitionToRegion(targetRegionId, this.worldManager ?? undefined, traversalMode);
            if (res.success) {
              this.player.setPosition(nextSpawnX, nextSpawnY);
            } else if (res.reason) {
              this.spawnFloatingText(this.player.x, this.player.y - 30, `🔒 ${res.reason}`, '#ff0055');
            }
          }
        }
      }
    }

    // Movement & Dash
    if (this.dsl.open_world && this.vehicleManager?.isInVehicle()) {
      const moveX = (rightDown ? 1 : 0) - (leftDown ? 1 : 0);
      const moveY = (downDown ? 1 : 0) - (upDown ? 1 : 0);
      this.vehicleManager.updateDriving(moveX, moveY, this.player, delta);
    } else {
      let currentSpd = this.playerSpeed;
      const wantsDash = isPlatformer ? shiftDown : (spaceDown || shiftDown);
      if (this.archetypePolicy.allowsDash && wantsDash && this.dashCooldownTimer <= 0 && this.stamina >= 30) {
        this.dashCooldownTimer = this.dsl.player.dash_cooldown || 1.2;
        this.stamina -= 30;
        currentSpd = this.dsl.player.dash_speed || 600;
        this.cameras.main.shake(80, 0.004);
        this.vfxSystem?.triggerDashGhost(this.player);
        this.spawnDashParticles(this.player.x, this.player.y);
        this.telemetry.record('OBJECTIVE_COMPLETED', { action: 'dash' });
        this.ruleEngine.trigger('on_dash', this.getGameContext(), { speed: currentSpd });
      }

      if (isPlatformer) {
        const playerBody = this.player.body as Phaser.Physics.Arcade.Body;
        const isGrounded = playerBody.blocked.down || playerBody.touching.down;
        const wantsJump = upDown || spaceDown;
        if (wantsJump && isGrounded && this.archetypePolicy.jumpEnabled) {
          this.player.setVelocityY(-(this.dsl.player.jump_power || 500));
        }
        this.player.setVelocityX(vx * currentSpd);
      } else {
        if (vx !== 0 && vy !== 0) {
          vx *= 0.7071;
          vy *= 0.7071;
        }
        this.player.setVelocity(vx * currentSpd, vy * currentSpd);
        if (vx !== 0 || vy !== 0) {
          this.player.setRotation(Math.atan2(vy, vx) + Math.PI / 2);
        }
      }
    }

    // Combat Handling per Archetype Policy
    const attackType = this.dsl.player.attack_type ?? this.archetypePolicy.defaultAttackType;
    const cooldownMs = (this.dsl.player.attack_cooldown ?? 0.25) * 1000;

    if (attackType === 'ranged' && this.archetypePolicy.allowsRangedCombat) {
      if ((this.input.activePointer.isDown || fDown) && time - this.lastFiredTime > cooldownMs) {
        this.fireBullet();
        this.lastFiredTime = time;
      }
    } else if (attackType === 'melee' && this.archetypePolicy.allowsMeleeCombat) {
      if ((this.input.activePointer.isDown || fDown || (isPlatformer && fDown)) && time - this.lastMeleeAttackTime > cooldownMs) {
        this.performMeleeAttack();
        this.lastMeleeAttackTime = time;
      }
    }

    // Centralized entity behaviors update
    this.behaviorSystem.update({
      time,
      delta,
      player: this.player,
      scene: this,
      enemyBulletsGroup: this.enemyBulletsGroup,
    });

    this.updateHUD();
  }

  private fireBullet(): void {
    if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;

    const ptr = this.input.activePointer;
    const targetX = ptr.worldX || this.player.x + 100;
    const targetY = ptr.worldY || this.player.y;
    const angle = Phaser.Math.Angle.Between(this.player.x, this.player.y, targetX, targetY);

    this.vfxSystem?.triggerMuzzleFlash(this.player.x, this.player.y, angle);

    const bulletTex = `tex_bullet_${this.visualProfile?.themeKey ?? 'neutral'}`;
    const bullet = this.bulletsGroup.get(
      this.player.x,
      this.player.y,
      this.textures.exists(bulletTex) ? bulletTex : 'tex_bullet'
    ) as Phaser.Physics.Arcade.Sprite;

    if (bullet) {
      bullet.setActive(true);
      bullet.setVisible(true);
      bullet.setDisplaySize(10, 16);
      bullet.setRotation(angle + Math.PI / 2);
      bullet.setVelocity(Math.cos(angle) * 500, Math.sin(angle) * 500);

      this.time.delayedCall(1500, () => {
        if (bullet.active) bullet.destroy();
      });
    }
  }

  private performMeleeAttack(): void {
    if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;

    const angle = this.player.rotation - Math.PI / 2;
    const reach = 48;
    const attackX = this.player.x + Math.cos(angle) * reach;
    const attackY = this.player.y + Math.sin(angle) * reach;
    const attackDmg = this.dsl.player.attack_damage ?? 35;

    this.spawnParticleBurst(attackX, attackY, this.dsl.player.weapon_color || '#00ffff');
    this.cameras.main.shake(100, 0.006);

    this.enemiesGroup.getChildren().forEach((eObj) => {
      const enemy = eObj as Phaser.Physics.Arcade.Sprite;
      if (Phaser.Math.Distance.Between(attackX, attackY, enemy.x, enemy.y) <= 54) {
        const hp = (enemy.getData('health') || 30) - attackDmg;
        enemy.setData('health', hp);
        this.spawnFloatingText(enemy.x, enemy.y, `-${attackDmg}`, '#ffea00');
        this.vfxSystem?.triggerHitFeedback(enemy, !!enemy.getData('is_boss'));

        if (hp <= 0) {
          if (enemy === this.currentBossSprite) {
            this.destroyBossUI();
          }
          this.spawnParticleBurst(enemy.x, enemy.y, '#ff0055');
          this.telemetry.record('ENEMY_DEFEATED', { damageDealt: attackDmg, melee: true });
          this.score += enemy.getData('points') || 100;
          this.ruleEngine.evaluateScoreThresholds(this.score - 100, this.score, this.getGameContext());
          this.objectiveEvaluator?.recordEnemyDefeat(1);
          this.ruleEngine.trigger('on_enemy_defeat', this.getGameContext(), { enemy_id: enemy.getData('id') });
          this.behaviorSystem.unregisterEntity(enemy);
          enemy.destroy();
        }
      }
    });
  }

  private handleCollect(_p: any, colObj: any): void {
    if (!this.stateMachine.canMutateGameplay()) return;

    const col = colObj as Phaser.Physics.Arcade.Sprite;
    const pts = col.getData('points') || 50;
    const entId = col.getData('id') || '';
    const prevScore = this.score;
    this.score += pts;

    this.spawnFloatingText(col.x, col.y, `+${pts}`, '#00ffcc');
    this.telemetry.record('ITEM_COLLECTED', { points: pts });
    this.telemetry.record('SCORE_CHANGED', { score: this.score });

    this.vfxSystem?.triggerPickupFeedback(col.x, col.y);
    this.ruleEngine.trigger('on_collect', this.getGameContext(), { amount: pts, id: entId });
    this.ruleEngine.evaluateScoreThresholds(prevScore, this.score, this.getGameContext());

    // Record with objective evaluator
    this.objectiveEvaluator?.recordCollection(1);
    this.objectiveEvaluator?.recordScore(this.score);

    // Goal detection follows the objective contract (no magic strings)
    if (this.objectiveEvaluator && this.objectiveEvaluator.getObjectiveDef().type === 'reach_exit') {
      const targetId = this.objectiveEvaluator.getObjectiveDef().target_entity_id;
      const isExit = col.getData('is_exit') === true || (targetId ? entId === targetId : true);
      if (isExit) {
        this.ruleEngine.trigger('on_reach_goal', this.getGameContext(), { goal_id: entId });
        this.objectiveEvaluator.recordExitReached(entId);
      }
    }

    col.destroy();
  }

  private handlePlayerEnemyCollision(_p: any, enemyObj: any): void {
    if (!this.stateMachine.canMutateGameplay()) return;

    const now = this.time.now;
    if (now - this.lastDamageTime < this.damageCooldownMs) return;
    this.lastDamageTime = now;

    const enemy = enemyObj as Phaser.Physics.Arcade.Sprite;
    const dmg = enemy.getData('damage') || 15;
    this.health = Math.max(0, this.health - dmg);

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

    const angle = Phaser.Math.Angle.Between(enemy.x, enemy.y, this.player.x, this.player.y);
    this.player.setVelocity(Math.cos(angle) * 350, Math.sin(angle) * 350);

    if (this.health <= 0) {
      this.ruleEngine.trigger('on_player_death', this.getGameContext(), { score: this.score });
      this.triggerEndGame('LOST', '✖ HEALTH DEPLETED ✖');
    }
  }

  private handlePlayerEnemyBulletCollision(_p: any, bulletObj: any): void {
    if (!this.stateMachine.canMutateGameplay()) return;

    const bullet = bulletObj as Phaser.Physics.Arcade.Sprite;
    const dmg = bullet.getData('damage') || 15;
    bullet.destroy();

    const now = this.time.now;
    if (now - this.lastDamageTime < this.damageCooldownMs) return;
    this.lastDamageTime = now;

    this.health = Math.max(0, this.health - dmg);

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
      this.triggerEndGame('LOST', '✖ OVERWHELMED BY ENEMY FIRE ✖');
    }
  }

  private handleHazardTouch(_p: any, hazObj: any): void {
    if (!this.stateMachine.canMutateGameplay()) return;

    const now = this.time.now;
    if (now - this.lastDamageTime < this.damageCooldownMs) return;
    this.lastDamageTime = now;

    const haz = hazObj as Phaser.Physics.Arcade.Sprite;
    const dmg = haz.getData('damage') || 20;
    this.health = Math.max(0, this.health - dmg);

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
    if (!this.stateMachine.canMutateGameplay()) return;

    const bullet = bulletObj as Phaser.Physics.Arcade.Sprite;
    const enemy = enemyObj as Phaser.Physics.Arcade.Sprite;
    bullet.destroy();

    const attackDmg = this.dsl.player.attack_damage ?? 25;
    const hp = (enemy.getData('health') || 30) - attackDmg;
    enemy.setData('health', hp);
    this.spawnFloatingText(enemy.x, enemy.y, `-${attackDmg}`, '#ffea00');
    this.vfxSystem?.triggerHitFeedback(enemy, !!enemy.getData('is_boss'));

    if (hp > 0 && enemy.getData('is_boss')) {
      const maxHp = enemy.getData('maxHealth') || 1;
      if (hp <= maxHp * 0.5) {
        const phaseApplied = this.behaviorSystem.triggerBossPhase2(enemy);
        if (phaseApplied) {
          this.spawnFloatingText(enemy.x, enemy.y - 30, 'PHASE 2!', '#ff00ff');
          this.cameras.main.shake(200, 0.012);
        }
      }
    }

    if (hp <= 0) {
      if (enemy === this.currentBossSprite) {
        this.destroyBossUI();
      }
      this.spawnParticleBurst(enemy.x, enemy.y, '#ff0055');
      this.telemetry.record('ENEMY_DEFEATED', { damageDealt: attackDmg });
      const pts = enemy.getData('points') || 100;
      const prev = this.score;
      this.score += pts;
      this.telemetry.record('SCORE_CHANGED', { score: this.score });

      this.ruleEngine.trigger('on_enemy_defeat', this.getGameContext(), { enemy_id: enemy.getData('id') });
      this.ruleEngine.evaluateScoreThresholds(prev, this.score, this.getGameContext());
      this.objectiveEvaluator?.recordEnemyDefeat(1);

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

      this.behaviorSystem.unregisterEntity(enemy);
      enemy.destroy();

      // If in wave survival mode, check wave cleared
      if (this.waveController && this.enemiesGroup.countActive() === 0) {
        const res = this.waveController.onWaveEnemiesCleared();
        if (res.shouldAdvance) {
          this.time.delayedCall(1200, () => {
            this.waveController?.requestNextWave();
          });
        }
      }
    }
  }

  private advanceToNextLevel(): void {
    if (this.isTransitioning) return;

    if (this.currentLevelIndex >= this.totalLevels - 1) {
      this.triggerEndGame('WON');
      return;
    }

    this.isTransitioning = true;
    this.stateMachine.beginTransition('LEVEL_TRANSITION');

    const nextIndex = this.currentLevelIndex + 1;
    const nextStage = this.runtimeConfig.stages[nextIndex];
    const stageTitle = nextStage.title;

    this.spawnFloatingText(this.player.x, this.player.y - 40, `★ LEVEL COMPLETE! ★`, '#00ff66');
    this.spawnFloatingText(this.player.x, this.player.y - 15, `Entering: ${stageTitle}`, '#00f0ff');

    const FADE_MS = 200;
    this.cameras.main.fadeOut(FADE_MS, 0, 0, 0);
    this.cameras.main.once(Phaser.Cameras.Scene2D.Events.FADE_OUT_COMPLETE, () => {
      this.currentLevelIndex = nextIndex;
      this.currentStageConfig = nextStage;

      // Tear down previous stage state
      this.enemiesGroup.getChildren().forEach((child) => {
        this.behaviorSystem.unregisterEntity(child as Phaser.Physics.Arcade.Sprite);
      });
      this.enemiesGroup.clear(true, true);
      this.collectiblesGroup.clear(true, true);
      this.hazardsGroup.clear(true, true);
      this.platformsGroup.clear(true, true);
      this.bulletsGroup.clear(true, true);
      this.enemyBulletsGroup.clear(true, true);
      this.openWorldLabelsGroup.clear(true, true);
      this.destroyBossUI();

      // Re-configure stage bounds, gravity, camera, rules, and objective
      this.physics.world.setBounds(0, 0, nextStage.worldBounds.width, nextStage.worldBounds.height);
      this.cameras.main.setBounds(0, 0, nextStage.worldBounds.width, nextStage.worldBounds.height);
      this.physics.world.gravity.y = nextStage.gravityY;
      if (this.archetypePolicy.isPlatformer) {
        this.player.setGravityY(nextStage.gravityY);
      } else {
        (this.player.body as Phaser.Physics.Arcade.Body).setAllowGravity(false);
      }

      this.ruleEngine = new RuleEngine(nextStage.rules);
      this.setupObjectiveEngine(nextStage);
      this.applyStageConfig(nextStage);

      if (this.archetypePolicy.allowsEnemyWaves) {
        this.waveController?.reset(nextStage.maxWaves);
        this.waveController?.startInitialWave();
      }

      this.telemetry.record('OBJECTIVE_COMPLETED', { stage: this.currentLevelIndex + 1, title: stageTitle });

      this.cameras.main.fadeIn(FADE_MS, 0, 0, 0);
      this.cameras.main.once(Phaser.Cameras.Scene2D.Events.FADE_IN_COMPLETE, () => {
        this.isTransitioning = false;
        this.stateMachine.endTransition();
      });
    });
  }

  private spawnWaveEnemies(waveNum: number): void {
    const waveBehaviors = ['chase', 'patrol', 'bounce', 'ranged_attack', 'guard', 'flee'] as const;
    const enemyCount = waveNum * 2;
    const stage = this.currentStageConfig;

    for (let i = 0; i < enemyCount; i++) {
      const rx = this.prng();
      const ry = this.prng();
      const x = Math.floor(80 + rx * (stage.worldBounds.width - 160));
      const y = Math.floor(80 + ry * (stage.worldBounds.height - 160));

      const enemy = this.enemiesGroup.create(x, y, 'tex_enemy') as Phaser.Physics.Arcade.Sprite;
      enemy.setDisplaySize(28, 28);
      const behavior = waveBehaviors[i % waveBehaviors.length];
      const hp = 30 + waveNum * 10;
      const dmg = 15 + waveNum * 2;
      const spd = 120 + waveNum * 15;

      enemy.setData('id', `wave_${waveNum}_enemy_${i}`);
      enemy.setData('health', hp);
      enemy.setData('damage', dmg);
      enemy.setData('speed', spd);
      enemy.setData('behavior', behavior);
      enemy.setData('originX', x);
      enemy.setCollideWorldBounds(true);

      this.behaviorSystem.registerEntity(enemy, {
        id: `wave_${waveNum}_enemy_${i}`,
        type: 'enemy',
        x,
        y,
        width: 28,
        height: 28,
        speed: spd,
        health: hp,
        behavior,
        damage: dmg,
        fire_rate: Math.max(0.8, 2.0 - waveNum * 0.2),
        patrol_radius: 160,
        detection_radius: 280,
        color: '#ff0055',
        points: 100,
      });
    }
  }

  private triggerEndGame(outcome: 'WON' | 'LOST', customMessage?: string): void {
    if (this.stateMachine.isTerminal()) return;

    if (outcome === 'WON') {
      this.stateMachine.setWon(customMessage);
    } else {
      this.stateMachine.setLost(customMessage);
    }
    this.gameState = outcome;

    const defaultMessage = outcome === 'WON' ? '★ PROTOTYPE CLEARED ★' : '✖ MISSION FAILED ✖';
    if (this.bannerText?.active && this.bannerText?.scene) {
      this.bannerText.setText(customMessage && customMessage.trim() ? customMessage.trim() : defaultMessage);
      this.bannerText.setColor(outcome === 'WON' ? '#00ff66' : '#ff0055');
      this.bannerText.setVisible(true);
    }

    this.waveController?.setTerminal(true);

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
    const showWave = (ui?.show_wave ?? true) && this.archetypePolicy.allowsEnemyWaves;
    const showObjectives = ui?.show_objectives ?? true;

    // Health Bar
    this.healthBarBg = this.add.rectangle(70, 10, 120, 14, 0x222233).setOrigin(0, 0.5);
    this.healthBarFill = this.add.rectangle(70, 10, 120, 12, 0x00ff66).setOrigin(0, 0.5);
    this.hpLabel = this.add.text(0, 2, 'HEALTH', { fontSize: '11px', color: '#8899aa', fontFamily: 'monospace' });

    this.healthBarBg.setVisible(showHealth);
    this.healthBarFill.setVisible(showHealth);
    this.hpLabel.setVisible(showHealth);

    // Stamina Bar
    const stamCol = Phaser.Display.Color.HexStringToColor(this.visualProfile?.palette.accent ?? '#00f0ff').color;
    this.staminaBarFill = this.add.rectangle(70, 24, 120, 6, stamCol).setOrigin(0, 0.5);
    this.staminaBarFill.setVisible(showStamina);

    // Score & Stage/Wave Text
    const scoreCol = this.visualProfile?.palette.accent ?? '#ffea00';
    const primaryCol = this.visualProfile?.palette.primary ?? '#00f0ff';
    const font = this.visualProfile?.hud.fontFamily ?? 'monospace';

    this.scoreText = this.add.text(0, 36, `SCORE: 0`, { fontSize: '13px', color: scoreCol, fontFamily: font, fontStyle: 'bold' });
    this.scoreText.setVisible(showScore);

    let nextY = 54;
    if (this.totalLevels > 1) {
      this.stageText = this.add.text(0, nextY, `LEVEL: 1/${this.totalLevels}`, { fontSize: '12px', color: primaryCol, fontFamily: font, fontStyle: 'bold' });
      nextY += 16;
    }

    this.waveText = this.add.text(0, nextY, `WAVE: 1/${this.maxWaves}`, { fontSize: '12px', color: primaryCol, fontFamily: font });
    this.waveText.setVisible(showWave);
    if (showWave) {
      nextY += 16;
    }

    // Objective / Status Text
    const goalLabel = this.objectiveEvaluator?.getHUDLabel() || ui?.status_text || 'PLAY PROTOTYPE';
    this.objectiveText = this.add.text(0, nextY, goalLabel, { fontSize: '11px', color: this.visualProfile?.palette.text ?? '#a0aec0', fontFamily: font });
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
    if (this.healthBarFill?.active && this.healthBarFill?.scene) {
      const hpRatio = Math.max(0, this.health / this.maxHealth);
      this.healthBarFill.width = 120 * hpRatio;
      this.healthBarFill.fillColor = hpRatio > 0.4 ? 0x00ff66 : 0xff0055;
    }

    if (this.staminaBarFill?.active && this.staminaBarFill?.scene) {
      const stamRatio = Math.max(0, this.stamina / this.maxStamina);
      this.staminaBarFill.width = 120 * stamRatio;
    }

    if (this.scoreText?.active && this.scoreText?.scene) {
      this.scoreText.setText(`SCORE: ${this.score}`);
    }
    if (this.archetypePolicy.allowsEnemyWaves && this.waveController && this.waveText?.active && this.waveText?.scene) {
      this.waveText.setText(`WAVE: ${this.waveController.getCurrentWave()}/${this.waveController.getMaxWaves()}`);
    }

    if (this.objectiveText?.active && this.objectiveText?.scene && this.objectiveEvaluator) {
      this.objectiveText.setText(this.objectiveEvaluator.getHUDLabel());
    }

    // Open World live HUD status
    if (this.dsl.open_world && this.regionManager) {
      const curReg = this.regionManager.getCurrentRegion();
      const threatLvl = this.threatManager?.getThreatLevel() ?? 0;
      const timeStr = this.worldManager?.getFormattedTime() ?? '12:00';
      const act = this.activityManager?.getActiveActivity();
      const actStr = act
        ? `${act.title.toUpperCase()} (${this.activityManager?.getProgress().current}/${this.activityManager?.getProgress().target})`
        : 'FREE ROAM';

      const inVeh = this.vehicleManager?.isInVehicle();
      const vehStr = inVeh ? ' [DRIVING - E TO EXIT]' : ' [E TO INTERACT/ENTER]';

      if (this.objectiveText?.active && this.objectiveText?.scene) {
        this.objectiveText.setText(`[${curReg.name.toUpperCase()} (DANGER ${curReg.danger_level})] 🚨 ALERT ${threatLvl}/5 ⏰ ${timeStr} 🎯 ${actStr}${vehStr}`);
        this.objectiveText.setColor('#00f0ff');
      }
    }

    // Boss health bar
    if (this.currentBossSprite && this.currentBossSprite.active && this.bossHealthBarFill) {
      const hp = Math.max(0, this.currentBossSprite.getData('health') ?? 0);
      const maxHp = this.currentBossSprite.getData('maxHealth') || 1;
      const ratio = Math.max(0, Math.min(1, hp / maxHp));
      this.bossHealthBarFill.width = 200 * ratio;
    }
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
      isWon: this.stateMachine ? this.stateMachine.getState() === 'WON' : false,
      isLost: this.stateMachine ? this.stateMachine.getState() === 'LOST' : false,
      addScore: (pts: number) => {
        if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;
        const prev = this.score;
        this.score += pts;
        this.ruleEngine.evaluateScoreThresholds(prev, this.score, this.getGameContext());
        this.objectiveEvaluator?.recordScore(this.score);
      },
      damagePlayer: (dmg: number) => {
        if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;
        this.health = Math.max(0, this.health - dmg);
        if (this.health <= 0) {
          this.ruleEngine.trigger('on_player_death', this.getGameContext(), { score: this.score });
          this.triggerEndGame('LOST');
        }
      },
      healPlayer: (amount: number) => {
        if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;
        this.health = Math.min(this.maxHealth, this.health + amount);
      },
      setGameWon: (reason: string) => {
        this.triggerEndGame('WON', reason);
      },
      setGameLost: (reason: string) => {
        this.triggerEndGame('LOST', reason);
      },
      applySpeedBoost: (durationMs: number, multiplier: number) => {
        if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;
        this.applySpeedBoost(durationMs, multiplier);
      },
      spawnBonusEntity: () => {
        if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;
        const stage = this.currentStageConfig;
        const rx = this.prng ? this.prng() : 0.5;
        const ry = this.prng ? this.prng() : 0.5;
        const minX = 80;
        const maxX = Math.max(minX + 40, stage.worldBounds.width - 80);
        const minY = 80;
        const maxY = Math.max(minY + 40, stage.worldBounds.height - 80);
        const col = this.collectiblesGroup.create(
          Math.floor(minX + rx * (maxX - minX)),
          Math.floor(minY + ry * (maxY - minY)),
          'tex_collectible'
        ) as Phaser.Physics.Arcade.Sprite;
        col.setDisplaySize(20, 20);
        col.setData('points', 75);
        (col.body as Phaser.Physics.Arcade.Body).setAllowGravity(false);
      },
      spawnWave: (_waveNum?: number) => {
        if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;
        if (this.archetypePolicy.allowsEnemyWaves && this.waveController) {
          this.waveController.requestNextWave();
        }
      },
      grantPowerup: (type: string) => {
        if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;
        if (type === 'speed') {
          this.applySpeedBoost(5000, 1.5);
        } else if (type === 'heal') {
          this.health = Math.min(this.maxHealth, this.health + 30);
        }
        this.spawnFloatingText(this.player.x, this.player.y - 30, `POWERUP: ${type.toUpperCase()}`, '#ffea00');
        this.time.delayedCall(5000, () => {
          if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;
          this.ruleEngine.trigger('on_powerup_expire', this.getGameContext(), { type });
        });
      },
      activateCheckpoint: (id: string) => {
        if (!this.stateMachine || !this.stateMachine.canMutateGameplay()) return;
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

  public cleanupGameScene(): void {
    this.vfxSystem?.destroy();
    this.environmentSystem?.destroy();
    this.behaviorSystem?.clear();
    this.openWorldLabelsGroup?.destroy(true);
    this.objectiveText = undefined as any;
    this.stageText = undefined as any;
    this.scoreText = undefined as any;
    this.waveText = undefined as any;
    this.bannerText = undefined as any;
    this.healthBarBg = undefined as any;
    this.healthBarFill = undefined as any;
    this.staminaBarFill = undefined as any;
    this.hpLabel = undefined as any;
    this.regionBannerText = undefined as any;
    this.backgroundRect = undefined as any;
    this.bossHealthBarBg = undefined;
    this.bossHealthBarFill = undefined;
    this.bossLabelText = undefined;
  }

  public shutdown(): void {
    this.stateMachine?.destroy();
    this.cleanupGameScene();
    this.events.removeAllListeners();
    this.time.removeAllEvents();
    this.tweens.killAll();
  }
}
