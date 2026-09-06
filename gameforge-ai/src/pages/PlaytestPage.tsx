import React, { useState } from 'react';
import { PhaserCanvas } from '../runtime/PhaserCanvas';
import {
  PLATFORMER_FIXTURE,
  ARENA_FIXTURE,
  SHOOTER_FIXTURE,
  COLLECTOR_FIXTURE,
  SURVIVAL_FIXTURE,
  RUNNER_FIXTURE,
  OPEN_WORLD_FIXTURE,
} from '../runtime/fixtures';
import type { GameArchetype, GameDSL, PlaytestSummary } from '../runtime/types';

interface ArchetypeOption {
  key: string;
  name: string;
  archetype: GameArchetype;
  dsl: GameDSL;
  mode: string;
  controls: string;
}

const OPTIONS: ArchetypeOption[] = [
  {
    key: 'platformer',
    name: '2D Platformer',
    archetype: 'platformer',
    dsl: PLATFORMER_FIXTURE,
    mode: 'Linear / Gravity 900',
    controls: 'A/D: Move | SPACE: Jump | SHIFT: Dash | Goal: Beacon',
  },
  {
    key: 'arena',
    name: 'Arena Combat',
    archetype: 'arena',
    dsl: ARENA_FIXTURE,
    mode: 'Arena / 3 Waves',
    controls: 'WASD: Move | Click: Fire Plasma | SPACE/SHIFT: Dash',
  },
  {
    key: 'shooter',
    name: 'Top-Down Shooter',
    archetype: 'shooter',
    dsl: SHOOTER_FIXTURE,
    mode: 'Linear / Top-Down',
    controls: 'WASD: Move | Click: Fire Plasma | Eliminate Patrols',
  },
  {
    key: 'collector',
    name: 'Data Collector',
    archetype: 'collector',
    dsl: COLLECTOR_FIXTURE,
    mode: 'Linear / Evade & Collect',
    controls: 'WASD: Move | Gather Shards | Avoid Hostile Patrols',
  },
  {
    key: 'survival',
    name: 'Swarm Survival',
    archetype: 'survival',
    dsl: SURVIVAL_FIXTURE,
    mode: 'Linear / Swarm Dodging',
    controls: 'WASD: Move | Dodge Hunter Drones | Collect Energy Orbs',
  },
  {
    key: 'runner',
    name: 'Skyline Runner',
    archetype: 'runner',
    dsl: RUNNER_FIXTURE,
    mode: 'Continuous / Gravity 700',
    controls: 'D: Sprint | SPACE: Jump Obstacles | Extraction Pad',
  },
  {
    key: 'arena_ow',
    name: 'Open World (Arena)',
    archetype: 'arena',
    dsl: {
      ...OPEN_WORLD_FIXTURE,
      metadata: { ...OPEN_WORLD_FIXTURE.metadata, title: 'District Arena Operations', archetype: 'arena' },
      player: { ...OPEN_WORLD_FIXTURE.player, attack_type: 'melee' },
    },
    mode: 'Open World / Melee Combat',
    controls: 'WASD: Move | Click/F: Melee Attack | E: Vehicle/Interact',
  },
  {
    key: 'shooter_ow',
    name: 'Open World (Shooter)',
    archetype: 'shooter',
    dsl: {
      ...OPEN_WORLD_FIXTURE,
      metadata: { ...OPEN_WORLD_FIXTURE.metadata, title: 'District Recon Shooter', archetype: 'shooter' },
      player: { ...OPEN_WORLD_FIXTURE.player, attack_type: 'ranged' },
    },
    mode: 'Open World / Ranged Combat',
    controls: 'WASD: Move | Click: Fire Plasma | E: Vehicle/Interact',
  },
  {
    key: 'collector_ow',
    name: 'Open World (Collector)',
    archetype: 'collector',
    dsl: {
      ...OPEN_WORLD_FIXTURE,
      metadata: { ...OPEN_WORLD_FIXTURE.metadata, title: 'District Data Smuggler', archetype: 'collector' },
      player: { ...OPEN_WORLD_FIXTURE.player, attack_type: 'none' },
    },
    mode: 'Open World / Salvage Operations',
    controls: 'WASD: Move | E: Gather & Interact | Evade Hostiles',
  },
  {
    key: 'survival_ow',
    name: 'Open World (Survival)',
    archetype: 'survival',
    dsl: {
      ...OPEN_WORLD_FIXTURE,
      metadata: { ...OPEN_WORLD_FIXTURE.metadata, title: 'District Lockdown Survival', archetype: 'survival' },
      player: { ...OPEN_WORLD_FIXTURE.player, attack_type: 'none' },
    },
    mode: 'Open World / Sector Lockdown',
    controls: 'WASD: Move | E: Commandeer Vehicle / Interact | Evade Threat',
  },
];

