import type { ThreatSystemDef, ThreatResponseUnitDef } from './types';

export class ThreatManager {
  private threatSystem: ThreatSystemDef;
  private currentThreat: number = 0;
  private onThreatChanged?: (newLevel: number, oldLevel: number) => void;
  private onDeployResponse?: (unitDef: ThreatResponseUnitDef) => void;

  constructor(
    threatDef?: ThreatSystemDef,
    onThreatChanged?: (newLevel: number, oldLevel: number) => void,
    onDeployResponse?: (unitDef: ThreatResponseUnitDef) => void
  ) {
    this.threatSystem = threatDef || {
      name: 'Threat Level',
      current_level: 0,
      max_level: 5,
      decay_rate_per_sec: 0.05,
    };
    this.currentThreat = this.threatSystem.current_level || 0;
    this.onThreatChanged = onThreatChanged;
    this.onDeployResponse = onDeployResponse;
  }

  public getThreatLevel(): number {
    return Math.floor(this.currentThreat);
  }

  public getThreatFraction(): number {
    return this.currentThreat;
  }

  public getThreatName(): string {
    return this.threatSystem.name;
  }

  public update(deltaSeconds: number): void {
    if (this.currentThreat > 0) {
      const decay = (this.threatSystem.decay_rate_per_sec || 0.05) * deltaSeconds;
      const prevInt = Math.floor(this.currentThreat);
      this.currentThreat = Math.max(0, this.currentThreat - decay);
      const newInt = Math.floor(this.currentThreat);

      if (newInt !== prevInt && this.onThreatChanged) {
        this.onThreatChanged(newInt, prevInt);
      }
    }
  }

  public escalateThreat(amount: number = 1): number {
    const prevInt = Math.floor(this.currentThreat);
    const maxLvl = this.threatSystem.max_level || 5;
    this.currentThreat = Math.min(maxLvl, this.currentThreat + amount);
    const newInt = Math.floor(this.currentThreat);

    if (newInt !== prevInt) {
      if (this.onThreatChanged) {
        this.onThreatChanged(newInt, prevInt);
      }
      this.checkResponseUnits(newInt);
    }
    return newInt;
  }

  private checkResponseUnits(level: number): void {
    if (!this.threatSystem.response_units) return;

    for (const unit of this.threatSystem.response_units) {
      if (level >= unit.min_threat_level && this.onDeployResponse) {
        this.onDeployResponse(unit);
      }
    }
  }
}
