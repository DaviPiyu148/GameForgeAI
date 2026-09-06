import type { ActivityDef, ActivityConsequence } from './types';
import type { FactionManager } from './FactionManager';
import type { WorldManager } from './WorldManager';

export class ActivityManager {
  private activities: Map<string, ActivityDef> = new Map();
  private activeActivity: ActivityDef | null = null;
  private completedActivityIds: Set<string> = new Set();
  private progressCount: number = 0;
  private timeRemaining: number = 0;
  private onActivityStarted?: (act: ActivityDef) => void;
  private onActivityCompleted?: (act: ActivityDef, consequences?: ActivityConsequence) => void;
  private onActivityFailed?: (act: ActivityDef, reason?: string) => void;

  constructor(
    activities: ActivityDef[] = [],
    onStarted?: (act: ActivityDef) => void,
    onCompleted?: (act: ActivityDef, consequences?: ActivityConsequence) => void,
    onFailed?: (act: ActivityDef, reason?: string) => void
  ) {
    for (const a of activities) {
      this.activities.set(a.id, a);
    }
    this.onActivityStarted = onStarted;
    this.onActivityCompleted = onCompleted;
    this.onActivityFailed = onFailed;

    // Automatically set the first available mission active if present
    const firstAvail = activities.find((a) => a.status === 'available');
    if (firstAvail) {
      this.startActivity(firstAvail.id);
    }
  }

  public getActiveActivity(): ActivityDef | null {
    return this.activeActivity;
  }

  public getProgress(): { current: number; target: number; timeRemaining?: number } {
    const target = this.activeActivity?.target_count || 1;
    return {
      current: this.progressCount,
      target,
      timeRemaining: this.activeActivity?.time_limit_seconds ? Math.ceil(this.timeRemaining) : undefined,
    };
  }

  public getAllActivities(): ActivityDef[] {
    return Array.from(this.activities.values());
  }

  public update(deltaSeconds: number): void {
    if (!this.activeActivity) return;

    if (this.activeActivity.time_limit_seconds && this.activeActivity.time_limit_seconds > 0) {
      this.timeRemaining -= deltaSeconds;
      if (this.timeRemaining <= 0) {
        this.failActiveActivity('TIME_EXPIRED');
      }
    }
  }

  public canStartActivity(activityId: string, factionManager?: FactionManager, worldManager?: WorldManager): { allowed: boolean; reason?: string } {
    const act = this.activities.get(activityId);
    if (!act) return { allowed: false, reason: 'Activity not found.' };
    if (act.status === 'completed') return { allowed: false, reason: 'Activity already completed.' };

    const prereqs = act.prerequisites;
    if (prereqs) {
      // Check completed activities requirement
      if (prereqs.completed_activities && prereqs.completed_activities.length > 0) {
        for (const reqId of prereqs.completed_activities) {
          if (!this.completedActivityIds.has(reqId)) {
            return { allowed: false, reason: `Requires completing prerequisite activity '${reqId}'.` };
          }
        }
      }

      // Check reputation prerequisites
      if (prereqs.min_reputation && factionManager) {
        for (const [fId, minRep] of Object.entries(prereqs.min_reputation)) {
          if (factionManager.getReputation(fId) < minRep) {
            return { allowed: false, reason: `Requires at least ${minRep} reputation with faction '${fId}'.` };
          }
        }
      }

      // Check world state prerequisites
      if (prereqs.required_state && worldManager) {
        for (const [k, v] of Object.entries(prereqs.required_state)) {
          if (worldManager.getState(k) !== v) {
            return { allowed: false, reason: `Requires world state '${k}' == ${v}.` };
          }
        }
      }
    }

    return { allowed: true };
  }

  public startActivity(activityId: string, factionManager?: FactionManager, worldManager?: WorldManager): boolean {
    const check = this.canStartActivity(activityId, factionManager, worldManager);
    if (!check.allowed) {
      return false;
    }

    const act = this.activities.get(activityId)!;
    this.activeActivity = act;
    act.status = 'active';
    this.progressCount = 0;
    this.timeRemaining = act.time_limit_seconds || 0;

    if (this.onActivityStarted) {
      this.onActivityStarted(act);
    }
    return true;
  }

  /**
   * Evaluates POI interaction against the active activity target.
   */
  public recordPOIInteraction(poiId: string): boolean {
    if (!this.activeActivity) return false;

    // If target_poi_id is specified, only that target POI advances progress
    if (this.activeActivity.target_poi_id && this.activeActivity.target_poi_id !== poiId) {
      return false;
    }

    return this.recordProgress(1);
  }

  /**
   * Evaluates Actor interaction against the active activity target.
   */
  public recordActorInteraction(actorId: string): boolean {
    if (!this.activeActivity) return false;

    if (this.activeActivity.target_actor_id && this.activeActivity.target_actor_id !== actorId) {
      return false;
    }

    return this.recordProgress(1);
  }

  public recordProgress(amount: number = 1): boolean {
    if (!this.activeActivity) return false;

    this.progressCount += amount;
    const target = this.activeActivity.target_count || 1;

    if (this.progressCount >= target) {
      this.completeActiveActivity();
      return true;
    }
    return false;
  }

  public completeActiveActivity(): ActivityDef | null {
    if (!this.activeActivity) return null;

    const completedAct = this.activeActivity;
    completedAct.status = 'completed';
    this.completedActivityIds.add(completedAct.id);
    this.activeActivity = null;

    // Unlock subsequent activities if prerequisites now met
    for (const a of this.activities.values()) {
      if (a.status === 'locked' || a.status === 'available') {
        const check = this.canStartActivity(a.id);
        if (check.allowed) {
          a.status = 'available';
        }
      }
    }

    if (this.onActivityCompleted) {
      this.onActivityCompleted(completedAct, completedAct.success_consequences);
    }
    return completedAct;
  }

  public failActiveActivity(reason: string = 'MISSION_FAILED'): ActivityDef | null {
    if (!this.activeActivity) return null;

    const failedAct = this.activeActivity;
    failedAct.status = 'failed';
    this.activeActivity = null;

    if (this.onActivityFailed) {
      this.onActivityFailed(failedAct, reason);
    }
    return failedAct;
  }
}
