/**
 * StudioInspirationDeck.tsx
 *
 * Step 3: Project Studio Inspiration Deck & Deterministic Synergy Preview
 *
 * Rules:
 * - Consumes persisted project inspirations via GET /api/projects/{id}/inspirations.
 * - Displays immutable historical snapshots stored against the project.
 * - Card deletion calls DELETE /api/projects/{id}/inspirations/{steam_app_id}.
 * - Alignment with project is derived at display time from stored genres vs current project.genre.
 * - Synergy is purely deterministic overlap across >= 2 inspirations (zero LLM, zero Gemini).
 */

import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GameProject, ProjectInspirationRecord } from '../../types';
import { inspirationService } from '../../services/inspirations';
import { pushToast } from '../../services/toastBus';
import { computeProjectAlignment, extractGameDNA } from '../../utils/gameDna';
import { computeInspirationSynergy } from '../../utils/synergy';

interface StudioInspirationDeckProps {
  project: GameProject;
  /** Optional callback to close the Studio modal before navigating */
  onCloseStudio?: () => void;
}

export const StudioInspirationDeck: React.FC<StudioInspirationDeckProps> = ({
  project,
  onCloseStudio,
}) => {
  const navigate = useNavigate();
  const [inspirations, setInspirations] = useState<ProjectInspirationRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Deletion interaction states
  const [confirmingAppId, setConfirmingAppId] = useState<string | null>(null);
  const [deletingAppId, setDeletingAppId] = useState<string | null>(null);

  const fetchInspirations = useCallback(async () => {
    if (!project.id) return;
    try {
      setIsLoading(true);
      setError(null);
      const data = await inspirationService.list(project.id);
      setInspirations(data);
    } catch (err: unknown) {
      console.error('Failed to load project inspirations:', err);
      setError('Could not load project inspirations. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [project.id]);

  useEffect(() => {
    fetchInspirations();
  }, [fetchInspirations]);

  const handleNavigateToDiscovery = () => {
    if (onCloseStudio) {
      onCloseStudio();
    }
    navigate('/');
  };

  const handleConfirmDetach = async (item: ProjectInspirationRecord) => {
    try {
      setDeletingAppId(item.steamAppId);
      await inspirationService.detach(project.id, item.steamAppId);
      setInspirations((prev) => prev.filter((i) => i.steamAppId !== item.steamAppId));
      setConfirmingAppId(null);
      pushToast({
        variant: 'info',
        title: 'INSPIRATION REMOVED',
        description: `"${item.title}" was removed from project inspirations.`,
      });
    } catch (err: unknown) {
      console.error('Failed to detach inspiration:', err);
      pushToast({
        variant: 'error',
        title: 'DETACH FAILED',
        description: 'Failed to remove inspiration. Please try again.',
      });
    } finally {
      setDeletingAppId(null);
    }
  };

  // Compute deterministic synergy for 2+ inspirations
  const synergy = computeInspirationSynergy(inspirations);
  const hasSynergy =
    synergy.sharedGenres.length > 0 ||
    synergy.sharedTags.length > 0 ||
    synergy.sharedPlayerModes.length > 0;

  return (
    <div className="space-y-4 font-mono" data-testid="studio-inspiration-deck">
      {/* Section Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant/40 pb-2.5">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-base" aria-hidden="true">
            lightbulb
          </span>
          <h3 className="text-xs uppercase tracking-widest font-bold text-primary">
            DESIGN INSPIRATIONS
          </h3>
          <span className="text-[10px] px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/30 font-bold">
            {inspirations.length}
          </span>
        </div>

        <button
          type="button"
          onClick={handleNavigateToDiscovery}
          className="px-2.5 py-1 bg-surface border border-primary/40 hover:border-primary text-primary hover:bg-primary/10 font-mono text-[11px] font-bold rounded flex items-center gap-1.5 transition-colors cursor-pointer"
        >
          <span className="material-symbols-outlined text-xs">add</span>
          <span>ADD INSPIRATION</span>
        </button>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5" data-testid="deck-loading">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="bg-surface-container-low border border-outline-variant/30 rounded-sm p-4 space-y-3 animate-pulse"
            >
              <div className="w-full h-24 bg-surface-container-highest rounded" />
              <div className="h-4 bg-surface-container-highest rounded w-3/4" />
              <div className="flex gap-1.5">
                <div className="h-3 bg-surface-container-highest rounded w-16" />
                <div className="h-3 bg-surface-container-highest rounded w-12" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error State */}
      {!isLoading && error && (
        <div className="bg-rose-500/10 border border-rose-500/40 rounded p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-rose-300" data-testid="deck-error">
          <div className="flex items-center gap-2 text-xs">
            <span className="material-symbols-outlined text-sm">error</span>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={fetchInspirations}
            className="px-3 py-1 bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/40 text-xs rounded transition-colors cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && inspirations.length === 0 && (
        <div
          className="bg-surface-container-lowest border-2 border-dashed border-outline-variant/50 rounded p-6 text-center space-y-3"
          data-testid="deck-empty"
        >
          <div className="w-10 h-10 mx-auto rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center text-primary">
            <span className="material-symbols-outlined text-xl">travel_explore</span>
          </div>
          <div className="space-y-1">
            <h4 className="text-xs font-bold uppercase tracking-wider text-white">
              No inspirations attached yet
            </h4>
            <p className="text-[11px] text-on-surface-variant font-sans max-w-md mx-auto leading-relaxed">
              Discover games that could influence your game&apos;s mechanics, theme, or feel. Use
              <span className="text-primary font-bold"> &quot;Use as Inspiration&quot; </span> in Discovery to attach them here.
            </p>
          </div>
          <button
            type="button"
            onClick={handleNavigateToDiscovery}
            className="px-4 py-2 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/40 font-bold text-xs uppercase rounded transition-colors inline-flex items-center gap-1.5 cursor-pointer"
          >
            <span className="material-symbols-outlined text-sm">explore</span>
            <span>Explore Games in Discovery</span>
          </button>
        </div>
      )}

      {/* Card Grid */}
      {!isLoading && !error && inspirations.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5" data-testid="deck-cards">
          {inspirations.map((item) => {
            // Compute dynamic project alignment for this inspiration
            const dna = extractGameDNA({
              id: item.steamAppId,
              title: item.title,
              genres: item.genres,
              tags: item.tags,
              player_modes: item.playerModes,
            } as any);
            const alignedGenres = computeProjectAlignment(dna, project);

            const isConfirming = confirmingAppId === item.steamAppId;
            const isDeleting = deletingAppId === item.steamAppId;

            return (
              <div
                key={item.id}
                className="bg-surface-container-low border border-outline-variant/60 hover:border-primary/50 transition-all rounded-sm flex flex-col justify-between overflow-hidden relative shadow-sm"
                data-testid={`inspiration-card-${item.steamAppId}`}
              >
                {/* Cover Image & Header */}
                <div>
                  <div className="w-full h-24 bg-surface-container-highest relative overflow-hidden border-b border-outline-variant/40">
                    {item.coverUrl ? (
                      <img
                        src={item.coverUrl}
                        alt={item.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-on-surface-variant/30">
                        <span className="material-symbols-outlined text-3xl">sports_esports</span>
                      </div>
                    )}
                    <div className="absolute top-1.5 right-1.5 bg-background/80 backdrop-blur-xs px-1.5 py-0.5 rounded text-[9px] font-mono text-on-surface-variant border border-outline-variant/40">
                      ID: {item.steamAppId}
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="p-3 space-y-2.5">
                    <div>
                      <h4 className="font-display text-xs text-white font-bold leading-tight line-clamp-1" title={item.title}>
                        {item.title}
                      </h4>
                      <p className="text-[9px] text-on-surface-variant mt-0.5">
                        Attached: {new Date(item.createdAt).toLocaleDateString()}
                      </p>
                    </div>

                    {/* Alignment Chip (derived dynamically) */}
                    {alignedGenres.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {alignedGenres.map((g) => (
                          <span
                            key={g}
                            className="text-[9px] px-1.5 py-0.5 bg-tertiary/10 text-tertiary border border-tertiary/40 rounded font-bold"
                          >
                            ✓ Matches {g}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Genres */}
                    {item.genres.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {item.genres.map((g) => (
                          <span
                            key={g}
                            className="text-[9px] px-1.5 py-0.2 bg-primary/5 text-primary border border-primary/20 rounded"
                          >
                            {g}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Tags */}
                    {item.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-1 border-t border-outline-variant/20">
                        {item.tags.slice(0, 4).map((t) => (
                          <span
                            key={t}
                            className="text-[9px] px-1.5 py-0.2 bg-surface-container border border-outline-variant/40 text-on-surface-variant rounded"
                          >
                            #{t}
                          </span>
                        ))}
                        {item.tags.length > 4 && (
                          <span className="text-[9px] text-outline self-center">
                            +{item.tags.length - 4}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Card Footer & Removal Action */}
                <div className="p-2.5 pt-0">
                  {isConfirming ? (
                    <div className="bg-surface-container-highest border border-rose-500/50 p-2 rounded space-y-1.5 text-center">
                      <p className="text-[10px] text-rose-300">Remove from inspirations?</p>
                      <div className="flex justify-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => setConfirmingAppId(null)}
                          disabled={isDeleting}
                          className="px-2 py-0.5 bg-surface border border-outline-variant text-[10px] rounded text-on-surface hover:text-white cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => handleConfirmDetach(item)}
                          disabled={isDeleting}
                          className="px-2 py-0.5 bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/50 text-[10px] font-bold rounded cursor-pointer flex items-center gap-1"
                        >
                          {isDeleting ? 'Removing...' : 'Remove'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex justify-end pt-2 border-t border-outline-variant/20">
                      <button
                        type="button"
                        onClick={() => setConfirmingAppId(item.steamAppId)}
                        className="text-[10px] text-on-surface-variant hover:text-rose-400 flex items-center gap-1 transition-colors px-1.5 py-0.5 rounded hover:bg-rose-500/10 cursor-pointer"
                        aria-label={`Remove ${item.title} from inspirations`}
                      >
                        <span className="material-symbols-outlined text-xs">delete</span>
                        <span>Remove</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Deterministic Synergy Preview (rendered when >= 2 inspirations exist) */}
      {!isLoading && !error && inspirations.length >= 2 && (
        <div
          className="bg-surface-container-low border border-secondary/40 rounded-sm p-4 space-y-3 mt-4 shadow-sm"
          data-testid="deck-synergy"
        >
          <div className="flex items-center justify-between border-b border-outline-variant/30 pb-2">
            <div className="flex items-center gap-2 text-secondary font-bold text-xs uppercase tracking-wider">
              <span className="material-symbols-outlined text-sm" aria-hidden="true">
                join_inner
              </span>
              <span>INSPIRATION SYNERGY</span>
            </div>
            <span className="text-[10px] text-on-surface-variant">
              {synergy.totalInspirations} reference games
            </span>
          </div>

          <p className="text-[11px] text-on-surface-variant font-sans leading-relaxed">
            Deterministic attribute intersections across your attached inspirations. These commonalities represent natural mechanics and thematic anchors for your game.
          </p>

          {hasSynergy ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1 text-xs">
              {/* Shared Genres */}
              {synergy.sharedGenres.length > 0 && (
                <div className="bg-surface p-2.5 rounded border border-outline-variant/30 space-y-1.5">
                  <div className="text-[10px] uppercase text-tertiary font-bold flex items-center gap-1">
                    <span className="material-symbols-outlined text-xs">category</span>
                    <span>Shared Genres</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {synergy.sharedGenres.map((g) => (
                      <span
                        key={g}
                        className="text-[10px] px-1.5 py-0.5 bg-tertiary/10 text-tertiary border border-tertiary/30 rounded font-bold"
                      >
                        {g}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Shared Tags */}
              {synergy.sharedTags.length > 0 && (
                <div className="bg-surface p-2.5 rounded border border-outline-variant/30 space-y-1.5">
                  <div className="text-[10px] uppercase text-secondary font-bold flex items-center gap-1">
                    <span className="material-symbols-outlined text-xs">label</span>
                    <span>Shared Tags</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {synergy.sharedTags.map((t) => (
                      <span
                        key={t}
                        className="text-[10px] px-1.5 py-0.5 bg-secondary/10 text-secondary border border-secondary/30 rounded"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Shared Player Modes */}
              {synergy.sharedPlayerModes.length > 0 && (
                <div className="bg-surface p-2.5 rounded border border-outline-variant/30 space-y-1.5">
                  <div className="text-[10px] uppercase text-primary font-bold flex items-center gap-1">
                    <span className="material-symbols-outlined text-xs">people</span>
                    <span>Shared Modes</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {synergy.sharedPlayerModes.map((m) => (
                      <span
                        key={m}
                        className="text-[10px] px-1.5 py-0.5 bg-primary/10 text-primary border border-primary/30 rounded"
                      >
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-[11px] text-outline italic p-2 bg-surface rounded border border-outline-variant/20">
              No overlapping genres, tags, or modes detected between these specific games. They provide diverse, complementary reference points.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
