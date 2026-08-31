import React, { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import type { DiscoverySessionContext } from '../../types';
import { useModalDialog } from '../../hooks/useModalDialog';

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
  const [localRefinements, setLocalRefinements] = useState<string[]>(
    sessionContext.refinements || []
  );
  const [localAvoidTags, setLocalAvoidTags] = useState<string[]>(
    sessionContext.temporary_avoid_tags || []
  );
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  const { isClosing, handleClose, handleBackdropClick, dialogRef } = useModalDialog({
    isOpen,
    onClose,
    initialFocusRef: closeBtnRef,
    closeDelayMs: 200,
  });

  useEffect(() => {
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
    handleClose();
  };

  const handleReset = () => {
    setLocalRefinements([]);
    setLocalAvoidTags([]);
    onReset();
    handleClose();
  };

  return createPortal(
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm ${
        isClosing ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
      }`}
      role="dialog"
      aria-modal="true"
      aria-label="Tune recommendations dialog"
      onClick={handleBackdropClick}
    >
      <div
        ref={dialogRef}
        className={`w-full max-w-lg max-h-[90vh] overflow-y-auto bg-surface border-2 border-primary shadow-[0_0_30px_rgba(76,224,210,0.25)] flex flex-col rounded-sm relative z-10 p-6 space-y-6 ${
          isClosing ? 'modal-exit' : 'modal-enter'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-primary/30 pb-3">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-xl">tune</span>
            <h2 className="font-display text-lg text-white uppercase tracking-wider">
              Tune Your Discovery
            </h2>
          </div>
          <button
            ref={closeBtnRef}
            onClick={handleClose}
            className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer min-w-[32px] min-h-[32px] flex items-center justify-center"
            aria-label="Close tune dialog"
          >
            <span className="material-symbols-outlined text-base">close</span>
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
                  aria-pressed={isSelected}
                  aria-label={`Toggle preference for ${opt}`}
                  onClick={() => toggleRefinement(opt)}
                  className={`px-3 py-1.5 text-xs font-mono rounded border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-primary/20 border-primary text-primary font-bold shadow-[0_0_8px_rgba(76,224,210,0.3)]'
                      : 'bg-surface-container-low border-outline-variant/40 text-on-surface hover:border-primary/50 hover:text-primary'
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
                  aria-pressed={isSelected}
                  aria-label={`Toggle avoidance for ${tag}`}
                  onClick={() => toggleAvoidTag(tag)}
                  className={`px-3 py-1.5 text-xs font-mono rounded border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-secondary/20 border-secondary text-secondary font-bold shadow-[0_0_8px_rgba(255,61,129,0.3)]'
                      : 'bg-surface-container-low border-outline-variant/40 text-on-surface hover:border-secondary/50 hover:text-secondary'
                  }`}
                >
                  - {tag}
                </button>
              );
            })}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-between items-center pt-4 border-t border-primary/20">
          <button
            type="button"
            onClick={handleReset}
            className="px-3 py-1.5 text-xs font-mono text-on-surface-variant hover:text-primary transition-colors cursor-pointer"
          >
            Reset Filters
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-outline-variant text-on-surface font-mono text-xs uppercase rounded hover:border-primary/50 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleApply}
              className="px-5 py-2 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive energy-sweep glow-cyan cursor-pointer"
            >
              Apply Tune
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};
