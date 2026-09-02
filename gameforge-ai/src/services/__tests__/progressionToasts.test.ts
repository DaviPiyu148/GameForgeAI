/**
 * Unit tests for progression diffing and toast bus notifications (FIND-BROWSER-001 coverage).
 *
 * Run with: npx tsx src/services/__tests__/progressionToasts.test.ts
 */

import { pushToast, subscribeToasts, type ToastMessage } from '../toastBus';
import { diffUserProgress } from '../profile';
import type { UserProgressData, MilestoneItem } from '../../types';

let passed = 0;
let failed = 0;

function assert(label: string, condition: boolean, details?: string) {
  if (condition) {
    console.log(`  ✓ ${label}`);
    passed++;
  } else {
    console.error(`  ✗ ${label}`);
    if (details) console.error(`      ${details}`);
    failed++;
  }
}

function createSampleProgress(overrides: Partial<UserProgressData> = {}): UserProgressData {
  const defaultMilestones: MilestoneItem[] = [
    {
      milestone_key: 'first_game',
      title: 'First Game Built',
      description: 'Built your first playable game prototype',
      icon: 'construction',
      xp_bonus: 50,
      is_unlocked: true,
      unlocked_at: '2026-09-01T12:00:00Z',
    },
    {
      milestone_key: 'five_games',
      title: 'Prolific Creator',
      description: 'Built 5 playable game prototypes',
      icon: 'military_tech',
      xp_bonus: 100,
      is_unlocked: false,
      unlocked_at: null,
    },
  ];

  return {
    user_id: 'test-user-123',
    total_xp: 100,
    current_level: 1,
    creator_title: 'Junior Creator',
    current_level_base_xp: 0,
    next_level_xp: 200,
    xp_into_level: 100,
    xp_needed_for_next: 100,
    progress_percentage: 50,
    milestones: defaultMilestones,
    unlocked_milestone_count: 1,
    total_milestone_count: 2,
    recent_events: [],
    ...overrides,
  };
}

console.log('\n=== 1. ToastBus Pub/Sub Unit Tests ===\n');

// Test 1: Subscribe and receive
{
  const received: ToastMessage[] = [];
  const unsubscribe = subscribeToasts((toast) => received.push(toast));

  pushToast({ variant: 'info', title: 'TEST_TOAST_1', description: 'Description 1' });

  assert(
    'subscribeToasts receives published message',
    received.length === 1 && received[0].title === 'TEST_TOAST_1' && received[0].variant === 'info'
  );

  assert(
    'pushToast automatically assigns unique id',
    typeof received[0].id === 'string' && received[0].id.startsWith('toast_')
  );

  // Test 2: Unsubscribe
  unsubscribe();
  pushToast({ variant: 'success', title: 'TEST_TOAST_2' });

  assert(
    'unsubscribe stops receiving further publications',
    received.length === 1,
    `Expected 1 toast, received ${received.length}`
  );
}

// Test 3: Multiple subscribers
{
  const sub1Messages: ToastMessage[] = [];
  const sub2Messages: ToastMessage[] = [];

  const un1 = subscribeToasts((t) => sub1Messages.push(t));
  const un2 = subscribeToasts((t) => sub2Messages.push(t));

  pushToast({ variant: 'levelup', title: 'LEVEL UP' });

  assert(
    'all active subscribers receive broadcast message',
    sub1Messages.length === 1 && sub2Messages.length === 1
  );

  un1();
  un2();
}

console.log('\n=== 2. diffUserProgress — Progression Diffing Tests ===\n');

// Test 4: Null prev (Initial login / hydration) -> No toasts
{
  const current = createSampleProgress({ total_xp: 100, current_level: 1 });
  const toasts = diffUserProgress(null, current);

  assert(
    'initial hydration (prev is null) produces NO toasts',
    toasts.length === 0,
    `Expected 0 toasts on initial load, got ${toasts.length}`
  );
}

// Test 5: Null current (Logout) -> No toasts
{
  const prev = createSampleProgress({ total_xp: 100, current_level: 1 });
  const toasts = diffUserProgress(prev, null);

  assert(
    'logout transition (current is null) produces NO toasts',
    toasts.length === 0,
    `Expected 0 toasts on logout, got ${toasts.length}`
  );
}

