import React, { useState } from 'react';
import type { RemixIntentType } from '../../types';
import { REMIX_INTENT_LABELS } from '../../types';

const MAX_SELECTABLE_INTENTS = 3;

// Closed vocabulary of remix options, matching the server's RemixIntentType exactly.
// "Add Boss" and "More Vehicles" are deliberately absent -- those runtime
// capabilities don't exist yet (boss/finale is Phase 5, vehicles are Phase 6), and
// offering them here would promise something the game can't actually deliver.
const REMIX_OPTIONS: RemixIntentType[] = [
  'increase_combat',
  'increase_exploration',
  'increase_difficulty',
  'decrease_difficulty',
  'add_levels',
  'more_story',
  'faster_pace',
  'more_enemies',
  'change_theme',
];

// Mirrors the server's mutually-exclusive pair check (app.schemas.remix) so the
// contradictory combination is disabled in the UI instead of round-tripping a 422.
const MUTUALLY_EXCLUSIVE: [RemixIntentType, RemixIntentType][] = [
  ['increase_difficulty', 'decrease_difficulty'],
];

interface RemixPanelProps {
  isOpen: boolean;
  isApplying: boolean;
  error: string | null;
  onApply: (intents: RemixIntentType[]) => void;
  onCancel: () => void;
}

export const RemixPanel: React.FC<RemixPanelProps> = ({ isOpen, isApplying, error, onApply, onCancel }) => {
  const [selected, setSelected] = useState<RemixIntentType[]>([]);

  if (!isOpen) return null;

  const isExcludedBy = (type: RemixIntentType): boolean =>
    MUTUALLY_EXCLUSIVE.some(([a, b]) => (a === type && selected.includes(b)) || (b === type && selected.includes(a)));

  const toggle = (type: RemixIntentType) => {
    setSelected((prev) => {
      if (prev.includes(type)) return prev.filter((t) => t !== type);
      if (prev.length >= MAX_SELECTABLE_INTENTS) return prev;
      if (isExcludedBy(type)) return prev;
      return [...prev, type];
    });
  };

  return (
    <div className="bg-terminal-bg border border-secondary/40 rounded p-3 flex flex-col gap-3 font-mono text-xs animate-fadeIn">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-secondary text-sm">shuffle</span>
        <span className="font-bold text-secondary uppercase tracking-wide">Remix This Game</span>
        <span className="text-[10px] text-on-surface-variant ml-auto">
          {selected.length}/{MAX_SELECTABLE_INTENTS} selected
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
        {REMIX_OPTIONS.map((type) => {
          const isSelected = selected.includes(type);
          const excluded = !isSelected && isExcludedBy(type);
          const disabled = !isSelected && (selected.length >= MAX_SELECTABLE_INTENTS || excluded);
          return (
            <button
              key={type}
              type="button"
              disabled={disabled}
              onClick={() => toggle(type)}
              title={excluded ? 'Cannot combine with the opposite difficulty option.' : undefined}
              className={`px-2 py-1.5 rounded border text-[11px] font-bold uppercase transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 ${
                isSelected
                  ? 'bg-secondary/20 border-secondary text-secondary'
                  : 'bg-surface/40 border-primary/20 text-on-surface-variant hover:bg-surface/80'
              }`}
            >
              {REMIX_INTENT_LABELS[type]}
            </button>
          );
        })}
      </div>

      {error && <div className="text-red-400 text-[11px]">{error}</div>}

      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          disabled={isApplying}
          className="px-3 py-1.5 text-xs font-mono rounded border border-primary/20 text-on-surface-variant hover:text-on-surface transition-colors cursor-pointer disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => onApply(selected)}
          disabled={isApplying || selected.length === 0}
          className="px-4 py-1.5 text-xs font-mono font-bold rounded bg-secondary text-surface hover:bg-secondary/90 transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50"
        >
          <span className="material-symbols-outlined text-sm">auto_awesome</span>
          <span>{isApplying ? 'REMIXING...' : 'APPLY REMIX'}</span>
        </button>
      </div>
    </div>
  );
};
