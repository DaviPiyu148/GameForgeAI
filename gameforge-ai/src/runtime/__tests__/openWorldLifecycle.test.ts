import test from 'node:test';
import assert from 'node:assert/strict';
import { RegionManager } from '../RegionManager';
import { ActivityManager } from '../ActivityManager';
import { WorldManager } from '../WorldManager';
import type { RegionDef, WorldConnectionDef, ActivityDef } from '../types';

test('Open World Lifecycle: Multi-region transitions (A -> B -> C -> A) with state key requirements and traversal gating', () => {
  const regions: RegionDef[] = [
    { id: 'reg_a', name: 'Downtown Core', x: 0, y: 0, width: 1200, height: 900, danger_level: 1 },
    { id: 'reg_b', name: 'Industrial Strip', x: 1200, y: 0, width: 1400, height: 900, danger_level: 3 },
    { id: 'reg_c', name: 'High-Tech Citadel', x: 2600, y: 0, width: 1600, height: 1000, danger_level: 5 },
  ];

  const connections: WorldConnectionDef[] = [
    {
      from_region: 'reg_a',
      to_region: 'reg_b',
      boundary_side: 'right',
      traversal_types: ['on_foot', 'vehicle'],
      bidirectional: true,
    },
    {
      from_region: 'reg_b',
      to_region: 'reg_c',
      boundary_side: 'right',
      required_state_key: 'has_citadel_pass',
      traversal_types: ['vehicle'], // Gated: vehicle only
      bidirectional: true,
    },
    {
      from_region: 'reg_c',
      to_region: 'reg_a',
      boundary_side: 'bottom',
      traversal_types: ['fast_travel'],
      bidirectional: true,
    },
  ];

  const worldManager = new WorldManager(regions[0].id);
  const regionManager = new RegionManager(regions, connections, 'reg_a');

  assert.equal(regionManager.getCurrentRegion().id, 'reg_a');

  // 1. Transition A -> B (allowed on foot)
  const toB = regionManager.transitionToRegion('reg_b', worldManager, 'on_foot');
  assert.equal(toB.success, true);
  assert.equal(regionManager.getCurrentRegion().id, 'reg_b');

  // 2. Transition B -> C without required state key -> REJECTED
  const toC_unauthorized = regionManager.transitionToRegion('reg_c', worldManager, 'on_foot');
  assert.equal(toC_unauthorized.success, false);
  assert.ok(toC_unauthorized.reason?.includes('has_citadel_pass'));

  // 3. Grant key, but try on foot -> REJECTED (requires vehicle)
  worldManager.setState('has_citadel_pass', true);
  const toC_wrongMode = regionManager.transitionToRegion('reg_c', worldManager, 'on_foot');
  assert.equal(toC_wrongMode.success, false);
  assert.ok(toC_wrongMode.reason?.includes('vehicle'));

  // 4. Transition B -> C with key and vehicle -> ALLOWED
  const toC = regionManager.transitionToRegion('reg_c', worldManager, 'vehicle');
  assert.equal(toC.success, true);
  assert.equal(regionManager.getCurrentRegion().id, 'reg_c');

  // 5. Transition C -> A via fast travel -> ALLOWED
  const toA = regionManager.transitionToRegion('reg_a', worldManager, 'fast_travel');
  assert.equal(toA.success, true);
  assert.equal(regionManager.getCurrentRegion().id, 'reg_a');
});

test('Open World Lifecycle: Repeated transitions (A -> B -> C -> A) × 10 verify zero unbounded growth', () => {
  const regions: RegionDef[] = [
    { id: 'r1', name: 'R1', x: 0, y: 0, width: 800, height: 600, danger_level: 1 },
    { id: 'r2', name: 'R2', x: 800, y: 0, width: 800, height: 600, danger_level: 2 },
    { id: 'r3', name: 'R3', x: 1600, y: 0, width: 800, height: 600, danger_level: 3 },
  ];

  const connections: WorldConnectionDef[] = [
    { from_region: 'r1', to_region: 'r2', bidirectional: true },
    { from_region: 'r2', to_region: 'r3', bidirectional: true },
    { from_region: 'r3', to_region: 'r1', bidirectional: true },
  ];

  let transitionCount = 0;
  const activeRegionHistory: string[] = [];

  const regionManager = new RegionManager(regions, connections, 'r1', (newR) => {
    transitionCount++;
    activeRegionHistory.push(newR.id);
  });

  // Cycle 10 times across 3 regions (30 transitions)
  for (let i = 0; i < 10; i++) {
    assert.equal(regionManager.transitionToRegion('r2').success, true);
    assert.equal(regionManager.transitionToRegion('r3').success, true);
    assert.equal(regionManager.transitionToRegion('r1').success, true);
  }

  assert.equal(transitionCount, 30);
  assert.equal(regionManager.getCurrentRegion().id, 'r1');
  // Manager internal collection counts remain constant
  assert.equal(regionManager.getAllRegions().length, 3);
  assert.equal(regionManager.getConnections().length, 3);
});

test('Open World Lifecycle: Activity prerequisites, POI target evaluation, and rewards', () => {
  const activities: ActivityDef[] = [
    {
      id: 'act_intel',
      title: 'Scout Data Relay',
      description: 'Interact with the terminal in Sector 1',
      status: 'available',
      type: 'courier',
      target_poi_id: 'poi_terminal_1',
      target_count: 1,
      reward: { score: 150 },
    },
    {
      id: 'act_heist',
      title: 'Vault Breaker',
      description: 'Breach the central vault after relay intelligence is secured',
      status: 'locked',
      type: 'investigation',
      prerequisites: {
        completed_activities: ['act_intel'],
      },
      target_poi_id: 'poi_vault',
      target_count: 1,
      reward: { score: 500 },
    },
  ];

  let completedReward: number | undefined;
  const activityManager = new ActivityManager(
    activities,
    undefined,
    (act) => {
      completedReward = act.reward?.score;
    }
  );

  // Initial active mission is act_intel
  assert.equal(activityManager.getActiveActivity()?.id, 'act_intel');

  // Attempting to start locked heist mission fails prerequisites
  assert.equal(activityManager.startActivity('act_heist'), false);

  // Interacting with wrong POI does NOT advance progress
  assert.equal(activityManager.recordPOIInteraction('poi_wrong_terminal'), false);
  assert.equal(activityManager.getProgress().current, 0);

  // Interacting with target POI completes the intel activity
  assert.equal(activityManager.recordPOIInteraction('poi_terminal_1'), true);
  assert.equal(completedReward, 150);

  // Now heist mission prerequisite is satisfied!
  assert.equal(activityManager.startActivity('act_heist'), true);
  assert.equal(activityManager.getActiveActivity()?.id, 'act_heist');

  // Complete heist
  assert.equal(activityManager.recordPOIInteraction('poi_vault'), true);
  assert.equal(completedReward, 500);
});
