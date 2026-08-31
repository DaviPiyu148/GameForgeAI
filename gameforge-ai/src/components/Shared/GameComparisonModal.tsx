import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { discoveryService } from '../../services/discovery';
import type { CompareGamesResponse } from '../../types';

interface GameComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedGameIds: string[];
  onRemoveGame: (gameId: string) => void;
}

export const GameComparisonModal: React.FC<GameComparisonModalProps> = ({
  isOpen,
  onClose,
  selectedGameIds,
  onRemoveGame,
}) => {
  const [data, setData] = useState<CompareGamesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || selectedGameIds.length < 2) {
      setData(null);
      return;
    }

    const fetchComparison = async () => {
      setIsLoading(true);
      try {
        const res = await discoveryService.compareGames(selectedGameIds);
        setData(res);
      } catch (err) {
        console.warn('Failed to load comparison:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchComparison();
  }, [isOpen, selectedGameIds]);

  // Lock body scroll while modal is open
  useEffect(() => {
    if (isOpen) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [isOpen]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm modal-backdrop-enter"
      role="dialog"
      aria-modal="true"
      aria-label="Game comparison modal"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="relative w-full max-w-4xl max-h-[90vh] bg-surface border-2 border-primary shadow-[0_0_30px_rgba(76,224,210,0.25)] rounded-sm p-6 flex flex-col space-y-4 overflow-hidden modal-enter z-10"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-primary/30 pb-3">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-xl">compare_arrows</span>
            <h2 className="font-display text-lg text-white uppercase tracking-wider">
              Compare Games ({selectedGameIds.length}/3)
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer"
            aria-label="Close comparison dialog"
          >
            <span className="material-symbols-outlined text-base">close</span>
          </button>
        </div>

        {isLoading ? (
          <div className="py-20 text-center font-mono text-xs text-primary animate-pulse">
            COMPILING COMPARISON MATRIX...
          </div>
        ) : !data || data.games.length === 0 ? (
          <div className="py-12 text-center font-mono text-xs text-on-surface-variant">
            Select at least 2 games from discovery cards to inspect side-by-side comparison.
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto space-y-6 pr-1">
            {/* Comparison Grid */}
            <div
              className="grid gap-4"
              style={{ gridTemplateColumns: `repeat(${data.games.length}, minmax(0, 1fr))` }}
            >
              {data.games.map((g) => (
                <div
                  key={g.id}
                  className="bg-surface-container-low border border-primary/20 rounded p-3 space-y-3 relative"
                >
                  <button
                    type="button"
                    onClick={() => onRemoveGame(g.id)}
                    className="absolute top-2 right-2 text-on-surface-variant hover:text-secondary text-xs cursor-pointer"
                    title="Remove from comparison"
                    aria-label={`Remove ${g.title} from comparison`}
                  >
                    ✕
                  </button>

                  <div className="space-y-1">
                    <h4 className="font-bold text-white text-sm font-display truncate">
                      {g.title}
                    </h4>
                    <p className="text-[10px] font-mono text-on-surface-variant">
                      {g.release_year > 0 ? g.release_year : 'Classic'} // {g.is_free ? 'FREE' : 'PAID'}
                    </p>
                  </div>

                  {/* Rating Badge */}
                  <div className="text-[11px] font-mono flex items-center gap-1 text-emerald-400">
                    <span className="material-symbols-outlined text-xs">thumb_up</span>
                    <span>{g.positive_percent}% positive</span>
                    <span className="text-on-surface-variant text-[9px]">({g.total_reviews} reviews)</span>
                  </div>

                  {/* Genres */}
                  <div className="space-y-1 pt-1 border-t border-primary/20">
                    <span className="text-[10px] font-mono text-primary font-bold uppercase">Genres</span>
                    <div className="flex flex-wrap gap-1">
                      {g.genres.slice(0, 3).map((gen) => (
                        <span
                          key={gen}
                          className="px-1.5 py-0.5 bg-primary/10 text-primary text-[10px] font-mono rounded"
                        >
                          {gen}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Modes */}
                  <div className="space-y-1 pt-1 border-t border-primary/20">
                    <span className="text-[10px] font-mono text-secondary font-bold uppercase">Modes</span>
                    <div className="text-[11px] font-mono text-on-surface">
                      {g.player_modes.join(', ') || 'Single-player'}
                    </div>
                  </div>

                  {/* Platforms */}
                  <div className="space-y-1 pt-1 border-t border-primary/20">
                    <span className="text-[10px] font-mono text-tertiary font-bold uppercase">Platforms</span>
                    <div className="text-[11px] font-mono text-on-surface truncate">
                      {g.platforms.join(', ') || 'PC'}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Overlap Summary */}
            <div className="bg-surface-container-low border border-primary/20 rounded p-4 space-y-3">
              <h4 className="font-mono text-xs text-primary font-bold uppercase tracking-wider">
                Common Ground & Differentiators
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
                <div>
                  <span className="text-on-surface-variant block mb-1">SHARED ATTRIBUTES:</span>
                  <div className="text-white space-y-0.5">
                    <div>Genres: {data.common_genres.join(', ') || 'None'}</div>
                    <div>Modes: {data.common_modes.join(', ') || 'None'}</div>
                  </div>
                </div>
                <div>
                  <span className="text-on-surface-variant block mb-1">DISTINCT TAGS:</span>
                  <div className="flex flex-wrap gap-1">
                    {data.differentiating_tags.map((t) => (
                      <span key={t} className="px-1.5 py-0.5 bg-surface-container border border-primary/20 rounded text-[10px] text-on-surface">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex justify-end pt-2 border-t border-primary/20">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive energy-sweep glow-cyan cursor-pointer"
          >
            Close Comparison
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
