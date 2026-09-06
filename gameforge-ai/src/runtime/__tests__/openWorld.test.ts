import test from 'node:test';
import assert from 'node:assert/strict';
import { RegionManager } from '../RegionManager';
import { ActivityManager } from '../ActivityManager';
import { WorldManager } from '../WorldManager';
import type { RegionDef, WorldConnectionDef, ActivityDef } from '../types';

test('OpenWorld: Region transition respects required_state_key', () => {
  const regions: RegionDef[] = [
    { id: 'reg_downtown', name: 'Downtown', theme: 'cyberpunk', width: 1200, height: 900, danger_level: 2 },
    { id: 'reg_highrise', name: 'Highrise Sector', theme: 'cyberpunk', width: 1600, height: 1200, danger_level: 5 },
  ];

  const connections: WorldConnectionDef[] = [
    {
      from_region: 'reg_downtown',
      to_region: 'reg_highrise',
      bidirectional: true,
      traversal_types: ['on_foot', 'vehicle'],
      required_state_key: 'keycard_highrise',
    },
  ];

  const worldMgr = new WorldManager(undefined, { keycard_highrise: false });
  const regMgr = new RegionManager(regions, connections, 'reg_downtown');

  // Attempt transition while keycard is false -> must fail
  const attempt1 = regMgr.transitionToRegion('reg_highrise', worldMgr);
  assert.equal(attempt1.success, false);
  assert.ok(attempt1.reason?.includes('keycard_highrise'));
  assert.equal(regMgr.getCurrentRegion().id, 'reg_downtown');

  // Unlock keycard in world state
  worldMgr.setState('keycard_highrise', true);

  // Transition now succeeds
  const attempt2 = regMgr.transitionToRegion('reg_highrise', worldMgr);
  assert.equal(attempt2.success, true);
  assert.equal(regMgr.getCurrentRegion().id, 'reg_highrise');
});

test('OpenWorld: Targeted POI interaction advances only designated activity target', () => {
  let completed = false;
  const activities: ActivityDef[] = [
    {
      id: 'act_hack_terminal',
      title: 'Infiltrate Terminal',
      description: 'Hack Data Hub Alpha',
      type: 'mission',
      status: 'available',
      target_poi_id: 'poi_terminal_alpha',
      target_count: 1,
    },
  ];

  const actMgr = new ActivityManager(
    activities,
    undefined,
    () => {
      completed = true;
    }
  );

  // Interacting with unrelated garage POI -> does not advance progress
  assert.equal(actMgr.recordPOIInteraction('poi_garage_beta'), false);
  assert.equal(completed, false);
  assert.equal(actMgr.getProgress().current, 0);

  // Interacting with target POI -> completes activity
  assert.equal(actMgr.recordPOIInteraction('poi_terminal_alpha'), true);
  assert.equal(completed, true);
});

test('OpenWorld: Timed activity fails upon countdown expiry', () => {
  let failed = false;
  const activities: ActivityDef[] = [
    {
      id: 'act_timed_delivery',
      title: 'Courier Rush',
      description: 'Deliver goods within 5 seconds',
      type: 'delivery',
      status: 'available',
      target_poi_id: 'poi_station_drop',
      target_count: 1,
      time_limit_seconds: 5,
    },
  ];

  const actMgr = new ActivityManager(
    activities,
    undefined,
    undefined,
    () => {
      failed = true;
    }
  );

  actMgr.update(3.0);
  assert.equal(failed, false);
  assert.equal(actMgr.getProgress().timeRemaining, 2);

  actMgr.update(3.0);
  assert.equal(failed, true);
  assert.equal(actMgr.getActiveActivity(), null);
});
