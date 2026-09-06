import type { ObjectiveDef } from './types';

export type ObjectiveStatus = 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';

export interface ObjectiveProgress {
  type: ObjectiveDef['type'];
  status: ObjectiveStatus;
  current: number;
  target: number;
  timeRemaining?: number;
  description: string;
  isComplete: boolean;
}

export class ObjectiveEvaluator {
  private def: ObjectiveDef;
  private status: ObjectiveStatus = 'IN_PROGRESS';
  private currentProgress = 0;
  private targetValue = 1;
  private timeRemaining = 0;
  private totalTime = 0;
  private hasExitCoords = false;
  private exitX = 0;
  private exitY = 0;
  private exitRadius = 50;
  private onObjectiveComplete?: (def: ObjectiveDef) => void;
  private onObjectiveFailed?: (def: ObjectiveDef, reason: string) => void;

  constructor(
    def?: ObjectiveDef,
    totalLevelEntities?: { collectibles: number; enemies: number },
    callbacks?: {
      onComplete?: (def: ObjectiveDef) => void;
      onFailed?: (def: ObjectiveDef, reason: string) => void;
    }
  ) {
    this.def = def || {
      type: 'survive_time',
      time_limit_seconds: 30,
      description: 'Survive the onslaught',
    };
    this.onObjectiveComplete = callbacks?.onComplete;
    this.onObjectiveFailed = callbacks?.onFailed;

    this.initialize(totalLevelEntities);
  }

  private initialize(totalLevelEntities?: { collectibles: number; enemies: number }): void {
    this.status = 'IN_PROGRESS';
    this.currentProgress = 0;

    switch (this.def.type) {
      case 'collect_all': {
        const total = totalLevelEntities?.collectibles ?? 0;
        this.targetValue = Math.max(1, this.def.target_count ?? (total > 0 ? total : 1));
        break;
      }
      case 'defeat_all': {
        const total = totalLevelEntities?.enemies ?? 0;
        this.targetValue = Math.max(1, this.def.target_count ?? (total > 0 ? total : 1));
        break;
      }
      case 'reach_exit': {
        this.targetValue = 1;
        if (typeof this.def.exit_x === 'number' && typeof this.def.exit_y === 'number') {
          this.hasExitCoords = true;
          this.exitX = this.def.exit_x;
          this.exitY = this.def.exit_y;
        }
        break;
      }
      case 'survive_time': {
        this.totalTime = Math.max(5, this.def.time_limit_seconds ?? 30);
        this.timeRemaining = this.totalTime;
        this.targetValue = this.totalTime;
        break;
      }
      case 'score_target': {
        this.targetValue = Math.max(10, this.def.target_score ?? 500);
        break;
      }
      default: {
        this.targetValue = 1;
        break;
      }
    }
  }

  public getStatus(): ObjectiveStatus {
    return this.status;
  }

  public isComplete(): boolean {
    return this.status === 'COMPLETED';
  }

  public isFailed(): boolean {
    return this.status === 'FAILED';
  }

  public getObjectiveDef(): ObjectiveDef {
    return this.def;
  }

  public getProgress(): ObjectiveProgress {
    return {
      type: this.def.type,
      status: this.status,
      current: this.currentProgress,
      target: this.targetValue,
      timeRemaining: this.def.type === 'survive_time' ? Math.ceil(this.timeRemaining) : undefined,
      description: this.def.description || 'Complete objective',
      isComplete: this.status === 'COMPLETED',
    };
  }

  public getHUDLabel(): string {
    if (this.status === 'COMPLETED') return '★ OBJECTIVE COMPLETE ★';
    if (this.status === 'FAILED') return '✗ MISSION FAILED';

    const desc = this.def.description || '';
    switch (this.def.type) {
      case 'collect_all':
        return `COLLECT: ${this.currentProgress}/${this.targetValue} ${desc ? `(${desc})` : ''}`.trim();
      case 'defeat_all':
        return `ELIMINATE: ${this.currentProgress}/${this.targetValue} ${desc ? `(${desc})` : ''}`.trim();
      case 'reach_exit':
        return `GOAL: ${desc || 'Reach the extraction point'}`;
      case 'survive_time':
        return `SURVIVE: ${Math.ceil(this.timeRemaining)}s ${desc ? `(${desc})` : ''}`.trim();
      case 'score_target':
        return `SCORE TARGET: ${this.currentProgress}/${this.targetValue}`;
      default:
        return desc || 'SURVIVE';
    }
  }

  /**
   * Per-frame simulation update (evaluates survival countdown and exit proximity).
   */
  public update(deltaSeconds: number, playerX?: number, playerY?: number): void {
    if (this.status !== 'IN_PROGRESS') return;

    if (this.def.type === 'survive_time') {
      this.timeRemaining = Math.max(0, this.timeRemaining - deltaSeconds);
      this.currentProgress = this.totalTime - this.timeRemaining;
      if (this.timeRemaining <= 0) {
        this.markCompleted();
      }
    } else if (this.def.type === 'reach_exit' && this.hasExitCoords && playerX !== undefined && playerY !== undefined) {
      const dist = Math.hypot(playerX - this.exitX, playerY - this.exitY);
      if (dist <= this.exitRadius) {
        this.currentProgress = 1;
        this.markCompleted();
      }
    }
  }

  /**
   * Record a collectible pickup event.
   */
  public recordCollection(amount: number = 1): boolean {
    if (this.status !== 'IN_PROGRESS' || this.def.type !== 'collect_all') return false;

    this.currentProgress += amount;
    if (this.currentProgress >= this.targetValue) {
      this.markCompleted();
      return true;
    }
    return false;
  }

  /**
   * Record an enemy defeat event.
   */
  public recordEnemyDefeat(amount: number = 1): boolean {
    if (this.status !== 'IN_PROGRESS' || this.def.type !== 'defeat_all') return false;

    this.currentProgress += amount;
    if (this.currentProgress >= this.targetValue) {
      this.markCompleted();
      return true;
    }
    return false;
  }

  /**
   * Record a score mutation event.
   */
  public recordScore(score: number): boolean {
    if (this.status !== 'IN_PROGRESS' || this.def.type !== 'score_target') return false;

    this.currentProgress = score;
    if (this.currentProgress >= this.targetValue) {
      this.markCompleted();
      return true;
    }
    return false;
  }

  /**
   * Record manual trigger of exit/goal reach (e.g. collided with goal entity).
   */
  public recordExitReached(entityId?: string): boolean {
    if (this.status !== 'IN_PROGRESS' || this.def.type !== 'reach_exit') return false;
    if (this.def.target_entity_id && entityId && this.def.target_entity_id !== entityId) {
      return false;
    }

    this.currentProgress = 1;
    this.markCompleted();
    return true;
  }

  public fail(reason: string = 'OBJECTIVE FAILED'): void {
    if (this.status !== 'IN_PROGRESS') return;
    this.status = 'FAILED';
    if (this.onObjectiveFailed) {
      this.onObjectiveFailed(this.def, reason);
    }
  }

  private markCompleted(): void {
    if (this.status !== 'IN_PROGRESS') return;
    this.status = 'COMPLETED';
    if (this.onObjectiveComplete) {
      this.onObjectiveComplete(this.def);
    }
  }
}
