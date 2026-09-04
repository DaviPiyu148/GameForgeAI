/**
 * StudioSynthesisModal.tsx
 *
 * Step 4 & 5: Inspiration Synthesis Proposal Review & Versioned Blueprint Application.
 *
 * Features:
 * - Proposal preview with confidence gauge and single-source dominance balance guard.
 * - Interactive conflict resolution: blocks Apply until all conflicts are resolved.
 * - Blueprint Changes Preview (diff between current project and proposal).
 * - Explicit developer confirmation before versioned application.
 * - Optimistic concurrency validation against baseVersionNumber.
 * - Stale proposal error handling with Refresh & Regenerate action.
 * - Atomic application creating Project Version N+1 without modifying prior history.
 */

import React, { useRef, useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useModalDialog } from '../../hooks/useModalDialog';
import type {
  ApplySynthesisProposalResponse,
  GameProject,
  InspirationSynthesisProposal,
} from '../../types';
import { inspirationService } from '../../services/inspirations';
import { pushToast } from '../../services/toastBus';
import { ApiError } from '../../services/api';

interface StudioSynthesisModalProps {
  proposal: InspirationSynthesisProposal;
  project: GameProject;
  onClose: () => void;
  onApplied?: (res: ApplySynthesisProposalResponse) => void;
  onRegenerate?: () => Promise<void>;
}

