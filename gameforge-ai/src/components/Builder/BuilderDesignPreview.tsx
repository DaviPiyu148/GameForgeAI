import React, { useMemo } from 'react';
import type { BuildParams } from '../../types';

interface BuilderDesignPreviewProps {
  params: BuildParams;
  prompt?: string;
}

export const BuilderDesignPreview: React.FC<BuilderDesignPreviewProps> = ({ params, prompt = '' }) => {
  const worldMode = params.world_mode || 'linear';
  const scale = params.scale || 'standard';
  const engine = params.engine || 'Top-Down Action';


  // Deterministically infer core experience and active systems from prompt + builder options
  const inferredDesign = useMemo(() => {
    const text = prompt.toLowerCase();
    
    // Inferred genre
    let genre = engine.replace('2D ', '');
    if (text.includes('cyberpunk')) genre = 'Cyberpunk ' + genre;
    else if (text.includes('space') || text.includes('sci-fi')) genre = 'Sci-Fi ' + genre;
    else if (text.includes('dungeon') || text.includes('fantasy')) genre = 'Fantasy ' + genre;

    // Inferred core loop
    let coreLoop = 'Evade -> Challenge -> Upgrade -> Win';
    if (engine.includes('Platformer')) coreLoop = 'Traverse -> Jump -> Collect -> Goal';
    else if (engine.includes('Collector')) coreLoop = 'Sweep -> Evade -> Gather -> Clear';
    else if (worldMode === 'open_world' || text.includes('courier')) coreLoop = 'Infiltrate -> Mission -> Evade -> Escape';

    // Systems detected
    const systems: string[] = [];
    const activeModules = params.modules || [];
    if (activeModules.some(m => m.includes('Combat')) || text.includes('combat') || text.includes('shoot')) systems.push('Combat');
    if (activeModules.some(m => m.includes('Mobility')) || text.includes('dash')) systems.push('Dash');
    if (text.includes('vehicle') || text.includes('car') || text.includes('drive')) systems.push('Vehicles');
    if (text.includes('faction') || text.includes('rival')) systems.push('Factions');
    if (text.includes('threat') || text.includes('police') || text.includes('security')) systems.push('Threat Meter');
    if (text.includes('boss') || scale === 'campaign') systems.push('Boss / Finale');
    if (text.includes('activity') || text.includes('mission') || text.includes('hack')) systems.push('Activities');

    return { genre, coreLoop, systems: Array.from(new Set<string>(systems)) };
  }, [prompt, engine, worldMode, scale, params.modules]);




  // Level budget range by scale
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
      <div className="relative z-10 flex items-center justify-between border-b border-primary/20 pb-2 mb-2">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span className="font-mono text-[10px] text-primary uppercase font-bold tracking-wider">
            DESIGN BRIEF PREVIEW
          </span>
        </div>
        <span className="font-mono text-[9px] text-on-surface-variant uppercase px-1.5 py-0.5 bg-surface-container border border-outline-variant/40 rounded-xs">
          {worldMode === 'open_world' ? 'OPEN WORLD' : worldMode === 'campaign' ? 'CAMPAIGN' : 'LINEAR ARENA'}
        </span>
      </div>

      {/* Core Design Brief Summary */}
      <div className="relative z-10 space-y-1.5 font-mono text-[10px] py-1">
        <div className="flex items-center justify-between text-on-surface">
          <span className="text-on-surface-variant">INFERRED GENRE:</span>
          <span className="text-primary font-bold">{inferredDesign.genre}</span>
        </div>
        <div className="flex items-center justify-between text-on-surface">
          <span className="text-on-surface-variant">TARGET SCALE:</span>
          <span className="text-secondary-soft font-bold uppercase">{scale} ({levelBudget})</span>
        </div>
        <div className="flex items-center justify-between text-on-surface">
          <span className="text-on-surface-variant">CORE LOOP:</span>
          <span className="text-amber-300 font-bold truncate max-w-[170px] text-right" title={inferredDesign.coreLoop}>
            {inferredDesign.coreLoop}
          </span>
        </div>
      </div>

      {/* Dynamic Schematic Visualization */}
      <div className="relative z-10 py-1.5 min-h-[72px] flex flex-col justify-center border-t border-b border-primary/10 my-1">
        {worldMode === 'open_world' ? (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-[10px] font-mono px-2 py-0.5 bg-surface-container-high/60 border border-primary/30 rounded-xs">
              <span className="text-primary flex items-center gap-1">
                <span className="material-symbols-outlined text-[12px]">location_city</span>
                DISTRICT 1
              </span>
              <span className="text-secondary-soft text-[9px]">➔ POI ➔</span>
              <span className="text-secondary-soft flex items-center gap-1">
                <span className="material-symbols-outlined text-[12px]">hub</span>
                CORE ZONE
              </span>
            </div>
            <div className="flex items-center justify-between text-[10px] font-mono px-2 py-0.5 bg-surface-container-high/60 border border-secondary-soft/30 rounded-xs">
              <span className="text-secondary-soft flex items-center gap-1">
                <span className="material-symbols-outlined text-[12px]">explore</span>
                OUTSKIRTS
              </span>
              <span className="text-primary text-[9px]">➔ THREAT ➔</span>
              <span className="text-primary flex items-center gap-1">
                <span className="material-symbols-outlined text-[12px]">security</span>
                RESTRICTED
              </span>
            </div>
          </div>
        ) : worldMode === 'campaign' ? (
          <div className="flex items-center justify-between gap-1 font-mono text-[9px] py-1">
            <div className="flex-1 text-center p-1 bg-surface-container border border-primary/40 rounded-xs">
              <div className="text-primary font-bold">STAGE 1</div>
              <div className="text-[8px] text-on-surface-variant">Intro</div>
            </div>
            <span className="text-primary text-[9px]">➔</span>
            <div className="flex-1 text-center p-1 bg-surface-container border border-secondary-soft/40 rounded-xs">
              <div className="text-secondary-soft font-bold">STAGE 2</div>
              <div className="text-[8px] text-on-surface-variant">Escalate</div>
            </div>
            <span className="text-secondary-soft text-[9px]">➔</span>
            <div className="flex-1 text-center p-1 bg-primary/10 border border-primary text-primary rounded-xs">
              <div className="font-bold text-amber-300">FINALE</div>
              <div className="text-[8px] text-amber-300/80">Climax</div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-1 font-mono text-[9px] py-1">
            <div className="text-center p-1 bg-primary/10 border border-primary/40 rounded-xs">
              <span className="text-primary font-bold">PLAYER</span>
            </div>
            <span className="text-primary text-[9px]">➔</span>
            <div className="text-center p-1 bg-surface-container border border-secondary-soft/40 rounded-xs">
              <span className="text-secondary-soft font-bold">CHALLENGE</span>
            </div>
            <span className="text-secondary-soft text-[9px]">➔</span>
            <div className="text-center p-1 bg-emerald-500/10 border border-emerald-400/50 rounded-xs">
              <span className="text-emerald-400 font-bold">VICTORY</span>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Requested Systems Tags */}
      <div className="relative z-10 pt-1 flex flex-wrap items-center gap-1 font-mono text-[8.5px]">
        <span className="text-on-surface-variant/70 uppercase">Systems:</span>
        {inferredDesign.systems.length > 0 ? (
          inferredDesign.systems.map((s) => (
            <span key={s} className="px-1 py-0.2 bg-primary/10 text-primary border border-primary/30 rounded-xs">
              {s}
            </span>
          ))
        ) : (
          <span className="text-on-surface-variant">Standard Arcade Primitives</span>
        )}
      </div>
    </div>
  );
};
