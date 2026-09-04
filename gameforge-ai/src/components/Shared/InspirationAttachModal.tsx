/**
 * InspirationAttachModal.tsx
 *
 * Step 2: Discovery -> Inspiration -> Studio (Persistent API integration)
 *
 * Renders when a developer clicks "Use as Inspiration" on a Discovery result.
 *
 * Rules:
 * - Only displays DNA grounded in real GameDiscoveryItem fields.
 * - No LLM calls. No free-form invented content.
 * - Alignment section only shows verified genre intersections (derived dynamically).
 * - Persists to backend via POST /api/projects/{id}/inspirations.
 * - Enforces single submission and clear error handling for duplicates/unauthorized.
 */

import React, { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useModalDialog } from '../../hooks/useModalDialog';
import type { DiscoverySearchResult, GameProject } from '../../types';
import { extractGameDNA, computeProjectAlignment } from '../../utils/gameDna';
import { inspirationService } from '../../services/inspirations';
import { ApiError } from '../../services/api';

interface InspirationAttachModalProps {
  /** The Discovery result the developer explicitly chose. */
  result: DiscoverySearchResult;
  /** Resolved active project, or null if none is set. */
  activeProject: GameProject | null;
  /** All projects available for selection (used in no-active-project flow). */
  allProjects: GameProject[];
  onClose: () => void;
  /** Called when attachment successfully completes and persists. */
  onAttach: (result: DiscoverySearchResult, projectId: string) => void;
  /** Navigate to an existing project selection UI. */
  onSelectProject: () => void;
  /** Navigate to the new-project creation UI. */
  onCreateProject: () => void | Promise<void>;
}

/**
 * A single DNA section row. Renders nothing if items is empty.
 */
const DnaSection: React.FC<{ label: string; icon: string; items: string[] }> = ({
  label,
  icon,
  items,
}) => {
  if (items.length === 0) return null;
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
        <span className="material-symbols-outlined text-xs" aria-hidden="true">
          {icon}
        </span>
        <span>{label}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            className="px-2.5 py-1 bg-surface-container border border-outline-variant text-[11px] font-mono text-on-surface rounded-sm"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
};

