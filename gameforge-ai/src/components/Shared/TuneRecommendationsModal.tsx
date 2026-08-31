import React from 'react';
import type { DiscoverySessionContext } from '../../types';

interface TuneRecommendationsModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionContext: DiscoverySessionContext;
  onApply: (newContext: DiscoverySessionContext) => void;
  onReset: () => void;
}

const MORE_OPTIONS = ['Exploration', 'Story', 'Co-op', 'RPG', 'Action', 'Building'];
const LESS_OPTIONS = ['Combat', 'Horror', 'Competitive', 'Grind', 'Stealth'];

export const TuneRecommendationsModal: React.FC<TuneRecommendationsModalProps> = ({
  isOpen,
  onClose,
  sessionContext,
  onApply,
  onReset,
}) => {
  const [localRefinements, setLocalRefinements] = React.useState<string[]>(
    sessionContext.refinements || []
  );
  const [localAvoidTags, setLocalAvoidTags] = React.useState<string[]>(
    sessionContext.temporary_avoid_tags || []
  );

  React.useEffect(() => {
    setLocalRefinements(sessionContext.refinements || []);
    setLocalAvoidTags(sessionContext.temporary_avoid_tags || []);
  }, [sessionContext]);

  if (!isOpen) return null;

  const toggleRefinement = (opt: string) => {
    setLocalRefinements((prev) =>
      prev.includes(opt) ? prev.filter((o) => o !== opt) : [...prev, opt]
    );
  };

  const toggleAvoidTag = (tag: string) => {
    const norm = tag.toLowerCase();
    setLocalAvoidTags((prev) =>
      prev.includes(norm) ? prev.filter((t) => t !== norm) : [...prev, norm]
    );
  };

  const handleApply = () => {
    onApply({
      ...sessionContext,
      refinements: localRefinements,
      temporary_avoid_tags: localAvoidTags,
    });
    onClose();
  };

  const handleReset = () => {
    setLocalRefinements([]);
    setLocalAvoidTags([]);
    onReset();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg bg-surface-container-low border border-outline-variant/60 rounded-sm shadow-2xl p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-outline-variant/40 pb-3">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-xl">tune</span>
            <h2 className="font-display text-lg text-white uppercase tracking-wider">
              Tune Your Discovery
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-on-surface-variant hover:text-white text-sm font-mono cursor-pointer"
          >
            ✕
          </button>
        </div>

        <p className="text-xs font-mono text-on-surface-variant leading-relaxed">
          Adjust your immediate session focus without permanently modifying your long-term Game DNA.
        </p>

        {/* Section 1: More Of */}
        <div className="space-y-2">
          <div className="text-xs font-mono text-primary font-bold uppercase tracking-wider flex items-center gap-1.5">
            <span>MORE OF:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {MORE_OPTIONS.map((opt) => {
              const isSelected = localRefinements.includes(opt);
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => toggleRefinement(opt)}
                  className={`px-2.5 py-1 text-xs font-mono rounded border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-primary/20 border-primary text-primary font-bold'
                      : 'bg-surface-container-highest/40 border-outline-variant/40 text-on-surface hover:border-outline-variant'
                  }`}
                >
                  + {opt}
                </button>
              );
            })}
          </div>
        </div>

        {/* Section 2: Less Of */}
        <div className="space-y-2">
          <div className="text-xs font-mono text-secondary font-bold uppercase tracking-wider flex items-center gap-1.5">
            <span>LESS OF:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {LESS_OPTIONS.map((tag) => {
              const norm = tag.toLowerCase();
              const isSelected = localAvoidTags.includes(norm);
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => toggleAvoidTag(tag)}
                  className={`px-2.5 py-1 text-xs font-mono rounded border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-secondary/20 border-secondary text-secondary font-bold'
                      : 'bg-surface-container-highest/40 border-outline-variant/40 text-on-surface hover:border-outline-variant'
                  }`}
                >
                  - {tag}
                </button>
              );
            })}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-between items-center pt-4 border-t border-outline-variant/40">
          <button
            type="button"
            onClick={handleReset}
            className="px-3 py-1.5 text-xs font-mono text-on-surface-variant hover:text-white cursor-pointer"
          >
            Reset Filters
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1.5 border border-outline-variant text-on-surface font-mono text-xs uppercase rounded cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleApply}
              className="px-5 py-1.5 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive cursor-pointer"
            >
              Apply Tune
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
