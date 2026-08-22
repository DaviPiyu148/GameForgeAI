import type { RegionDef, WorldConnectionDef } from './types';

export class RegionManager {
  private regions: Map<string, RegionDef> = new Map();
  private connections: WorldConnectionDef[] = [];
  private currentRegion: RegionDef;
  private onRegionChange?: (newRegion: RegionDef, prevRegion: RegionDef) => void;

  constructor(
    regions: RegionDef[],
    connections: WorldConnectionDef[] = [],
    initialRegionId?: string,
    onRegionChange?: (newRegion: RegionDef, prevRegion: RegionDef) => void
  ) {
    for (const r of regions) {
      this.regions.set(r.id, r);
    }
    this.connections = connections;
    this.onRegionChange = onRegionChange;

    const startId = initialRegionId && this.regions.has(initialRegionId) ? initialRegionId : regions[0]?.id;
    this.currentRegion = this.regions.get(startId) || {
      id: 'reg_default',
      name: 'Central District',
      theme: 'cyberpunk',
      width: 1600,
      height: 1200,
      danger_level: 1,
    };
  }

  public getCurrentRegion(): RegionDef {
    return this.currentRegion;
  }

  public getRegion(regionId: string): RegionDef | undefined {
    return this.regions.get(regionId);
  }

  public getAllRegions(): RegionDef[] {
    return Array.from(this.regions.values());
  }

  public getConnectedRegionIds(regionId: string = this.currentRegion.id): string[] {
    const connected = new Set<string>();

    // From explicit connections
    for (const conn of this.connections) {
      if (conn.from_region === regionId) {
        connected.add(conn.to_region);
      } else if (conn.to_region === regionId && conn.bidirectional !== false) {
        connected.add(conn.from_region);
      }
    }

    // From region.traversal_connections
    const reg = this.regions.get(regionId);
    if (reg?.traversal_connections) {
      for (const targetId of reg.traversal_connections) {
        connected.add(targetId);
      }
    }

    return Array.from(connected);
  }

  public transitionToRegion(regionId: string): boolean {
    const nextRegion = this.regions.get(regionId);
    if (!nextRegion || nextRegion.id === this.currentRegion.id) {
      return false;
    }

    const prevRegion = this.currentRegion;
    this.currentRegion = nextRegion;

    if (this.onRegionChange) {
      this.onRegionChange(nextRegion, prevRegion);
    }
    return true;
  }
}
