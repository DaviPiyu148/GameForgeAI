import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { discoveryService } from '../../services/discovery';
import { useAppContext } from '../../context/AppContext';
import { useModalDialog } from '../../hooks/useModalDialog';

interface GameDNAOnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCompleted?: () => void;
}

const GENRE_OPTIONS = [
  'Action',
  'RPG',
  'Adventure',
  'Strategy',
  'Shooter',
  'Platformer',
  'Survival',
  'Roguelike',
  'Arcade',
  'Puzzle',
  'Casual',
  'Simulation',
];

const ENJOYMENT_OPTIONS = [
  'Exploration',
  'Story',
  'Combat',
  'Building',
  'Crafting',
  'Progression',
  'Tactics',
  'Creativity',
];

const AVOID_OPTIONS = [
  'Horror',
  'Heavy Combat',
  'Competitive PvP',
  'High Difficulty',
  'Grindy Progression',
  'Stealth',
];

export const GameDNAOnboardingModal: React.FC<GameDNAOnboardingModalProps> = ({
  isOpen,
  onClose,
  onCompleted,
}) => {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [selectedGenres, setSelectedGenres] = useState<string[]>([]);
  const [selectedEnjoyments, setSelectedEnjoyments] = useState<string[]>([]);
  const [selectedAvoidances, setSelectedAvoidances] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { refreshPreferences, state } = useAppContext();

  const { isClosing, handleClose, handleBackdropClick, dialogRef } = useModalDialog({
    isOpen,
    onClose,
    closeDelayMs: 200,
  });

  if (!isOpen) return null;

  const toggleGenre = (genre: string) => {
    setSelectedGenres((prev) =>
      prev.includes(genre) ? prev.filter((g) => g !== genre) : [...prev, genre]
    );
  };

  const toggleEnjoyment = (item: string) => {
    setSelectedEnjoyments((prev) =>
      prev.includes(item) ? prev.filter((i) => i !== item) : [...prev, item]
    );
  };

  const toggleAvoidance = (item: string) => {
    setSelectedAvoidances((prev) =>
      prev.includes(item) ? prev.filter((i) => i !== item) : [...prev, item]
    );
  };

  const handleFinish = async () => {
    setIsSubmitting(true);
    try {
      if (state.authStatus === 'AUTHENTICATED') {
        await discoveryService.onboardPreferences(
          selectedGenres,
          selectedEnjoyments,
          selectedAvoidances
        );
        await refreshPreferences();
      }
      setStep(4);
    } catch (err) {
      console.warn('Failed to save onboarded preferences:', err);
      setStep(4);
    } finally {
      setIsSubmitting(false);
    }
  };

  return createPortal(
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm ${
        isClosing ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
      }`}
      role="dialog"
      aria-modal="true"
      aria-label="Game DNA Onboarding Modal"
      onClick={handleBackdropClick}
    >
      <div
        ref={dialogRef}
        className={`relative w-full max-w-xl max-h-[90vh] overflow-y-auto bg-surface border-2 border-primary shadow-[0_0_30px_rgba(76,224,210,0.25)] rounded-sm p-6 space-y-6 z-10 ${
          isClosing ? 'modal-exit' : 'modal-enter'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-primary/30 pb-4">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-2xl">dna</span>
            <div>
              <h2 className="font-display text-lg sm:text-xl text-white uppercase tracking-wider">
                Let's Build Your Game DNA
              </h2>
              <p className="font-mono text-xs text-on-surface-variant">
                {step === 4 ? 'DNA Ready' : `Step ${step} of 3 // Personalized Starter`}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="text-on-surface-variant hover:text-primary text-sm font-mono cursor-pointer transition-colors min-w-[32px] min-h-[32px] flex items-center justify-center"
            aria-label="Skip DNA setup"
          >
            SKIP
          </button>
        </div>

        {/* Step 1: Genres */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="space-y-1">
              <h3 className="font-mono text-sm text-white font-bold uppercase">
                What genres do you gravitate toward?
              </h3>
              <p className="text-xs text-on-surface-variant font-mono">
                Select 2–5 genres to seed your baseline preferences.
              </p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2">
              {GENRE_OPTIONS.map((genre) => {
                const isSelected = selectedGenres.includes(genre);
                return (
                  <button
                    key={genre}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => toggleGenre(genre)}
                    className={`px-3 py-2 text-xs font-mono rounded border transition-all text-left flex items-center justify-between cursor-pointer ${
                      isSelected
                        ? 'bg-primary/20 border-primary text-primary font-bold shadow-[0_0_8px_rgba(76,224,210,0.3)]'
                        : 'bg-surface-container-highest/40 border-outline-variant/50 text-on-surface hover:border-outline-variant'
                    }`}
                  >
                    <span>{genre}</span>
                    {isSelected && <span className="material-symbols-outlined text-xs" aria-hidden="true">check</span>}
                  </button>
                );
              })}
            </div>
            <div className="flex justify-between items-center pt-4 border-t border-outline-variant/30">
              <span className="text-[11px] font-mono text-on-surface-variant">
                {selectedGenres.length} selected
              </span>
              <button
                type="button"
                onClick={() => setStep(2)}
                disabled={selectedGenres.length === 0}
                className="px-4 py-1.5 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive cursor-pointer disabled:opacity-50"
              >
                Next Step →
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Mechanics & Enjoyments */}
        {step === 2 && (
          <div className="space-y-4">
            <div className="space-y-1">
              <h3 className="font-mono text-sm text-white font-bold uppercase">
                What elements do you enjoy most in games?
              </h3>
              <p className="text-xs text-on-surface-variant font-mono">
                Helps prioritize mechanical tone over pure theme labels.
              </p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
              {ENJOYMENT_OPTIONS.map((item) => {
                const isSelected = selectedEnjoyments.includes(item);
                return (
                  <button
                    key={item}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => toggleEnjoyment(item)}
                    className={`px-3 py-2 text-xs font-mono rounded border transition-all text-left flex items-center justify-between cursor-pointer ${
                      isSelected
                        ? 'bg-secondary/20 border-secondary text-secondary font-bold shadow-[0_0_8px_rgba(255,0,85,0.3)]'
                        : 'bg-surface-container-highest/40 border-outline-variant/50 text-on-surface hover:border-outline-variant'
                    }`}
                  >
                    <span>{item}</span>
                    {isSelected && <span className="material-symbols-outlined text-xs" aria-hidden="true">check</span>}
                  </button>
                );
              })}
            </div>
            <div className="flex justify-between items-center pt-4 border-t border-outline-variant/30">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-xs font-mono text-on-surface-variant hover:text-white cursor-pointer"
              >
                ← Back
              </button>
              <button
                type="button"
                onClick={() => setStep(3)}
                className="px-4 py-1.5 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive cursor-pointer"
              >
                Next Step →
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Avoidances */}
        {step === 3 && (
          <div className="space-y-4">
            <div className="space-y-1">
              <h3 className="font-mono text-sm text-white font-bold uppercase">
                Anything you'd prefer to avoid? (Optional)
              </h3>
              <p className="text-xs text-on-surface-variant font-mono">
                Applies a deterministic negative filter so these don't crowd your picks.
              </p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2">
              {AVOID_OPTIONS.map((item) => {
                const isSelected = selectedAvoidances.includes(item);
                return (
                  <button
                    key={item}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => toggleAvoidance(item)}
                    className={`px-3 py-2 text-xs font-mono rounded border transition-all text-left flex items-center justify-between cursor-pointer ${
                      isSelected
                        ? 'bg-amber-500/20 border-amber-400 text-amber-300 font-bold'
                        : 'bg-surface-container-highest/40 border-outline-variant/50 text-on-surface hover:border-outline-variant'
                    }`}
                  >
                    <span>{item}</span>
                    {isSelected && <span className="material-symbols-outlined text-xs" aria-hidden="true">block</span>}
                  </button>
                );
              })}
            </div>
            <div className="flex justify-between items-center pt-4 border-t border-outline-variant/30">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="text-xs font-mono text-on-surface-variant hover:text-white cursor-pointer"
              >
                ← Back
              </button>
              <button
                type="button"
                onClick={handleFinish}
                disabled={isSubmitting}
                className="px-5 py-1.5 bg-gradient-to-r from-primary to-primary-bright text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive shadow-[0_0_12px_rgba(76,224,210,0.4)] cursor-pointer"
              >
                {isSubmitting ? 'Saving...' : 'Complete Game DNA ✓'}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Completion Confirmation */}
        {step === 4 && (
          <div className="text-center py-6 space-y-4 animate-fade-in">
            <div className="w-12 h-12 mx-auto rounded-full bg-emerald-500/20 border border-emerald-400 flex items-center justify-center">
              <span className="material-symbols-outlined text-emerald-400 text-2xl" aria-hidden="true">check</span>
            </div>
            <div className="space-y-1">
              <h3 className="font-display text-xl text-white uppercase tracking-wider">
                Your Game DNA is Ready!
              </h3>
              <p className="font-mono text-xs text-on-surface-variant max-w-sm mx-auto">
                Your future discoveries and recommendations will now adapt seamlessly to your preferences.
              </p>
            </div>
            <div className="pt-4">
              <button
                type="button"
                onClick={() => {
                  onClose();
                  if (onCompleted) onCompleted();
                }}
                className="px-6 py-2 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive energy-sweep glow-cyan cursor-pointer"
              >
                Start Exploring
              </button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};
