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

export interface RuleExecutionFrame {
  ruleId: string;
  trigger: RuleTrigger;
  action: RuleAction;
}

export interface RuleGraphValidationResult {
  hasCycles: boolean;
  cycles: string[][];
  warnings: string[];
}

/**
 * Mapping of rule actions to triggers they are known to emit synchronously or causally.
 */
const ACTION_TO_POTENTIAL_TRIGGERS: Record<RuleAction, RuleTrigger[]> = {
  add_score: ['on_score_target'],
  damage_player: ['on_player_death'],
  spawn_wave: ['on_wave_start'],
  win_game: [],
  lose_game: [],
  heal_player: [],
  speed_boost: [],
  spawn_entity: ['on_collect'],
  trigger_screen_shake: [],
  grant_powerup: [],
  activate_checkpoint: [],
  spawn_particles: [],
  knockback_target: [],
};

export class RuleEngine {
  private rulesByTrigger: Map<RuleTrigger, RuleDef[]> = new Map();
  private firedThresholdRuleIds: Set<string> = new Set();
  private executionDepth = 0;
  private static readonly MAX_EXECUTION_DEPTH = 12;

  // Active execution path tracking for synchronous cycle detection
  private activeRuleIds: Set<string> = new Set();
  private activeExecutionStack: RuleExecutionFrame[] = [];

  constructor(rules: RuleDef[] = []) {
    for (const rule of rules) {
      const existing = this.rulesByTrigger.get(rule.trigger) || [];
      existing.push(rule);
      this.rulesByTrigger.set(rule.trigger, existing);
    }
  }

  /**
   * Static validation of rule dependency graph to detect direct and indirect cycles before execution.
   */
  public static validateRuleGraph(rules: RuleDef[]): RuleGraphValidationResult {
    const rulesByTrigger = new Map<RuleTrigger, RuleDef[]>();
    for (const r of rules) {
      const list = rulesByTrigger.get(r.trigger) || [];
      list.push(r);
      rulesByTrigger.set(r.trigger, list);
    }

    const cycles: string[][] = [];
    const warnings: string[] = [];

    // Helper to traverse causal graph
    const visited = new Set<string>();
    const recStack = new Set<string>();
    const currentPath: string[] = [];

    const dfs = (rule: RuleDef) => {
      visited.add(rule.id);
      recStack.add(rule.id);
      currentPath.push(rule.id);

      const potentialTriggers = ACTION_TO_POTENTIAL_TRIGGERS[rule.action] || [];
      for (const nextTrigger of potentialTriggers) {
        const nextRules = rulesByTrigger.get(nextTrigger) || [];
        for (const nextRule of nextRules) {
          if (!visited.has(nextRule.id)) {
            dfs(nextRule);
          } else if (recStack.has(nextRule.id)) {
            const cycleStartIdx = currentPath.indexOf(nextRule.id);
            const cyclePath = currentPath.slice(cycleStartIdx).concat(nextRule.id);
            cycles.push(cyclePath);
            warnings.push(
              `Cyclic rule dependency detected: ${cyclePath.join(' -> ')}`
            );
          }
        }
      }

      recStack.delete(rule.id);
      currentPath.pop();
    };

    for (const rule of rules) {
      if (!visited.has(rule.id)) {
        dfs(rule);
      }
    }

    return {
      hasCycles: cycles.length > 0,
      cycles,
      warnings,
    };
  }

