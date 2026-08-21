import React from 'react';
import type { GameBlueprint } from '../../types';

interface GameBlueprintPanelProps {
  blueprint: GameBlueprint | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Nontechnical-friendly presentation of a project's design -- title, genre, core
 * loop, levels, objectives, progression, supported mechanics, and finale. Every
 * value shown here is fetched directly from GET /projects/{id}/blueprint, which is
 * derived server-side purely from the project's already-validated GameDesignSpec +
 * GameDSL -- nothing here is fabricated or model chain-of-thought.
 */
export const GameBlueprintPanel: React.FC<GameBlueprintPanelProps> = ({ blueprint, isLoading, error }) => {
  if (isLoading) {
    return (
      <div className="bg-terminal-bg border border-primary/20 rounded p-3 font-mono text-xs text-on-surface-variant animate-pulse">
        Loading Game Blueprint...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-terminal-bg border border-red-500/30 rounded p-3 font-mono text-xs text-red-400">
        Blueprint unavailable: {error}
      </div>
    );
  }

  if (!blueprint) {
    return null;
  }

  return (
    <div className="bg-terminal-bg border border-primary/30 rounded p-3 flex flex-col gap-3 font-mono text-xs">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-primary text-sm">architecture</span>
        <span className="font-bold text-primary uppercase tracking-wide">Game Blueprint</span>
      </div>

      <div className="text-on-surface font-bold text-sm">{blueprint.title}</div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <div className="bg-surface/50 p-2 rounded border border-primary/15">
          <div className="text-on-surface-variant text-[10px] uppercase">Genre</div>
          <div className="text-on-surface">{blueprint.genre}</div>
        </div>
        <div className="bg-surface/50 p-2 rounded border border-primary/15">
          <div className="text-on-surface-variant text-[10px] uppercase">Player Fantasy</div>
          <div className="text-on-surface">{blueprint.player_fantasy}</div>
        </div>
        <div className="bg-surface/50 p-2 rounded border border-primary/15 sm:col-span-2">
          <div className="text-on-surface-variant text-[10px] uppercase">Core Loop</div>
          <div className="text-primary">{blueprint.core_loop}</div>
        </div>
        <div className="bg-surface/50 p-2 rounded border border-primary/15">
          <div className="text-on-surface-variant text-[10px] uppercase">Levels</div>
          <div className="text-on-surface">{blueprint.level_count}</div>
        </div>
        <div className="bg-surface/50 p-2 rounded border border-primary/15">
          <div className="text-on-surface-variant text-[10px] uppercase">Session Length</div>
          <div className="text-on-surface">{blueprint.estimated_session_length}</div>
        </div>
      </div>

      {blueprint.objectives.length > 0 && (
        <div>
          <div className="text-on-surface-variant text-[10px] uppercase mb-1">Objectives</div>
          <ul className="list-disc list-inside space-y-0.5 text-on-surface">
            {blueprint.objectives.map((obj, idx) => (
              <li key={idx}>
                {obj.level_number ? <span className="text-primary/80">Level {obj.level_number}: </span> : null}
                {obj.description}
              </li>
            ))}
          </ul>
        </div>
      )}

      {blueprint.progression.length > 0 && (
        <div>
          <div className="text-on-surface-variant text-[10px] uppercase mb-1">Progression</div>
          <ul className="list-disc list-inside space-y-0.5 text-on-surface">
            {blueprint.progression.map((p, idx) => (
              <li key={idx}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      {blueprint.supported_mechanics.length > 0 && (
        <div>
          <div className="text-on-surface-variant text-[10px] uppercase mb-1">Main Mechanics</div>
          <div className="flex flex-wrap gap-1.5">
            {blueprint.supported_mechanics.map((m) => (
              <span
                key={m}
                className="px-2 py-0.5 rounded bg-primary/15 border border-primary/30 text-primary text-[10px] uppercase font-bold"
              >
                {m}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="bg-surface/50 p-2 rounded border border-amber-500/20">
        <div className="text-on-surface-variant text-[10px] uppercase">Finale</div>
        <div className="text-amber-300">{blueprint.finale}</div>
      </div>
    </div>
  );
};