export const StudioSynthesisModal: React.FC<StudioSynthesisModalProps> = ({
  proposal,
  project,
  onClose,
  onApplied,
  onRegenerate,
}) => {
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const { isClosing, handleClose, handleBackdropClick, dialogRef } = useModalDialog({
    isOpen: true,
    onClose,
    initialFocusRef: closeBtnRef,
    closeDelayMs: 200,
  });

  // Conflict resolution state
  const [conflictResolutions, setConflictResolutions] = useState<Record<string, string>>({});

  // Application workflow states
  const [showConfirmApply, setShowConfirmApply] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [isStale, setIsStale] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  // Check for unresolved conflicts
  const unresolvedConflicts = useMemo(() => {
    return proposal.conflicts.filter(
      (c) => c.resolutionStatus === 'UNRESOLVED' && !conflictResolutions[c.field]
    );
  }, [proposal.conflicts, conflictResolutions]);

  const hasBlockingConflicts = unresolvedConflicts.length > 0;

  const confidenceColor =
    proposal.confidence === 'HIGH'
      ? 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10'
      : proposal.confidence === 'MEDIUM'
      ? 'text-amber-400 border-amber-500/40 bg-amber-500/10'
      : 'text-rose-400 border-rose-500/40 bg-rose-500/10';

  const loopSteps = proposal.gameplayLoop.split(' -> ');

  // Compute field diffs for review
  const diffs = useMemo(() => {
    const items: Array<{ field: string; current: string; proposed: string; isNew?: boolean }> = [];

    if (project.genre !== proposal.proposedGenre) {
      items.push({
        field: 'Genre',
        current: project.genre || 'None',
        proposed: proposal.proposedGenre,
      });
    }

    const currentEngine = project.parameters?.engine || 'standard';
    if (currentEngine !== proposal.recommendedParameters.engine) {
      items.push({
        field: 'Engine / Archetype',
        current: currentEngine,
        proposed: proposal.recommendedParameters.engine,
      });
    }

    const currentTheme = project.designSpec?.theme || 'neon';
    if (currentTheme !== proposal.proposedTheme) {
      items.push({
        field: 'Theme',
        current: currentTheme,
        proposed: proposal.proposedTheme,
      });
    }

    const currentLoop = project.designSpec?.core_gameplay_loop;
    if (currentLoop !== proposal.gameplayLoop) {
      items.push({
        field: 'Gameplay Loop',
        current: currentLoop || 'Standard loop',
        proposed: proposal.gameplayLoop,
      });
    }

    return items;
  }, [project, proposal]);

  const handleSelectOption = (field: string, option: string) => {
    setConflictResolutions((prev) => ({
      ...prev,
      [field]: option,
    }));
  };

  const handleExecuteApply = async () => {
    try {
      setIsApplying(true);
      setApplyError(null);
      setIsStale(false);

      const baseVersion = project.currentVersion || 1;
      const res = await inspirationService.applySynthesis(project.id, {
        baseVersionNumber: baseVersion,
        conflictResolutions,
      });

      pushToast({
        variant: 'success',
        title: 'BLUEPRINT UPDATED',
        description: `Created Version ${res.newVersionNumber} from ${proposal.inspirationCount} inspirations.`,
      });

      if (onApplied) {
        onApplied(res);
      }
      handleClose();
    } catch (err: unknown) {
      console.error('Failed to apply proposal:', err);
      if (err instanceof ApiError && (err.status === 409 || err.message?.includes('STALE_PROPOSAL') || err.message?.includes('version'))) {
        setIsStale(true);
        setApplyError('This proposal was generated from an older project version. Refresh and regenerate to proceed.');
      } else {
        setApplyError(err instanceof Error ? err.message : 'Failed to apply proposal to Blueprint.');
      }
    } finally {
      setIsApplying(false);
    }
  };

  const handleRefreshAndRegenerate = async () => {
    try {
      setIsRegenerating(true);
      setApplyError(null);
      setIsStale(false);
      setShowConfirmApply(false);
      if (onRegenerate) {
        await onRegenerate();
      } else {
        const regenerated = await inspirationService.synthesize(project.id);
        Object.assign(proposal, regenerated);
      }
      pushToast({
        variant: 'info',
        title: 'PROPOSAL REGENERATED',
        description: 'Design proposal refreshed against current project state.',
      });
    } catch (err: unknown) {
      console.error('Failed to regenerate proposal:', err);
      setApplyError('Failed to regenerate proposal. Please retry.');
    } finally {
      setIsRegenerating(false);
    }
  };

  return createPortal(
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-background/90 backdrop-blur-md ${
        isClosing ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
      }`}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label="Inspiration Design Proposal Review and Apply"
    >
      <div
        ref={dialogRef}
        className={`w-full max-w-3xl max-h-[92vh] overflow-y-auto bg-surface border-2 border-primary/50 rounded-lg flex flex-col shadow-[0_0_50px_rgba(76,224,210,0.25)] glow-cyan ${
          isClosing ? 'modal-exit' : 'modal-enter'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Terminal Header */}
        <div className="bg-terminal-header border-b border-primary/30 p-3.5 flex justify-between items-center sticky top-0 z-20 backdrop-blur-sm shrink-0">
          <div className="flex items-center gap-2.5 text-primary">
            <span className="material-symbols-outlined text-lg animate-pulse" aria-hidden="true">
              auto_awesome
            </span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs tracking-widest font-bold uppercase">
                INSPIRATION SYNTHESIS // BLUEPRINT PROPOSAL
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary/20 text-primary border border-primary/40 font-bold">
                {proposal.inspirationCount} Source Games
              </span>
            </div>
          </div>
          <button
            ref={closeBtnRef}
            onClick={handleClose}
            className="text-on-surface-variant hover:text-primary transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center rounded focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
            aria-label="Close Proposal Modal"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-6 bg-terminal-bg space-y-6 font-mono text-xs flex-1">
          {/* Stale or Application Error Alert */}
          {applyError && (
            <div className={`p-4 rounded border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 ${
              isStale ? 'bg-amber-500/10 border-amber-500/50 text-amber-300' : 'bg-rose-500/10 border-rose-500/50 text-rose-300'
            }`}>
              <div className="flex items-start gap-2.5">
                <span className="material-symbols-outlined text-base mt-0.5">
                  {isStale ? 'update' : 'error'}
                </span>
                <div>
                  <div className="font-bold text-[11px] uppercase">
                    {isStale ? 'STALE PROPOSAL DETECTED' : 'APPLICATION FAILED'}
                  </div>
                  <p className="text-[11px] font-body text-on-surface/90 mt-0.5">
                    {applyError}
                  </p>
                </div>
              </div>
              {isStale && (
                <button
                  type="button"
                  onClick={handleRefreshAndRegenerate}
                  disabled={isRegenerating}
                  className="px-3 py-1.5 bg-amber-500 text-surface font-mono font-bold text-xs rounded hover:bg-amber-400 transition-colors flex items-center gap-1.5 shrink-0 cursor-pointer"
                >
                  {isRegenerating ? (
                    <>
                      <span className="material-symbols-outlined text-xs animate-spin">sync</span>
                      <span>REGENERATING...</span>
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined text-xs">refresh</span>
                      <span>REFRESH & REGENERATE</span>
                    </>
                  )}
                </button>
              )}
            </div>
          )}

          {/* Confidence & Coherence Gauge */}
          <div className={`border rounded p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 ${confidenceColor}`}>
            <div className="flex items-start gap-2.5">
              <span className="material-symbols-outlined text-base mt-0.5" aria-hidden="true">
                {proposal.confidence === 'HIGH' ? 'verified' : proposal.confidence === 'MEDIUM' ? 'info' : 'warning'}
              </span>
              <div>
                <div className="font-bold tracking-wider uppercase text-[11px]">
                  SYNTHESIS CONFIDENCE: {proposal.confidence}
                </div>
                <p className="text-[11px] font-body text-on-surface/90 mt-0.5 leading-relaxed">
                  {proposal.confidenceExplanation}
                </p>
              </div>
            </div>
          </div>

          {/* Single-Source Dominance Guard Warning */}
          {proposal.isSingleSourceDominant && proposal.dominantSourceTitle && (
            <div className="bg-amber-500/10 border border-amber-500/40 text-amber-300 rounded p-3 flex items-start gap-2">
              <span className="material-symbols-outlined text-sm mt-0.5">balance</span>
              <p className="text-[11px] font-body leading-relaxed">
                <span className="font-bold">Source Balance Notice:</span> This proposal draws primarily from{' '}
                <span className="font-bold">&quot;{proposal.dominantSourceTitle}&quot;</span>. Consider adding more varied reference games to achieve a more balanced synthesis.
              </p>
            </div>
          )}

          {/* Primary High-Level Direction */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="bg-surface-container-low border border-outline-variant/40 p-3 rounded-sm space-y-1">
              <div className="text-on-surface-variant text-[10px] uppercase tracking-wider">GENRE DIRECTION</div>
              <div className="text-secondary font-bold text-sm">{proposal.proposedGenre}</div>
            </div>

            <div className="bg-surface-container-low border border-outline-variant/40 p-3 rounded-sm space-y-1">
              <div className="text-on-surface-variant text-[10px] uppercase tracking-wider">ARCHETYPE & THEME</div>
              <div className="text-primary font-bold text-sm uppercase">
                {proposal.proposedArchetype} · {proposal.proposedTheme}
              </div>
            </div>

            <div className="bg-surface-container-low border border-outline-variant/40 p-3 rounded-sm space-y-1">
              <div className="text-on-surface-variant text-[10px] uppercase tracking-wider">PLAYER MODES</div>
              <div className="text-on-surface font-bold text-sm">
                {proposal.proposedPlayerModes.join(' / ')}
              </div>
            </div>
          </div>

          {/* Core Proposed Mechanics with Traceable Source Attribution */}
          <div className="bg-surface-container-low border border-outline-variant/50 p-4 rounded-sm space-y-3">
            <div className="flex items-center justify-between border-b border-outline-variant/30 pb-2">
              <div className="flex items-center gap-2 text-primary font-bold text-xs uppercase tracking-wider">
                <span className="material-symbols-outlined text-sm">bolt</span>
                <span>Proposed Core Mechanics (Traceable Composition)</span>
              </div>
              <span className="text-[10px] text-on-surface-variant">
                {proposal.proposedMechanics.length} active mechanics
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 pt-1">
              {proposal.sourceAttribution.map((attr, idx) => (
                <div
                  key={idx}
                  className="bg-surface p-2.5 rounded border border-outline-variant/30 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-primary font-bold uppercase text-[11px]">
                      {attr.element}
                    </span>
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-primary/10 text-primary border border-primary/20">
                      {attr.category}
                    </span>
                  </div>
                  <div className="text-[10px] text-on-surface-variant flex flex-wrap items-center gap-1">
                    <span>From:</span>
                    <span className="text-white font-bold">{attr.sourceTitles.join(' · ')}</span>
                  </div>
                  {attr.triggerAttributes.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {attr.triggerAttributes.map((k) => (
                        <span key={k} className="text-[9px] text-on-surface-variant/80 bg-surface-container px-1 rounded">
                          #{k}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Abstract Gameplay Loop */}
          <div className="bg-surface-container-low border border-outline-variant/50 p-4 rounded-sm space-y-3">
            <div className="flex items-center gap-2 text-secondary font-bold text-xs uppercase tracking-wider border-b border-outline-variant/30 pb-2">
              <span className="material-symbols-outlined text-sm">sync</span>
              <span>Abstract Gameplay Loop</span>
            </div>

            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-1 overflow-x-auto">
              {loopSteps.map((step, idx) => (
                <React.Fragment key={idx}>
                  <div className="bg-surface border border-outline-variant/40 p-2.5 rounded text-center flex-1 min-w-[120px]">
                    <div className="text-[9px] text-secondary font-bold uppercase">PHASE 0{idx + 1}</div>
                    <div className="text-[10px] text-on-surface mt-0.5 font-body leading-tight">{step}</div>
                  </div>
                  {idx < loopSteps.length - 1 && (
                    <span className="text-outline text-center text-xs sm:rotate-0 rotate-90 shrink-0">
                      ▶
                    </span>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Design Objectives & Parameter Recommendations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Objectives */}
            <div className="bg-surface-container-low border border-outline-variant/50 p-4 rounded-sm space-y-2.5">
              <div className="flex items-center gap-2 text-secondary font-bold text-xs uppercase tracking-wider">
                <span className="material-symbols-outlined text-sm">flag</span>
                <span>Design Objectives</span>
              </div>
              <ul className="space-y-2 pt-1">
                {proposal.designObjectives.map((obj, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-[11px] text-on-surface font-body">
                    <span className="text-secondary text-[10px] font-mono font-bold mt-0.5">
                      [{obj.type}]
                    </span>
                    <span>{obj.description}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Build Parameter Recommendations */}
            <div className="bg-surface-container-low border border-outline-variant/50 p-4 rounded-sm space-y-2.5">
              <div className="flex items-center gap-2 text-secondary font-bold text-xs uppercase tracking-wider">
                <span className="material-symbols-outlined text-sm">tune</span>
                <span>Recommended Build Specs</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
                <div className="bg-surface p-2 rounded border border-outline-variant/30">
                  <span className="text-on-surface-variant text-[10px]">ENGINE:</span>
                  <div className="text-primary font-bold uppercase">{proposal.recommendedParameters.engine}</div>
                </div>
                <div className="bg-surface p-2 rounded border border-outline-variant/30">
                  <span className="text-on-surface-variant text-[10px]">PHYSICS:</span>
                  <div className="text-on-surface font-bold">{proposal.recommendedParameters.physics}%</div>
                </div>
                <div className="bg-surface p-2 rounded border border-outline-variant/30">
                  <span className="text-on-surface-variant text-[10px]">ART DENSITY:</span>
                  <div className="text-on-surface font-bold">{proposal.recommendedParameters.artDensity}%</div>
                </div>
                <div className="bg-surface p-2 rounded border border-outline-variant/30">
                  <span className="text-on-surface-variant text-[10px]">WORLD MODE:</span>
                  <div className="text-on-surface font-bold uppercase">{proposal.recommendedParameters.worldMode}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Conflict Resolution Section */}
          {proposal.conflicts.length > 0 && (
            <div className="bg-surface-container-low border border-amber-500/50 p-4 rounded-sm space-y-3" data-testid="conflict-resolution-section">
              <div className="flex items-center justify-between border-b border-outline-variant/30 pb-2">
                <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase tracking-wider">
                  <span className="material-symbols-outlined text-sm">tune</span>
                  <span>Design Decisions Required ({proposal.conflicts.length})</span>
                </div>
                {hasBlockingConflicts ? (
                  <span className="text-[10px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30 font-bold">
                    {unresolvedConflicts.length} UNRESOLVED (BLOCKS APPLY)
                  </span>
                ) : (
                  <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30 font-bold flex items-center gap-1">
                    <span className="material-symbols-outlined text-xs">check</span>
                    <span>ALL RESOLVED</span>
                  </span>
                )}
              </div>

              <div className="space-y-3 pt-1">
                {proposal.conflicts.map((conflict, idx) => {
                  const selected = conflictResolutions[conflict.field];
                  const isResolved = Boolean(selected);

                  return (
                    <div
                      key={idx}
                      className={`p-3 rounded border space-y-2 transition-colors ${
                        isResolved
                          ? 'bg-surface border-emerald-500/40'
                          : 'bg-surface border-amber-500/40'
                      }`}
                    >
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-bold uppercase text-white">{conflict.field}</span>
                        <span
                          className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                            isResolved
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          }`}
                        >
                          {isResolved ? 'RESOLVED' : 'UNRESOLVED'}
                        </span>
                      </div>
                      <p className="text-[11px] text-on-surface-variant font-body leading-relaxed">
                        {conflict.description}
                      </p>
                      <div className="space-y-1.5 pt-1">
                        <div className="text-[10px] text-on-surface-variant font-bold uppercase">
                          Select Direction:
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {conflict.options.map((opt, oIdx) => {
                            const isChosen = selected === opt;
                            return (
                              <button
                                key={oIdx}
                                type="button"
                                onClick={() => handleSelectOption(conflict.field, opt)}
                                className={`text-[11px] font-mono px-3 py-1.5 rounded border transition-all cursor-pointer flex items-center gap-1.5 ${
                                  isChosen
                                    ? 'bg-emerald-500 text-surface font-bold border-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.3)]'
                                    : 'bg-surface-container-highest text-on-surface hover:text-white border-outline-variant hover:border-primary'
                                }`}
                              >
                                <span className="material-symbols-outlined text-xs">
                                  {isChosen ? 'check_circle' : 'radio_button_unchecked'}
                                </span>
                                <span>{opt}</span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Blueprint Changes Preview (Diff) */}
          <div className="bg-surface-container-low border border-primary/30 p-4 rounded-sm space-y-3" data-testid="blueprint-diff-section">
            <div className="flex items-center justify-between border-b border-outline-variant/30 pb-2">
              <div className="flex items-center gap-2 text-primary font-bold text-xs uppercase tracking-wider">
                <span className="material-symbols-outlined text-sm">history_edu</span>
                <span>Blueprint Changes Preview (Forward Diff)</span>
              </div>
              <span className="text-[10px] text-on-surface-variant">
                Target: Version {(project.currentVersion || 1) + 1}
              </span>
            </div>

            {diffs.length > 0 ? (
              <div className="space-y-2 pt-1">
                {diffs.map((d, idx) => (
                  <div
                    key={idx}
                    className="bg-surface p-2.5 rounded border border-outline-variant/30 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px]"
                  >
                    <span className="font-bold text-on-surface-variant uppercase">{d.field}:</span>
                    <div className="flex items-center gap-2 font-mono">
                      <span className="text-on-surface-variant/70 line-through">{d.current}</span>
                      <span className="text-primary font-bold">→</span>
                      <span className="text-emerald-400 font-bold">{d.proposed}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-[11px] text-on-surface-variant italic p-2">
                Proposal aligns with current project baseline; will update mechanics and design rationale.
              </div>
            )}
          </div>

          {/* Confirmation Prompt when Apply is Clicked */}
          {showConfirmApply && (
            <div className="bg-surface-container-high border-2 border-primary p-4 rounded space-y-3 shadow-[0_0_30px_rgba(76,224,210,0.2)] animate-fadeIn">
              <div className="flex items-start gap-2.5 text-primary">
                <span className="material-symbols-outlined text-lg">verified_user</span>
                <div>
                  <h4 className="font-bold text-xs uppercase tracking-wider">
                    Confirm Blueprint Mutation (Version {(project.currentVersion || 1) + 1})
                  </h4>
                  <p className="text-[11px] font-body text-on-surface/90 mt-1 leading-relaxed">
                    This action will apply the approved synthesis proposal and create a new immutable{' '}
                    <span className="font-bold text-primary">Version {(project.currentVersion || 1) + 1}</span>.
                    Your prior versions remain completely preserved and recoverable at any time in Studio Version History.
                  </p>
                </div>
              </div>

              <div className="flex justify-end items-center gap-2 pt-2 border-t border-outline-variant/30">
                <button
                  type="button"
                  onClick={() => setShowConfirmApply(false)}
                  disabled={isApplying}
                  className="px-3 py-1.5 border border-outline-variant hover:border-on-surface text-on-surface-variant hover:text-white font-mono text-xs uppercase rounded transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleExecuteApply}
                  disabled={isApplying}
                  className="px-4 py-1.5 bg-primary text-surface font-mono text-xs uppercase font-bold rounded flex items-center gap-1.5 hover:bg-primary/90 transition-all cursor-pointer shadow-[0_0_15px_rgba(76,224,210,0.4)] glow-cyan"
                  data-testid="confirm-apply-button"
                >
                  {isApplying ? (
                    <>
                      <span className="material-symbols-outlined text-xs animate-spin">sync</span>
                      <span>APPLYING TO BLUEPRINT...</span>
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined text-xs">check</span>
                      <span>CONFIRM & CREATE V{(project.currentVersion || 1) + 1}</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer Action Bar */}
        <div className="bg-terminal-header border-t border-primary/30 p-4 flex flex-wrap items-center justify-between gap-3 sticky bottom-0 z-20 backdrop-blur-sm shrink-0">
          <div className="text-[10px] text-on-surface-variant font-mono">
            {hasBlockingConflicts
              ? 'Resolve all conflicts above to enable Blueprint application'
              : `Ready to apply • Creates Version ${(project.currentVersion || 1) + 1}`}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleClose}
              disabled={isApplying}
              className="px-4 py-2 border border-outline-variant hover:border-on-surface text-on-surface-variant hover:text-white font-mono text-xs uppercase rounded transition-colors cursor-pointer"
            >
              Close & Review Later
            </button>

            {!showConfirmApply && (
              <button
                type="button"
                onClick={() => setShowConfirmApply(true)}
                disabled={hasBlockingConflicts || isApplying}
                title={hasBlockingConflicts ? 'Resolve all conflicts to enable Apply' : 'Apply proposal to project Blueprint'}
                className={`px-4 py-2 font-mono text-xs uppercase font-bold rounded flex items-center gap-1.5 transition-all ${
                  hasBlockingConflicts || isApplying
                    ? 'bg-primary/30 text-on-primary/50 border border-primary/20 cursor-not-allowed opacity-60'
                    : 'bg-primary text-surface hover:bg-primary/90 cursor-pointer shadow-[0_0_20px_rgba(76,224,210,0.3)] glow-cyan'
                }`}
                data-testid="apply-proposal-button"
              >
                <span className="material-symbols-outlined text-sm">auto_fix_high</span>
                <span>Apply to Blueprint</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};
