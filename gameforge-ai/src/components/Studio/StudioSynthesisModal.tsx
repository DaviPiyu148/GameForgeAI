/**
 * StudioSynthesisModal.tsx
 *
 * Step 4: Proposal Preview UI for Inspiration Synthesis.
 *
 * Presents the deterministic, structured GameForge design proposal synthesized
 * from 2-5 attached project inspirations.
 * This is a review-only proposal modal; it does NOT automatically mutate the project.
 */

import React, { useRef } from 'react';
import { createPortal } from 'react-dom';
import { useModalDialog } from '../../hooks/useModalDialog';
import type { GameProject, InspirationSynthesisProposal } from '../../types';

interface StudioSynthesisModalProps {
  proposal: InspirationSynthesisProposal;
  project: GameProject;
  onClose: () => void;
}

export const StudioSynthesisModal: React.FC<StudioSynthesisModalProps> = ({
  proposal,
  project: _project,
  onClose,
}) => {
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const { isClosing, handleClose, handleBackdropClick, dialogRef } = useModalDialog({
    isOpen: true,
    onClose,
    initialFocusRef: closeBtnRef,
    closeDelayMs: 200,
  });

  const confidenceColor =
    proposal.confidence === 'HIGH'
      ? 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10'
      : proposal.confidence === 'MEDIUM'
      ? 'text-amber-400 border-amber-500/40 bg-amber-500/10'
      : 'text-rose-400 border-rose-500/40 bg-rose-500/10';

  const loopSteps = proposal.gameplayLoop.split(' -> ');

  return createPortal(
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-background/90 backdrop-blur-md ${
        isClosing ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
      }`}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label="Inspiration Design Proposal Preview"
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
                INSPIRATION SYNTHESIS // PROPOSAL PREVIEW
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
                <p className="text-[11px] font-sans text-on-surface/90 mt-0.5 leading-relaxed">
                  {proposal.confidenceExplanation}
                </p>
              </div>
            </div>
          </div>

          {/* Single-Source Dominance Guard Warning */}
          {proposal.isSingleSourceDominant && proposal.dominantSourceTitle && (
            <div className="bg-amber-500/10 border border-amber-500/40 text-amber-300 rounded p-3 flex items-start gap-2">
              <span className="material-symbols-outlined text-sm mt-0.5">balance</span>
              <p className="text-[11px] font-sans leading-relaxed">
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
                    <div className="text-[10px] text-on-surface mt-0.5 font-sans leading-tight">{step}</div>
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
                  <li key={idx} className="flex items-start gap-2 text-[11px] text-on-surface font-sans">
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

          {/* Design Conflicts / Decisions Required */}
          {proposal.conflicts.length > 0 && (
            <div className="bg-surface-container-low border border-amber-500/50 p-4 rounded-sm space-y-3">
              <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase tracking-wider border-b border-outline-variant/30 pb-2">
                <span className="material-symbols-outlined text-sm">tune</span>
                <span>Design Decisions Required ({proposal.conflicts.length})</span>
              </div>

              <div className="space-y-3 pt-1">
                {proposal.conflicts.map((conflict, idx) => (
                  <div key={idx} className="bg-surface p-3 rounded border border-amber-500/30 space-y-2">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-bold text-amber-300 uppercase">{conflict.field}</span>
                      <span className="text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30">
                        {conflict.resolutionStatus}
                      </span>
                    </div>
                    <p className="text-[11px] text-on-surface-variant font-sans leading-relaxed">
                      {conflict.description}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <span className="text-[10px] text-on-surface-variant">Recommended options:</span>
                      {conflict.options.map((opt, oIdx) => (
                        <span key={oIdx} className="text-[10px] bg-surface-container-highest px-2 py-0.5 rounded text-white border border-outline-variant">
                          {opt}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer Action Bar */}
        <div className="bg-terminal-header border-t border-primary/30 p-4 flex flex-wrap items-center justify-between gap-3 sticky bottom-0 z-20 backdrop-blur-sm shrink-0">
          <div className="text-[10px] text-on-surface-variant font-mono">
            Review-only proposal • Blueprint application will occur in Step 5
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 border border-outline-variant hover:border-on-surface text-on-surface-variant hover:text-white font-mono text-xs uppercase rounded transition-colors cursor-pointer"
            >
              Close & Review Later
            </button>

            <button
              type="button"
              disabled
              title="Blueprint application will be implemented in Step 5"
              className="px-4 py-2 bg-primary/40 text-on-primary/60 font-mono text-xs uppercase font-bold rounded flex items-center gap-1.5 cursor-not-allowed border border-primary/30 opacity-70"
            >
              <span className="material-symbols-outlined text-sm">lock</span>
              <span>Apply to Blueprint (Step 5)</span>
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};
