import React, { useEffect, useState } from 'react';
import type { GameProject, GameBlueprint } from '../../types';
import { projectService } from '../../services/projects';
import { StudioInspirationDeck } from './StudioInspirationDeck';

interface StudioOverviewTabProps {
  project: GameProject;
  onCloseStudio?: () => void;
}

export const StudioOverviewTab: React.FC<StudioOverviewTabProps> = ({ project, onCloseStudio }) => {
  const [blueprint, setBlueprint] = useState<GameBlueprint | null>(null);
  const [isLoadingBlueprint, setIsLoadingBlueprint] = useState(false);

  useEffect(() => {
    let mounted = true;
    if (project.id) {
      setIsLoadingBlueprint(true);
      projectService.getBlueprint(project.id)
        .then((bp) => {
          if (mounted) setBlueprint(bp);
        })
        .catch((err) => {
          console.warn('Could not load blueprint in StudioOverviewTab:', err);
        })
        .finally(() => {
          if (mounted) setIsLoadingBlueprint(false);
        });
    }
    return () => {
      mounted = false;
    };
  }, [project.id]);

  const designSpec = project.designSpec;
  const coreLoop = blueprint?.core_loop || designSpec?.core_gameplay_loop;
  const elevatorPitch = blueprint?.player_fantasy || designSpec?.elevator_pitch;
  const objectives = blueprint?.objectives || [];
  const mechanics = blueprint?.supported_mechanics || designSpec?.player_abilities || [];

  return (
    <div className="space-y-6 font-mono text-sm">
      {/* Elevator Pitch & Core Loop Deck */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-surface-container-low border border-primary/30 p-4 rounded-sm space-y-3">
          <div className="flex items-center gap-2 text-primary font-bold text-xs uppercase tracking-wider">
            <span className="material-symbols-outlined text-sm">auto_stories</span>
            <span>Narrative Premise & Theme</span>
          </div>
          <p className="text-on-surface/90 text-xs leading-relaxed font-sans">
            {elevatorPitch || (
              <span className="text-outline italic">No narrative premise provided.</span>
            )}
          </p>
          {designSpec?.theme && (
            <div className="pt-2 border-t border-outline-variant/30 flex items-center gap-2 text-xs">
              <span className="text-on-surface-variant">Theme:</span>
              <span className="text-secondary font-bold uppercase">{designSpec.theme}</span>
            </div>
          )}
        </div>

        <div className="bg-surface-container-low border border-primary/30 p-4 rounded-sm space-y-3">
          <div className="flex items-center gap-2 text-primary font-bold text-xs uppercase tracking-wider">
            <span className="material-symbols-outlined text-sm">sync</span>
            <span>Core Gameplay Loop</span>
          </div>
          <p className="text-on-surface/90 text-xs leading-relaxed font-sans">
            {coreLoop || (
              <span className="text-outline italic">Standard interactive arcade loop.</span>
            )}
          </p>
          <div className="pt-2 border-t border-outline-variant/30 flex items-center gap-2 text-xs">
            <span className="text-on-surface-variant">Genre:</span>
            <span className="text-secondary font-bold uppercase">{project.genre}</span>
          </div>
        </div>
      </div>

      {/* Objectives & Mechanics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Objectives */}
        <div className="bg-surface-container-low border border-outline-variant/50 p-4 rounded-sm space-y-3">
          <div className="flex items-center gap-2 text-secondary font-bold text-xs uppercase tracking-wider">
            <span className="material-symbols-outlined text-sm">flag</span>
            <span>Key Objectives</span>
          </div>
          {isLoadingBlueprint ? (
            <div className="text-xs text-outline animate-pulse">Loading mission parameters...</div>
          ) : objectives.length > 0 ? (
            <ul className="space-y-1.5 text-xs text-on-surface/90">
              {objectives.map((obj, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-secondary text-[10px] mt-0.5">▶</span>
                  <span className="font-sans">{typeof obj === 'string' ? obj : obj.description}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-xs text-outline italic">Defeat targets and survive.</div>
          )}
        </div>

        {/* Mechanics */}
        <div className="bg-surface-container-low border border-outline-variant/50 p-4 rounded-sm space-y-3">
          <div className="flex items-center gap-2 text-secondary font-bold text-xs uppercase tracking-wider">
            <span className="material-symbols-outlined text-sm">bolt</span>
            <span>Supported Mechanics</span>
          </div>
          {mechanics.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {mechanics.map((mech, idx) => (
                <span
                  key={idx}
                  className="text-[10px] bg-surface-container-highest border border-outline-variant px-2 py-0.5 uppercase text-on-surface font-mono rounded"
                >
                  {typeof mech === 'string' ? mech : (mech as { name?: string }).name || String(mech)}
                </span>
              ))}
            </div>
          ) : (
            <div className="text-xs text-outline italic">Standard locomotion & collision mechanics.</div>
          )}
        </div>
      </div>

      {/* World & Build Parameters */}
      <div className="bg-surface-container-low border border-outline-variant/50 p-4 rounded-sm space-y-3">
        <h3 className="text-xs text-secondary uppercase tracking-widest font-bold flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">tune</span>
          <span>Build Specifications</span>
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="bg-surface p-2.5 rounded border border-outline-variant/30">
            <div className="text-on-surface-variant text-[10px]">ENGINE</div>
            <div className="text-primary font-bold">{project.parameters.engine}</div>
          </div>
          <div className="bg-surface p-2.5 rounded border border-outline-variant/30">
            <div className="text-on-surface-variant text-[10px]">ART DENSITY</div>
            <div className="text-on-surface font-bold">{project.parameters.artDensity}%</div>
          </div>
          <div className="bg-surface p-2.5 rounded border border-outline-variant/30">
            <div className="text-on-surface-variant text-[10px]">PHYSICS</div>
            <div className="text-on-surface font-bold">{project.parameters.physics}%</div>
          </div>
          <div className="bg-surface p-2.5 rounded border border-outline-variant/30">
            <div className="text-on-surface-variant text-[10px]">SCALE / WORLD</div>
            <div className="text-on-surface font-bold uppercase">{project.parameters.scale} ({project.parameters.worldMode})</div>
          </div>
        </div>

        {/* Modules & AI Model */}
        <div className="pt-2 flex flex-wrap justify-between items-center gap-2 text-xs border-t border-outline-variant/20">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-on-surface-variant text-[10px]">LOGIC MODULES:</span>
            {project.parameters.modules.length > 0 ? (
              project.parameters.modules.map((mod) => (
                <span key={mod} className="text-[10px] bg-primary/10 text-primary border border-primary/30 px-1.5 py-0.5 uppercase rounded font-bold">
                  {mod}
                </span>
              ))
            ) : (
              <span className="text-outline italic text-[11px]">None</span>
            )}
          </div>
          {project.runtimeMetadata?.model && (
            <div className="flex items-center gap-1.5 text-[11px]">
              <span className="text-on-surface-variant">AI Model:</span>
              <span className="text-primary font-bold">
                {project.runtimeMetadata.model.includes('gemini-3-flash-preview')
                  ? 'Gemini 3 Flash'
                  : project.runtimeMetadata.model.includes('gemma-4-31b-it')
                  ? 'Gemma 4 31B'
                  : project.runtimeMetadata.model}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Creation Prompt */}
      <div className="space-y-2">
        <h3 className="text-xs text-secondary uppercase tracking-widest font-bold flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">terminal</span>
          <span>Original Prompt</span>
        </h3>
        <div className="bg-surface-container-lowest border border-outline-variant/50 p-3 text-xs text-on-surface/80 rounded font-mono max-h-28 overflow-y-auto whitespace-pre-wrap leading-relaxed">
          {project.prompt}
        </div>
      </div>

      {/* Inspiration Deck & Synergy Section */}
      <StudioInspirationDeck project={project} onCloseStudio={onCloseStudio} />
    </div>
  );
};