  /**
   * Execute all registered rules for a given trigger event with re-entrancy and synchronous cycle protection.
   * Ensures:
   * 1. Multiple independent rules listening to the same trigger are all allowed to execute.
   * 2. Legitimate linear causal chains (A -> B -> C -> D) execute fully.
   * 3. True synchronous cycles (A -> A, A -> B -> A, A -> B -> C -> A) are detected and suppressed immediately.
   * 4. MAX_EXECUTION_DEPTH acts as a secondary defensive ceiling.
   */
  public trigger(
    triggerEvent: RuleTrigger,
    context: GameContext,
    overrideParams?: Record<string, number | string | boolean>
  ): void {
    if (this.executionDepth >= RuleEngine.MAX_EXECUTION_DEPTH) {
      console.warn(
        `[RuleEngine] Defensive depth ceiling reached: suppressed trigger '${triggerEvent}' (depth ${this.executionDepth} >= ${RuleEngine.MAX_EXECUTION_DEPTH}).`
      );
      return;
    }

    const matchingRules = this.rulesByTrigger.get(triggerEvent) || [];
    if (matchingRules.length === 0) return;

    this.executionDepth++;
    try {
      for (const rule of matchingRules) {
        // Synchronous Cycle Detection on the active rule execution path
        if (this.activeRuleIds.has(rule.id)) {
          const pathStr = this.activeExecutionStack
            .map((f) => `${f.ruleId} (${f.trigger}:${f.action})`)
            .join(' -> ');
          console.warn(
            `[RuleEngine] Synchronous cycle detected on rule '${rule.id}'. Active path: [${pathStr}] -> ${rule.id}. Suppressing re-entrant execution.`
          );
          continue;
        }

        // For score target rules triggered directly, ensure single-shot threshold semantic unless repeating is specified
        if (triggerEvent === 'on_score_target') {
          if (this.firedThresholdRuleIds.has(rule.id)) {
            continue;
          }
          this.firedThresholdRuleIds.add(rule.id);
        }

        const handler = ACTION_HANDLERS[rule.action];
        if (handler) {
          const frame: RuleExecutionFrame = {
            ruleId: rule.id,
            trigger: triggerEvent,
            action: rule.action,
          };

          this.activeRuleIds.add(rule.id);
          this.activeExecutionStack.push(frame);

          try {
            const mergedParams = { ...rule.params, ...(overrideParams || {}) };
            handler(context, mergedParams);
          } finally {
            this.activeRuleIds.delete(rule.id);
            this.activeExecutionStack.pop();
          }
        }
      }
    } finally {
      this.executionDepth--;
    }
  }

  /**
   * Evaluates score-target threshold crossing rules upon score mutations.
   * Fires when the player's score crosses a configured target threshold.
   * Supports legitimate repeated crossings when score falls below and re-crosses threshold.
   */
  public evaluateScoreThresholds(prevScore: number, newScore: number, context: GameContext): void {
    const scoreRules = this.rulesByTrigger.get('on_score_target') || [];
    for (const rule of scoreRules) {
      const target =
        typeof rule.params.target_score === 'number'
          ? rule.params.target_score
          : typeof rule.params.score === 'number'
          ? rule.params.score
          : typeof rule.params.amount === 'number'
          ? rule.params.amount
          : 100;

      // Re-arm threshold if score dropped below target and repeating is enabled
      const isRepeating = rule.params.repeating === true || rule.params.once === false;
      if (isRepeating && newScore < target) {
        this.firedThresholdRuleIds.delete(rule.id);
      }

      if (this.firedThresholdRuleIds.has(rule.id)) continue;

      if (prevScore < target && newScore >= target) {
        this.trigger('on_score_target', context, { score: newScore, target });
      }
    }
  }

  /**
   * Reset runtime execution state and one-shot threshold tracking (e.g. on stage change or restart).
   */
  public resetState(): void {
    this.firedThresholdRuleIds.clear();
    this.activeRuleIds.clear();
    this.activeExecutionStack = [];
    this.executionDepth = 0;
  }

  /**
   * Inspect active execution stack depth for testing.
   */
  public getActiveStackDepth(): number {
    return this.activeExecutionStack.length;
  }

  /**
   * Check if any rules are registered for a given trigger.
   */
  public hasRulesForTrigger(trigger: RuleTrigger): boolean {
    const rules = this.rulesByTrigger.get(trigger);
    return !!rules && rules.length > 0;
  }

  /**
   * Inspect registered rules count for testing.
   */
  public getRuleCount(): number {
    let count = 0;
    for (const list of this.rulesByTrigger.values()) {
      count += list.length;
    }
    return count;
  }
}