// Test 6: Identical progress -> No toasts (No duplicate on re-render/unchanged polling)
{
  const prev = createSampleProgress({ total_xp: 150, current_level: 2 });
  const current = createSampleProgress({ total_xp: 150, current_level: 2 });
  const toasts = diffUserProgress(prev, current);

  assert(
    'identical progress state produces NO toasts',
    toasts.length === 0,
    `Expected 0 toasts, got ${toasts.length}`
  );
}

// Test 7: In-session XP gain (no level up) -> Exactly one XP toast
{
  const prev = createSampleProgress({ total_xp: 100, current_level: 1 });
  const current = createSampleProgress({ total_xp: 175, current_level: 1 });
  const toasts = diffUserProgress(prev, current);

  assert(
    'XP gain generates exactly one +XP toast with correct delta',
    toasts.length === 1 &&
      toasts[0].variant === 'xp' &&
      toasts[0].title === '+75 XP',
    `Expected [+75 XP], got: ${JSON.stringify(toasts)}`
  );
}

// Test 8: In-session Level Up -> Exactly one LEVEL UP toast (suppresses redundant +XP toast)
{
  const prev = createSampleProgress({ total_xp: 180, current_level: 1, creator_title: 'Junior Creator' });
  const current = createSampleProgress({ total_xp: 250, current_level: 2, creator_title: 'Cyber Architect' });
  const toasts = diffUserProgress(prev, current);

  assert(
    'level up generates LEVEL UP toast and suppresses redundant +XP toast',
    toasts.length === 1 &&
      toasts[0].variant === 'levelup' &&
      toasts[0].title === 'LEVEL UP → 2' &&
      toasts[0].description === 'Cyber Architect',
    `Expected [LEVEL UP → 2], got: ${JSON.stringify(toasts)}`
  );
}

// Test 9: Milestone unlock -> Exactly one NEW MILESTONE toast with title
{
  const prev = createSampleProgress({
    total_xp: 100,
    current_level: 1,
    unlocked_milestone_count: 1,
  });

  const updatedMilestones: MilestoneItem[] = [
    { ...prev.milestones[0] },
    { ...prev.milestones[1], is_unlocked: true, unlocked_at: '2026-09-02T12:00:00Z' },
  ];

  const current = createSampleProgress({
    total_xp: 100,
    current_level: 1,
    milestones: updatedMilestones,
    unlocked_milestone_count: 2,
  });

  const toasts = diffUserProgress(prev, current);

  assert(
    'milestone unlock generates NEW MILESTONE toast with title',
    toasts.length === 1 &&
      toasts[0].variant === 'milestone' &&
      toasts[0].title === 'NEW MILESTONE' &&
      toasts[0].description === 'Prolific Creator',
    `Expected [NEW MILESTONE: Prolific Creator], got: ${JSON.stringify(toasts)}`
  );
}

// Test 10: Simultaneous Level up and Milestone unlock
{
  const prev = createSampleProgress({
    total_xp: 180,
    current_level: 1,
    unlocked_milestone_count: 1,
  });

  const updatedMilestones: MilestoneItem[] = [
    { ...prev.milestones[0] },
    { ...prev.milestones[1], is_unlocked: true, unlocked_at: '2026-09-02T12:00:00Z' },
  ];

  const current = createSampleProgress({
    total_xp: 280,
    current_level: 2,
    creator_title: 'Cyber Architect',
    milestones: updatedMilestones,
    unlocked_milestone_count: 2,
  });

  const toasts = diffUserProgress(prev, current);

  assert(
    'simultaneous level up and milestone unlock emits both notifications in order',
    toasts.length === 2 &&
      toasts[0].variant === 'levelup' &&
      toasts[0].title === 'LEVEL UP → 2' &&
      toasts[1].variant === 'milestone' &&
      toasts[1].title === 'NEW MILESTONE',
    `Expected 2 toasts, got: ${JSON.stringify(toasts)}`
  );
}

console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);

if (failed > 0) {
  if (typeof (globalThis as any).process !== 'undefined') {
    (globalThis as any).process.exit(1);
  } else {
    throw new Error(`${failed} tests failed`);
  }
}
