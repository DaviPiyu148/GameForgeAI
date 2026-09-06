import type { RegionDef, WorldConnectionDef } from './types';
import type { WorldManager } from './WorldManager';

export class RegionManager {
  private regions: Map<string, RegionDef> = new Map();
  private connections: WorldConnectionDef[] = [];
  private currentRegion: RegionDef;
  private onRegionChange?: (newRegion: RegionDef, prevRegion: RegionDef) => void;

  constructor(
    regions: RegionDef[] = [],
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

  public getConnections(): WorldConnectionDef[] {
    return [...this.connections];
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

  public canTransition(
    targetRegionId: string,
    worldManager?: WorldManager,
    traversalType: 'on_foot' | 'vehicle' | 'fast_travel' = 'on_foot'
  ): { allowed: boolean; reason?: string } {
    const targetRegion = this.regions.get(targetRegionId);
    if (!targetRegion) {
      return { allowed: false, reason: 'Destination region not found.' };
    }
    if (targetRegion.id === this.currentRegion.id) {
      return { allowed: false, reason: 'Already in target region.' };
    }

    // Find connection definition
    const conn = this.connections.find(
      (c) =>
        (c.from_region === this.currentRegion.id && c.to_region === targetRegionId) ||
        (c.bidirectional !== false && c.from_region === targetRegionId && c.to_region === this.currentRegion.id)
    );

    if (conn) {
      // Check required state key (e.g. security badge, unlocked gate)
      if (conn.required_state_key && worldManager) {
        const stateVal = worldManager.getState(conn.required_state_key);
        if (!stateVal) {
          return {
            allowed: false,
            reason: `Locked: requires state key '${conn.required_state_key}'.`,
          };
        }
      }

      // Check traversal type
      if (conn.traversal_types && conn.traversal_types.length > 0) {
        if (!conn.traversal_types.includes(traversalType)) {
          return {
            allowed: false,
            reason: `Traversal method '${traversalType}' not supported (requires: ${conn.traversal_types.join(', ')}).`,
          };
        }
      }
    }

    return { allowed: true };
  }

  public transitionToRegion(
    regionId: string,
    worldManager?: WorldManager,
    traversalType: 'on_foot' | 'vehicle' | 'fast_travel' = 'on_foot'
  ): { success: boolean; reason?: string } {
    const check = this.canTransition(regionId, worldManager, traversalType);
    if (!check.allowed) {
      return { success: false, reason: check.reason };
    }

    const nextRegion = this.regions.get(regionId)!;
    const prevRegion = this.currentRegion;
    this.currentRegion = nextRegion;

    if (this.onRegionChange) {
      this.onRegionChange(nextRegion, prevRegion);
    }
    return { success: true };
  }
}
