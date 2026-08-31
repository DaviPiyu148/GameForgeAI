# GameForge AI — Generation to Runtime Integration Audit

## 1. Executive Summary

An audit of existing generated games and sanitized database fixtures (`backend/tests/data/real_output_fixtures.json`) was conducted to evaluate the translation of generated DSL structures into actual player-facing gameplay within the Phaser runtime.

### The Core Disconnect
In earlier milestones, the AI generator learned to produce rich JSON schemas containing vehicles, factions, threat systems, POIs, activities, and rules. However, an inspection of runtime handlers revealed that:
1. **Coexistence without consequence**: Systems frequently exist in metadata without modifying player decisions or gameplay loops.
2. **Dead rules**: Generated rules occasionally reference triggers or actions that never execute in the Phaser scene.
3. **Passive open-world entities**: Vehicles could exist on the map but have no distance or traversal incentive; factions were referenced only as color tints without impacting activity outcomes or alert levels.

---

## 2. Requirement → DSL → Runtime Mapping Audit

| Subsystem | DSL Representation | Runtime Owner | Runtime Handler / Trigger | Player-Facing Consequence | Audit Status |
|---|---|---|---|---|---|
| **Vehicles** | `open_world.vehicles` (`type`, `speed`, `durability`) | `VehicleManager` | Key `E` to enter/exit, driving physics | **FULL** when vehicle speed exceeds player speed across large districts ($\ge 1000\text{px}$) enabling traversal/escape; **PASSIVE** if spawn is near objective or slower than player. | PARTIAL $\rightarrow$ FULL |
| **Factions** | `open_world.factions` (`name`, `color`, `territory`) | `FactionManager` | Territory tracking, entity color tinting | **FULL** when activities specifically target named factions and modify reputation/threat; **PASSIVE** when factions only color NPC clothes without mission impact. | PARTIAL |
| **Threat System** | `open_world.threat` (`max_level`, `decay_rate`) | `ThreatManager` | Combat kills, activity completion, reinforcement spawn | **FULL** when hostile acts escalate alert levels and spawn aggressive response units; **PASSIVE** if threat only increments a HUD number without spawning units. | FULL |
| **Activities** | `open_world.activities` (`type`, `poi_id`, `target`) | `ActivityManager` | POI interaction, delivery check, progress counter | **FULL** when anchored to specific POIs with distinct delivery/combat goals and score rewards; **DEAD** if coordinates or targets are missing. | FULL |
| **Points of Interest (POIs)** | `open_world.pois` (`name`, `type`, `x`, `y`) | `RegionManager` | Proximity overlap, `E` interact key | **FULL** when POI serves as activity anchor or extraction station; **PASSIVE** when POI is purely a floating label on an empty coordinate. | PARTIAL $\rightarrow$ FULL |
| **World Events** | `open_world.events` (`type`, `duration_seconds`) | `WorldEventManager` | Periodic timer, alert banner, threat modifier | **FULL** when event alters threat level or triggers lockdown spawns; **PASSIVE** if event banner displays without changing game state. | PARTIAL $\rightarrow$ FULL |
| **Boss Finale** | `levels[i].entities` (`is_boss: true`, `health >= 150`) | `GameScene` | Health bar UI, Phase 2 rage trigger at $\le 50\%$ HP | **FULL** when final level features unique crest silhouette, elevated health pool, and phase escalation; **DEAD** if flag exists without boss entity. | FULL |
| **Rules & Triggers** | `dsl.rules` (`trigger`, `action`, `params`) | `RuleEngine` | Event listener dispatch (`on_collect`, `on_wave_start`, etc.) | **FULL** when trigger is emitted by scene and action alters player state; **DEAD** if trigger is never emitted (e.g. invalid event or unachievable condition). | CRITICAL RISK |

---

## 3. Top Integration Gaps Discovered

### Gap 1: Dead Rules in Generated DSLs
- **Problem**: Generated rules can define triggers that the runtime never emits or actions that do not exist, yet the game builds with "SUCCESS".
- **Remediation**: Build a strict deterministic `DeadRuleValidator` verifying that every rule trigger has an active runtime emitter and every action maps to an executable handler.

### Gap 2: Passive Open-World Coexistence
- **Problem**: Vehicles, factions, and POIs were generated as independent lists. A player could complete the game without ever entering a vehicle, visiting a POI, or interacting with a faction.
- **Remediation**: Require canonical cross-system links:
  - Courier / Traversal activities must require reaching distant POIs ($\ge 800\text{px}$).
  - Vehicle top speed must exceed player on-foot speed ($> 250$).
  - Activities must explicitly link to registered factions.

### Gap 3: Threat Meter as Cosmetic HUD
- **Problem**: In some prototypes, threat was tracked in the manager but never spawned response units or increased enemy aggression.
- **Remediation**: Enforce that threat escalation triggers active response units (`ThreatManager.spawnThreatResponseUnits`) and combat feedback.

### Gap 4: Objective Disconnection from Systems
- **Problem**: An open-world game with 5 complex subsystems defaulted to a simple `collect_all` 3 gems objective that ignored all open-world systems.
- **Remediation**: Generation contract and prompts must align the primary objective with the active structural design pattern.
