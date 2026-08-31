import React from 'react';
import type { BuildParams } from '../../types';

interface BuilderDesignPreviewProps {
  params: BuildParams;
}

export const BuilderDesignPreview: React.FC<BuilderDesignPreviewProps> = ({ params }) => {
  const worldMode = params.world_mode || 'linear';
  const scale = params.scale || 'standard';
  const engine = params.engine || 'Top-Down Action';
  const modules = params.modules || [];

  const hasVehicles = modules.some((m) => m.toLowerCase().includes('vehicle'));
  const hasBoss = modules.some((m) => m.toLowerCase().includes('boss'));
  const hasFactions = modules.some((m) => m.toLowerCase().includes('faction') || m.toLowerCase().includes('npc'));
  const hasWaveSpawner = modules.some((m) => m.toLowerCase().includes('wave') || m.toLowerCase().includes('spawn'));

  // Approximate level budget range by scale
  const levelBudget =
    scale === 'campaign' ? '3–5 Levels' : scale === 'standard' ? '2–3 Levels' : '1–2 Levels';

  return (
    <div className="bg-terminal-bg border border-secondary-soft/30 rounded relative overflow-hidden flex flex-col p-3 text-left">
      {/* Background cyber grid */}
      <div
        className="absolute inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage:
            'linear-gradient(rgba(105, 248, 234, 0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(105, 248, 234, 0.15) 1px, transparent 1px)',
          backgroundSize: '16px 16px',
        }}
      />

      {/* Top Header info bar */}
      <div className="relative z-10 flex items-center justify-between border-b border-primary/20 pb-2 mb-2.5">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span className="font-mono text-[10px] text-primary uppercase font-bold tracking-wider">
            DESIGN PREVIEW
          </span>
        </div>
        <span className="font-mono text-[9px] text-on-surface-variant uppercase px-1.5 py-0.5 bg-surface-container border border-outline-variant/40 rounded-xs">
          {worldMode === 'open_world' ? 'OPEN WORLD' : worldMode === 'campaign' ? 'CAMPAIGN' : 'LINEAR ARENA'}
        </span>
      </div>

      {/* Dynamic Schematic Visualization */}
      <div className="relative z-10 py-1 min-h-[96px] flex flex-col justify-center">
        {worldMode === 'open_world' ? (
          /* ── Open World Topology Schematic ── */
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-[10px] font-mono px-2 py-1 bg-surface-container-high/60 border border-primary/30 rounded-xs">
              <div className="flex items-center gap-1 text-primary">
                <span className="material-symbols-outlined text-[13px]">location_city</span>
                <span>DISTRICT A</span>
              </div>
              <span className="text-secondary-soft">──[ POI ]──</span>
              <div className="flex items-center gap-1 text-secondary-soft">
                <span className="material-symbols-outlined text-[13px]">hub</span>
                <span>CORE SECTOR</span>
              </div>
            </div>

            <div className="flex justify-around items-center text-[10px] font-mono text-on-surface-variant">
              <span className="text-primary/70">│</span>
              <span className="text-xs text-secondary-soft/80 font-bold">⚡ NETWORK</span>
              <span className="text-primary/70">│</span>
            </div>

            <div className="flex items-center justify-between text-[10px] font-mono px-2 py-1 bg-surface-container-high/60 border border-secondary-soft/30 rounded-xs">
              <div className="flex items-center gap-1 text-secondary-soft">
                <span className="material-symbols-outlined text-[13px]">explore</span>
                <span>OUTSKIRTS</span>
              </div>
              <span className="text-primary">──[ POI ]──</span>
              <div className="flex items-center gap-1 text-primary">
                <span className="material-symbols-outlined text-[13px]">security</span>
                <span>RESTRICTED</span>
              </div>
            </div>
          </div>
        ) : worldMode === 'campaign' ? (
          /* ── Multi-Level Campaign Progression ── */
          <div className="flex items-center justify-between gap-1 font-mono text-[10px] py-1">
            <div className="flex-1 text-center p-1.5 bg-surface-container border border-primary/40 rounded-xs">
              <div className="text-primary font-bold text-[9px]">STAGE 1</div>
              <div className="text-[8px] text-on-surface-variant">Infiltration</div>
            </div>
            <span className="text-primary text-[10px]">➔</span>
            <div className="flex-1 text-center p-1.5 bg-surface-container border border-secondary-soft/40 rounded-xs">
              <div className="text-secondary-soft font-bold text-[9px]">STAGE 2</div>
              <div className="text-[8px] text-on-surface-variant">Data Sweep</div>
            </div>
            <span className="text-secondary-soft text-[10px]">➔</span>
            <div className="flex-1 text-center p-1.5 bg-primary/10 border border-primary text-primary rounded-xs">
              <div className="font-bold text-[9px] text-amber-300">FINALE</div>
              <div className="text-[8px] text-amber-300/80">{hasBoss ? 'Boss Encounter' : 'Extraction'}</div>
            </div>
          </div>
        ) : (
          /* ── Linear / Arena Flow Schematic ── */
          <div className="flex items-center justify-between gap-1 font-mono text-[10px] py-1">
            <div className="text-center p-1.5 bg-primary/10 border border-primary/40 rounded-xs">
              <div className="text-primary font-bold text-[9px]">PLAYER</div>
              <div className="text-[8px] text-primary/70">{engine.split(' ')[0]}</div>
            </div>
            <span className="text-primary text-[10px]">➔</span>
            <div className="text-center p-1.5 bg-surface-container border border-secondary-soft/40 rounded-xs">
              <div className="text-secondary-soft font-bold text-[9px]">ARENA</div>
              <div className="text-[8px] text-on-surface-variant">{hasWaveSpawner ? 'Waves' : 'Encounter'}</div>
            </div>
            <span className="text-secondary-soft text-[10px]">➔</span>
            <div className="text-center p-1.5 bg-surface-container border border-error/40 rounded-xs">
              <div className="text-error font-bold text-[9px]">THREATS</div>
              <div className="text-[8px] text-on-surface-variant">Hazards</div>
            </div>
            <span className="text-error text-[10px]">➔</span>
            <div className="text-center p-1.5 bg-emerald-500/10 border border-emerald-400/50 rounded-xs">
              <div className="text-emerald-400 font-bold text-[9px]">GOAL</div>
              <div className="text-[8px] text-emerald-400/80">Victory</div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Configuration Metadata Indicators */}
      <div className="relative z-10 border-t border-primary/20 pt-2 mt-2 flex flex-wrap items-center justify-between gap-1 font-mono text-[9px]">
        <div className="flex items-center gap-1.5 text-on-surface-variant">
          <span>SCALE: <strong className="text-primary uppercase">{scale}</strong> ({levelBudget})</span>
        </div>
        <div className="flex items-center gap-1">
          {hasVehicles && (
            <span className="px-1 py-0.2 bg-secondary-soft/10 text-secondary-soft border border-secondary-soft/30 rounded-xs">
              VEHICLES
            </span>
          )}
          {hasFactions && (
            <span className="px-1 py-0.2 bg-primary/10 text-primary border border-primary/30 rounded-xs">
              FACTIONS
            </span>
          )}
          {hasBoss && (
            <span className="px-1 py-0.2 bg-amber-400/10 text-amber-300 border border-amber-400/30 rounded-xs">
              BOSS
            </span>
          )}
          <span className="text-on-surface-variant/60">
            {modules.length} MODULES
          </span>
        </div>
      </div>
    </div>
  );
};
