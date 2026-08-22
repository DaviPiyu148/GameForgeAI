import type { ActivityDef, ActivityConsequence } from './types';

export class ActivityManager {
  private activities: Map<string, ActivityDef> = new Map();
  private activeActivity: ActivityDef | null = null;
  private completedActivityIds: Set<string> = new Set();
  private progressCount: number = 0;
  private onActivityStarted?: (act: ActivityDef) => void;
  private onActivityCompleted?: (act: ActivityDef, consequences?: ActivityConsequence) => void;
  private onActivityFailed?: (act: ActivityDef) => void;

  constructor(
    activities: ActivityDef[] = [],
    onStarted?: (act: ActivityDef) => void,
    onCompleted?: (act: ActivityDef, consequences?: ActivityConsequence) => void,
    onFailed?: (act: ActivityDef) => void
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

  public getProgress(): { current: number; target: number } {
    const target = this.activeActivity?.target_count || 1;
    return { current: this.progressCount, target };
  }

  public getAllActivities(): ActivityDef[] {
    return Array.from(this.activities.values());
  }

  public startActivity(activityId: string): boolean {
    const act = this.activities.get(activityId);
    if (!act || act.status === 'completed' || act.status === 'locked') {
      return false;
    }

    this.activeActivity = act;
    act.status = 'active';
    this.progressCount = 0;

    if (this.onActivityStarted) {
      this.onActivityStarted(act);
    }
    return true;
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

    // Unlock subsequent activities if any
    for (const a of this.activities.values()) {
      if (a.status === 'locked') {
        const completedRequired = a.prerequisites?.completed_activities || [];
        if (completedRequired.every((id) => this.completedActivityIds.has(id))) {
          a.status = 'available';
        }
      }
    }

    if (this.onActivityCompleted) {
      this.onActivityCompleted(completedAct, completedAct.success_consequences);
    }
    return completedAct;
  }

  public failActiveActivity(): ActivityDef | null {
    if (!this.activeActivity) return null;

    const failedAct = this.activeActivity;
    failedAct.status = 'failed';
    this.activeActivity = null;

    if (this.onActivityFailed) {
      this.onActivityFailed(failedAct);
    }
    return failedAct;
  }
}
