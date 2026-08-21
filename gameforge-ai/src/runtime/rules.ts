import type { RuleAction, RuleDef, RuleTrigger } from './types';

export interface GameContext {
  score: number;
  health: number;
  maxHealth: number;
  playerSpeed: number;
  isWon: boolean;
  isLost: boolean;
  addScore: (pts: number) => void;
  damagePlayer: (dmg: number) => void;
  healPlayer: (amount: number) => void;
  setGameWon: (reason: string) => void;
  setGameLost: (reason: string) => void;
  applySpeedBoost: (durationMs: number, multiplier: number) => void;
  spawnBonusEntity?: () => void;
  triggerScreenShake?: (intensity?: number) => void;
  spawnWave?: (waveNum?: number) => void;
  grantPowerup?: (type: string) => void;
  activateCheckpoint?: (id: string) => void;
  spawnParticles?: (colorHex?: string, count?: number) => void;
  knockbackTarget?: (intensity?: number) => void;
}

type ActionHandler = (context: GameContext, params: Record<string, number | string | boolean>) => void;

/**
 * Predefined allowlisted rule action handlers.
 * Evaluates rules deterministically without eval() or string code execution.
 */
const ACTION_HANDLERS: Record<RuleAction, ActionHandler> = {
  add_score: (ctx, params) => {
    const amount = typeof params.amount === 'number' ? params.amount : 10;
    ctx.addScore(amount);
  },

  damage_player: (ctx, params) => {
    const amount = typeof params.amount === 'number' ? params.amount : 15;
    ctx.damagePlayer(amount);
  },

  heal_player: (ctx, params) => {
    const amount = typeof params.amount === 'number' ? params.amount : 20;
    ctx.healPlayer(amount);
  },

  win_game: (ctx, params) => {
    const reason = typeof params.message === 'string' ? params.message : 'OBJECTIVE COMPLETE';
    ctx.setGameWon(reason);
  },

  lose_game: (ctx, params) => {
    const reason = typeof params.message === 'string' ? params.message : 'MISSION FAILED';
    ctx.setGameLost(reason);
  },

  speed_boost: (ctx, params) => {
    const duration = typeof params.duration === 'number' ? params.duration : 3000;
    const multiplier = typeof params.multiplier === 'number' ? params.multiplier : 1.5;
    ctx.applySpeedBoost(duration, multiplier);
  },

  spawn_entity: (ctx) => {
    if (ctx.spawnBonusEntity) {
      ctx.spawnBonusEntity();
    }
  },

  trigger_screen_shake: (ctx, params) => {
    const intensity = typeof params.intensity === 'number' ? params.intensity : 0.01;
    if (ctx.triggerScreenShake) {
      ctx.triggerScreenShake(intensity);
    }
  },

  spawn_wave: (ctx, params) => {
    const wave = typeof params.wave === 'number' ? params.wave : 1;
    if (ctx.spawnWave) {
      ctx.spawnWave(wave);
    }
  },

  grant_powerup: (ctx, params) => {
    const ptype = typeof params.type === 'string' ? params.type : 'shield';
    if (ctx.grantPowerup) {
      ctx.grantPowerup(ptype);
    }
  },

  activate_checkpoint: (ctx, params) => {
    const cid = typeof params.id === 'string' ? params.id : 'cp_1';
    if (ctx.activateCheckpoint) {
      ctx.activateCheckpoint(cid);
    }
  },

  spawn_particles: (ctx, params) => {
    const color = typeof params.color === 'string' ? params.color : '#00f0ff';
    const count = typeof params.count === 'number' ? params.count : 10;
    if (ctx.spawnParticles) {
      ctx.spawnParticles(color, count);
    }
  },

  knockback_target: (ctx, params) => {
    const force = typeof params.force === 'number' ? params.force : 300;
    if (ctx.knockbackTarget) {
      ctx.knockbackTarget(force);
    }
  },
};

export class RuleEngine {
  private rulesByTrigger: Map<RuleTrigger, RuleDef[]> = new Map();

  constructor(rules: RuleDef[]) {
    for (const rule of rules) {
      const existing = this.rulesByTrigger.get(rule.trigger) || [];
      existing.push(rule);
      this.rulesByTrigger.set(rule.trigger, existing);
    }
  }

  /**
   * Execute all registered rules for a given trigger event.
   */
  public trigger(triggerEvent: RuleTrigger, context: GameContext, overrideParams?: Record<string, number | string | boolean>): void {
    const matchingRules = this.rulesByTrigger.get(triggerEvent) || [];
    for (const rule of matchingRules) {
      const handler = ACTION_HANDLERS[rule.action];
      if (handler) {
        const mergedParams = { ...rule.params, ...(overrideParams || {}) };
        handler(context, mergedParams);
      }
    }
  }
}
