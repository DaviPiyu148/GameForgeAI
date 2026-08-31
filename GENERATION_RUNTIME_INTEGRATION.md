# GameForge AI — Generation to Runtime Integration V1

## 1. Overview & Architectural Problem Solved

GameForge AI's generator can output rich JSON schemas representing vehicles, factions, threat systems, activities, POIs, world events, and rules, and the Phaser runtime supports all of these subsystems. However, previously there was an architectural risk of **passive co-existence**:
- Vehicles generated on the map but never useful or slower than the player.
- Factions generated as cosmetic entity color tints without affecting missions, reputation, or alerts.
- Threat meters existing purely as passive HUD counters without triggering combat reinforcement sweeps.
- Rules generated with triggers or actions that the Phaser runtime never emits or handles (**dead rules**).

**Generation/Runtime Integration V1** provides the canonical bridge connecting AI generation to verified player-facing gameplay consequences.

---

## 2. Core Concepts & Canonical Definitions

### A. System Usage Tiers (`UsageTier`)
A system is not considered used merely because its JSON definition is populated. It must satisfy observable gameplay criteria:
- **`FULL`**: The system causes an observable, active gameplay consequence through an existing runtime capability (e.g. vehicle speed $> \text{player speed}$ across a district dimension $\ge 1000\text{px}$, or activities specifically naming and rewarding faction standings).
- **`PARTIAL`**: The system exists and provides UI or telemetry context but does not directly alter gameplay pacing or challenge (e.g. threat meter increments without reinforcement spawns).
- **`PASSIVE`**: The system is rendered visually or stored in metadata, but never interacted with or required to achieve objectives.
- **`DEAD`**: The system or rule references triggers or actions that cannot be emitted or handled by the Phaser engine.
- **`UNSUPPORTED`**: The requested capability is not part of the Phaser Arcade 2D runtime allowlist.

### B. Canonical System Usage Matrix (`SYSTEM_USAGE_DEFINITIONS`)
Defined in `backend/app/generation/composition_matrix.py`:
- **Vehicles** (`VehicleManager`): Traversal across large districts ($\ge 1000\text{px}$) with speed advantage over the player; emergency escapes.
- **Factions** (`FactionManager`): Explicitly referenced in missions/activities; territorial control and alert unit modifiers.
- **Threat** (`ThreatManager`): Hostile activity completion and kills escalate threat level; dispatches reinforcement units.
- **Activities** (`ActivityManager`): Anchored to POIs with distinct delivery, patrol, or combat objectives and score rewards.
- **POIs** (`RegionManager`): Serve as garages, terminals, or activity start/target locations.
- **World Events** (`WorldEventManager`): Environmental state triggers modifying threat or activating lockdowns.
- **Boss Finale** (`GameScene`): Elevated health pool ($\ge 150$), unique silhouette crest, and Phase 2 rage threshold.

### C. Rule Liveness & Dead-Rule Validator (`validate_rule_liveness`)
- Validates that rule triggers belong to the supported runtime trigger set:
  `["on_collect", "on_collide_enemy", "on_reach_goal", "on_score_target", "on_time_limit", "on_player_death", "on_wave_start", "on_dash", "on_hazard_touch", "on_enemy_defeat", "on_checkpoint", "on_powerup_expire"]`
- Validates that rule actions belong to the executable runtime action set:
  `["add_score", "damage_player", "heal_player", "win_game", "lose_game", "spawn_entity", "speed_boost", "trigger_screen_shake", "spawn_wave", "grant_powerup", "activate_checkpoint", "spawn_particles", "knockback_target"]`
- Flags missing action parameters (e.g. `type` for `grant_powerup`, `id` for `activate_checkpoint`).

---

## 3. Evaluation & Quality Scoring Updates

1. **Dead Rule Detection & Penalties**:
   - `GameDepthEvaluator` automatically audits all rules in the DSL.
   - Any detected dead rules apply `QualityFailureCode.DEAD_RULE_DETECTED` and penalize the overall quality score by up to 25 points.
2. **Passive System Penalty**:
   - Systems lacking verified cross-system relationships trigger `QualityFailureCode.PASSIVE_SYSTEM_DETECTED`.
3. **Frontend Integration**:
   - `SuccessStatusPage.tsx` parses compiler logs and displays verified active subsystems (e.g. `✓ Vehicles — Traversal`, `✓ Factions — Activities`, `✓ Threat — Escalation`).

---

## 4. Verification Results

- **Integration Tests**: `pytest tests/test_generation_runtime_integration.py -v` $\rightarrow$ **5 passed in 0.06s**.
- **Backend Regression Suite**: `pytest -q` across all generation, quality, provider, resilience, and runtime test files $\rightarrow$ **64 passed in 2.29s**.
- **Frontend Code Quality & Production Build**:
  - `npx oxlint` $\rightarrow$ **0 warnings, 0 errors across 56 files**.
  - `npm run build` $\rightarrow$ **Clean production build in 722ms**.
- **Database & Migrations**: Single head `bc9ae398f146 (head)` confirmed clean.
- **Browser Testing**: `BROWSER TESTING: NOT PERFORMED` (per strict instruction).
