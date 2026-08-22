import type { FactionDef } from './types';

export class FactionManager {
  private factions: Map<string, FactionDef> = new Map();
  private reputationMap: Map<string, number> = new Map();
  private onReputationChanged?: (factionId: string, newRep: number, delta: number) => void;

  constructor(
    factions: FactionDef[] = [],
    onReputationChanged?: (factionId: string, newRep: number, delta: number) => void
  ) {
    this.onReputationChanged = onReputationChanged;
    for (const f of factions) {
      this.factions.set(f.id, f);
      this.reputationMap.set(f.id, f.initial_reputation ?? 0);
    }
  }

  public getFaction(factionId: string): FactionDef | undefined {
    return this.factions.get(factionId);
  }

  public getAllFactions(): FactionDef[] {
    return Array.from(this.factions.values());
  }

  public getReputation(factionId: string): number {
    return this.reputationMap.get(factionId) ?? 0;
  }

  public modifyReputation(factionId: string, delta: number): number {
    const current = this.getReputation(factionId);
    const updated = Math.max(-100, Math.min(100, current + delta));
    this.reputationMap.set(factionId, updated);

    if (this.onReputationChanged) {
      this.onReputationChanged(factionId, updated, delta);
    }
    return updated;
  }

  public isHostile(factionId: string): boolean {
    const faction = this.factions.get(factionId);
    if (!faction) return false;
    const rep = this.getReputation(factionId);
    const threshold = faction.hostility_threshold ?? -20;
    return rep <= threshold;
  }
}