export const PlaytestPage: React.FC = () => {
  const [selectedKey, setSelectedKey] = useState<string>('platformer');
  const [lastSummary, setLastSummary] = useState<PlaytestSummary | null>(null);

  const selectedOption = OPTIONS.find((o) => o.key === selectedKey) || OPTIONS[0];

  const handlePlaytestComplete = (summary: PlaytestSummary) => {
    setLastSummary(summary);
  };

  return (
    <div className="min-h-screen bg-[#070912] text-white flex flex-col p-4">
      {/* Header & Archetype Selector */}
      <div className="max-w-6xl mx-auto w-full mb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cyan-500/30 pb-3">
          <div>
            <h1 className="text-xl font-mono font-bold text-cyan-400 flex items-center gap-2">
              <span className="material-symbols-outlined text-cyan-400">sports_esports</span>
              GAMEFORGE AI — RUNTIME ARCHETYPE PLAYTEST
            </h1>
            <p className="text-xs text-gray-400 font-mono">
              Executable QA Matrix across all 6 archetypes, world modes, and viewports.
            </p>
          </div>
          {lastSummary && (
            <div
              id="playtest-outcome-badge"
              className={`text-xs font-mono px-3 py-1 rounded border font-bold uppercase ${
                lastSummary.outcome === 'WON'
                  ? 'bg-green-500/20 text-green-400 border-green-500/40'
                  : 'bg-red-500/20 text-red-400 border-red-500/40'
              }`}
            >
              LAST OUTCOME: {lastSummary.outcome} (SCORE: {lastSummary.score})
            </div>
          )}
        </div>

        {/* Archetype Buttons */}
        <div className="flex flex-wrap gap-2 mt-3">
          {OPTIONS.map((opt) => (
            <button
              key={opt.key}
              id={`btn-archetype-${opt.key}`}
              onClick={() => {
                setSelectedKey(opt.key);
                setLastSummary(null);
              }}
              className={`px-3 py-1.5 rounded font-mono text-xs uppercase tracking-wider transition-all border ${
                selectedKey === opt.key
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400 shadow-[0_0_10px_rgba(0,240,255,0.3)]'
                  : 'bg-black/40 text-gray-400 border-gray-800 hover:border-gray-600 hover:text-gray-200'
              }`}
            >
              {opt.name}
            </button>
          ))}
        </div>

        {/* Current Archetype Info Bar */}
        <div className="mt-3 p-2.5 rounded bg-black/50 border border-gray-800/80 flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
          <div className="flex items-center gap-4">
            <span className="text-cyan-400 font-bold">MODE: {selectedOption.mode}</span>
            <span className="text-gray-400">CONTROLS: {selectedOption.controls}</span>
          </div>
          <div className="text-gray-500 text-[11px]">
            HOTKEYS: [P] PAUSE / RESUME | [R] RESTART
          </div>
        </div>
      </div>

      {/* Phaser Canvas Container */}
      <div className="flex-1 flex items-center justify-center max-w-6xl mx-auto w-full">
        <div
          id="phaser-playtest-viewport"
          className="w-full flex justify-center bg-black/60 rounded border border-cyan-500/20 overflow-hidden shadow-2xl p-2"
        >
          <PhaserCanvas
            key={selectedKey}
            gameDsl={selectedOption.dsl}
            seed={18492031}
            onPlaytestComplete={handlePlaytestComplete}
          />
        </div>
      </div>
    </div>
  );
};

export default PlaytestPage;