export const InspirationAttachModal: React.FC<InspirationAttachModalProps> = ({
  result,
  activeProject,
  onClose,
  onAttach,
  onSelectProject,
  onCreateProject,
}) => {
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const [isAttaching, setIsAttaching] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { isClosing, handleClose, handleBackdropClick, dialogRef } = useModalDialog({
    isOpen: true,
    onClose,
    initialFocusRef: closeBtnRef,
    closeDelayMs: 200,
  });

  const game = result.game;
  const title = game.display_title ?? game.title;

  // --- DNA extraction (grounded in real data only) ---
  const dna = extractGameDNA(game);
  const alignedGenres = computeProjectAlignment(dna, activeProject);

  // Determine hero image for the game cover
  const heroUrl =
    game.hero_image_url ??
    game.cover_image_url ??
    game.enrichment?.cover_url ??
    (game.source === 'steam' && game.external_id
      ? `https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/${game.external_id}/header.jpg`
      : null);

  const hasDna =
    dna.genres.length > 0 || dna.playerModes.length > 0 || dna.tags.length > 0;

  const handleConfirmAttach = async () => {
    if (!activeProject) return;
    const steamAppId = game.external_id || game.id;
    if (!steamAppId) {
      setErrorMessage('Game catalog identity is missing.');
      return;
    }

    try {
      setIsAttaching(true);
      setErrorMessage(null);
      await inspirationService.attach(activeProject.id, steamAppId);
      onAttach(result, activeProject.id);
      handleClose();
    } catch (err: unknown) {
      setIsAttaching(false);
      if (err instanceof ApiError) {
        if (err.status === 409 || err.code === 'ALREADY_INSPIRED') {
          setErrorMessage('This game is already attached as inspiration to this project.');
        } else if (err.status === 404 || err.code === 'PROJECT_NOT_FOUND') {
          setErrorMessage('Project not found or you do not have permission.');
        } else if (err.status === 401) {
          setErrorMessage('Please sign in to attach inspirations to your project.');
        } else {
          setErrorMessage(err.message || 'Failed to attach inspiration.');
        }
      } else if (err instanceof Error) {
        setErrorMessage(err.message || 'Failed to attach inspiration.');
      } else {
        setErrorMessage('Failed to connect to server. Please try again.');
      }
    }
  };

  // ---- Render: No active project branch ----
  if (!activeProject) {
    return createPortal(
      <div
        className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-md ${
          isClosing ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
        }`}
        onClick={handleBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="Select project for inspiration"
      >
        <div
          ref={dialogRef}
          className={`w-full max-w-md bg-surface border border-primary/50 rounded-lg shadow-[0_0_40px_rgba(76,224,210,0.2)] glow-cyan flex flex-col ${
            isClosing ? 'modal-exit' : 'modal-enter'
          }`}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="bg-terminal-header border-b border-primary/30 px-4 py-3 flex justify-between items-center">
            <div className="flex items-center gap-2 text-primary">
              <span className="material-symbols-outlined text-base" aria-hidden="true">
                lightbulb
              </span>
              <span className="font-mono text-xs tracking-widest font-bold uppercase">
                USE AS INSPIRATION
              </span>
            </div>
            <button
              ref={closeBtnRef}
              type="button"
              onClick={handleClose}
              className="text-on-surface-variant hover:text-primary transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center rounded focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
              aria-label="Close"
            >
              <span className="material-symbols-outlined text-lg">close</span>
            </button>
          </div>

          {/* Body */}
          <div className="p-6 space-y-4">
            <p className="font-mono text-sm text-on-surface">
              <span className="text-primary font-bold">&quot;{title}&quot;</span> will be attached as
              inspiration. Choose a project to attach it to:
            </p>

            {errorMessage && (
              <div className="p-2.5 rounded bg-error/10 border border-error/40 text-error text-xs font-mono">
                {errorMessage}
              </div>
            )}

            <div className="space-y-3">
              <button
                type="button"
                onClick={() => {
                  handleClose();
                  onSelectProject();
                }}
                className="w-full px-4 py-3 border border-primary/50 hover:border-primary bg-primary/5 hover:bg-primary/10 text-primary font-mono text-xs uppercase font-bold rounded flex items-center gap-2 transition-colors cursor-pointer"
              >
                <span className="material-symbols-outlined text-sm" aria-hidden="true">
                  folder_open
                </span>
                <span>Use with existing project</span>
              </button>

              <button
                type="button"
                disabled={isAttaching}
                onClick={async () => {
                  try {
                    setIsAttaching(true);
                    setErrorMessage(null);
                    await onCreateProject();
                    handleClose();
                  } catch (err: unknown) {
                    setIsAttaching(false);
                    setErrorMessage(err instanceof Error ? err.message : 'Failed to create project.');
                  }
                }}
                className="w-full px-4 py-3 border border-secondary/50 hover:border-secondary bg-secondary/5 hover:bg-secondary/10 text-secondary font-mono text-xs uppercase font-bold rounded flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
              >
                <span className={`material-symbols-outlined text-sm ${isAttaching ? 'animate-spin' : ''}`} aria-hidden="true">
                  {isAttaching ? 'sync' : 'add_circle'}
                </span>
                <span>{isAttaching ? 'Creating project...' : 'Create new project'}</span>
              </button>

              <button
                type="button"
                onClick={handleClose}
                className="w-full px-4 py-3 border border-outline-variant hover:border-on-surface text-on-surface-variant hover:text-white font-mono text-xs uppercase rounded transition-colors cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>,
      document.body
    );
  }

  // ---- Render: Active project — full attachment preview ----
  return createPortal(
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-background/90 backdrop-blur-md ${
        isClosing ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
      }`}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label={`Attach ${title} as inspiration to ${activeProject.title}`}
    >
      <div
        ref={dialogRef}
        className={`w-full max-w-xl max-h-[90vh] overflow-y-auto bg-surface border border-primary/50 rounded-lg flex flex-col shadow-[0_0_40px_rgba(76,224,210,0.2)] glow-cyan ${
          isClosing ? 'modal-exit' : 'modal-enter'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-terminal-header border-b border-primary/30 px-4 py-2.5 flex justify-between items-center sticky top-0 z-20 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-primary">
            <span className="material-symbols-outlined text-base" aria-hidden="true">
              lightbulb
            </span>
            <span className="font-mono text-xs tracking-widest font-bold uppercase">
              INSPIRED BY
            </span>
          </div>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={handleClose}
            className="text-on-surface-variant hover:text-primary transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center rounded focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
            aria-label="Close inspiration modal"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 bg-terminal-bg p-4 sm:p-6 space-y-5">
          {/* Game hero + title */}
          <div className="flex items-start gap-4">
            <div className="w-24 h-16 shrink-0 rounded overflow-hidden bg-surface-container border border-outline-variant/60">
              {heroUrl ? (
                <img
                  src={heroUrl}
                  alt={title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-on-surface-variant/30">
                  <span className="material-symbols-outlined text-2xl" aria-hidden="true">
                    sports_esports
                  </span>
                </div>
              )}
            </div>
            <div className="min-w-0">
              <h2 className="font-display text-base sm:text-lg text-white font-bold leading-snug">
                {title}
              </h2>
              {game.release_year > 0 && (
                <p className="font-mono text-xs text-on-surface-variant mt-0.5">
                  {game.release_year} · {game.platforms?.join(', ') ?? 'PC'}
                </p>
              )}
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-outline-variant/40" />

          {/* Active project context */}
          <div className="space-y-1">
            <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
              Active Project
            </div>
            <div className="flex items-center gap-2 px-3 py-2 bg-surface-container/60 border border-outline-variant/60 rounded">
              <span
                className="material-symbols-outlined text-sm text-primary"
                aria-hidden="true"
              >
                folder
              </span>
              <span className="font-mono text-sm text-on-surface font-bold">
                {activeProject.title}
              </span>
              <span className="font-mono text-xs text-on-surface-variant ml-auto">
                {activeProject.genre}
              </span>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-outline-variant/40" />

          {/* Relevant Game DNA */}
          <div className="space-y-4">
            <div className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-widest text-secondary font-bold">
              <span className="material-symbols-outlined text-sm" aria-hidden="true">
                dna
              </span>
              <span>Relevant Game DNA</span>
            </div>

            {hasDna ? (
              <div className="space-y-3" data-testid="dna-sections">
                <DnaSection label="Genres" icon="category" items={dna.genres} />
                <DnaSection label="Player Modes" icon="people" items={dna.playerModes} />
                <DnaSection label="Tags" icon="label" items={dna.tags} />
              </div>
            ) : (
              <p className="font-mono text-xs text-on-surface-variant italic">
                No structured metadata available for this title.
              </p>
            )}
          </div>

          {/* Project Alignment (only if verified intersection exists) */}
          {alignedGenres.length > 0 && (
            <>
              <div className="border-t border-outline-variant/40" />
              <div className="space-y-2" data-testid="alignment-section">
                <div className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-widest text-tertiary font-bold">
                  <span className="material-symbols-outlined text-sm" aria-hidden="true">
                    join_inner
                  </span>
                  <span>Project Alignment</span>
                </div>
                <p className="font-mono text-xs text-on-surface-variant">
                  Matches your project&apos;s existing genre:
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {alignedGenres.map((g) => (
                    <span
                      key={g}
                      className="px-2.5 py-1 bg-tertiary/10 border border-tertiary/50 text-tertiary text-[11px] font-mono rounded-sm font-bold"
                      data-testid="alignment-chip"
                    >
                      ✓ {g}
                    </span>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Error Banner */}
          {errorMessage && (
            <div className="bg-rose-500/10 border border-rose-500/50 rounded p-3 flex items-start gap-2 text-rose-400">
              <span className="material-symbols-outlined text-sm shrink-0 mt-0.5" aria-hidden="true">
                error
              </span>
              <p className="font-mono text-xs leading-relaxed" data-testid="attach-error-msg">
                {errorMessage}
              </p>
            </div>
          )}
        </div>

        {/* Footer Action Bar */}
        <div className="bg-terminal-header border-t border-primary/30 p-4 flex items-center justify-between gap-3 sticky bottom-0 z-20 backdrop-blur-sm">
          <button
            type="button"
            onClick={handleClose}
            disabled={isAttaching}
            className="px-4 py-2.5 border border-outline-variant hover:border-on-surface text-on-surface-variant hover:text-white font-mono text-xs uppercase rounded transition-colors cursor-pointer disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleConfirmAttach}
            disabled={isAttaching}
            className="px-5 py-2.5 bg-primary text-on-primary font-mono text-xs uppercase font-bold rounded btn-interactive energy-sweep glow-cyan flex items-center gap-2 cursor-pointer shadow-lg disabled:opacity-60 disabled:cursor-not-allowed"
            data-testid="attach-button"
          >
            {isAttaching ? (
              <>
                <span className="material-symbols-outlined text-sm animate-spin" aria-hidden="true">
                  progress_activity
                </span>
                <span>Saving...</span>
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-sm" aria-hidden="true">
                  lightbulb
                </span>
                <span>Attach to Active Project</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
