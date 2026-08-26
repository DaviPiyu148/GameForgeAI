import { Link, useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

const ErrorStatusPage = () => {
  const { state, retryBuild } = useAppContext();
  const navigate = useNavigate();
  const [showLogModal, setShowLogModal] = useState(false);
  const [isClosingModal, setIsClosingModal] = useState(false);
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  const handleCloseModal = () => {
    setIsClosingModal(true);
    setTimeout(() => {
      setShowLogModal(false);
      setIsClosingModal(false);
    }, 250);
  };

  // If we somehow get here without an error state, kick back to builder
  useEffect(() => {
    if (state.buildStatus !== 'ERROR') {
      navigate('/build');
    }
  }, [state.buildStatus, navigate]);

  // Log Modal Accessibility — MUST be before any early return (Rules of Hooks)
  useEffect(() => {
    if (showLogModal) {
      closeBtnRef.current?.focus();
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && !isClosingModal) handleCloseModal();
      };
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [showLogModal, isClosingModal]);

  if (state.buildStatus !== 'ERROR') return null;

  const errorCode = state.lastError?.code || 'BUILD_ERROR';
  const isAiConfigError = errorCode === 'AI_CONFIGURATION_ERROR';
  const errorMessage = isAiConfigError
    ? 'AI GENERATION UNAVAILABLE // HOSTED MODEL API KEY NOT CONFIGURED'
    : state.lastError?.message || 'Prototype synthesis interrupted.';

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 md:p-8 my-auto w-full max-w-4xl mx-auto space-y-8">
      {/* 1. Warning Icon & Title */}
      <div className="flex flex-col items-center gap-4 w-full text-center">
        <span
          className="material-symbols-outlined text-[64px] text-error text-glow-error"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          warning
        </span>

        <h1 className="font-display text-xl md:text-2xl text-error uppercase border-y-4 border-error py-2 w-full tracking-wider">
          {isAiConfigError ? 'HOSTED AI GENERATION UNAVAILABLE' : 'PROTOTYPE GENERATION INTERRUPTED'}
        </h1>

        <div className="font-mono text-xs bg-error/10 px-4 py-2 border border-error/30 text-on-error-container w-full">
          {errorMessage.toUpperCase()}
        </div>
      </div>

      {/* 2. Error Terminal */}
      <div className="bg-terminal-bg border-2 border-error glow-error overflow-hidden w-full crt-flicker delay-2">
        {/* Header */}
        <div className="bg-terminal-header border-b-2 border-error px-4 py-2.5 flex items-center justify-between select-none">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-error/80"></div>
            <div className="w-3 h-3 rounded-full bg-tertiary/80"></div>
            <div className="w-3 h-3 rounded-full bg-primary/80"></div>
          </div>
          <div className="flex items-center gap-2 font-mono text-xs text-on-surface-variant tracking-wider">
            <span className="material-symbols-outlined text-sm text-error">bug_report</span>
            <span>ERROR_LOG_TTY1</span>
          </div>
        </div>

        {/* Body */}
        <div className="p-4 font-mono text-xs h-64 overflow-y-auto space-y-2 text-left">
          <div className="text-on-surface-variant">
            <span className="text-primary font-bold">root@gameforge:~$</span> tail -f /var/log/syslog | grep error
          </div>

          <div className="text-error font-bold">
            &gt; FATAL_EXCEPTION: {errorCode}
          </div>

          <div className="text-on-surface-variant/80">
            [STATUS: TERMINATED] {errorMessage}
          </div>

          <div className="flex items-center gap-2 py-1">
            <span className="text-on-surface-variant">MODULE:</span>
            <span className="text-tertiary font-bold inline-flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">memory</span>
              AI_BUILD_SERVICE
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-on-surface-variant">STATUS:</span>
            <span className="text-primary font-bold inline-flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">health_and_safety</span>
              RECOVERABLE
            </span>
          </div>

          <p className="text-on-surface-variant/70 leading-relaxed pt-2 pb-1">
            Build execution failed safety checks or timed out. Prompt parameters preserved in memory. Retry generation to request a fresh synthesis pass.
          </p>

          <div className="text-on-surface-variant flex items-center gap-1 pt-1">
            <span className="text-primary font-bold">root@gameforge:~$</span>
            <span className="w-2.5 h-4 bg-error terminal-cursor inline-block align-middle ml-1"></span>
          </div>
        </div>
      </div>

      {/* 3. Action Buttons */}
      <div className="flex flex-wrap items-center justify-center gap-4 w-full">
        <button
          onClick={() => retryBuild(navigate)}
          disabled={(state.buildStatus as string) === 'COMPILING'}
          className={`font-mono text-xs uppercase px-6 py-3 bg-primary text-on-primary border-2 border-primary font-bold inline-flex items-center justify-center gap-2 glow-cyan btn-interactive energy-sweep cursor-pointer ${(state.buildStatus as string) === 'COMPILING' ? 'opacity-50 cursor-wait' : 'hover:bg-primary-bright hover:border-primary-bright'}`}
        >
          <span
            className={`material-symbols-outlined text-base inline-block ${(state.buildStatus as string) === 'COMPILING' ? 'animate-spin' : ''}`}
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {(state.buildStatus as string) === 'COMPILING' ? 'sync' : 'restart_alt'}
          </span>
          {(state.buildStatus as string) === 'COMPILING' ? 'COMPILING...' : 'RETRY GENERATION'}
        </button>

        <Link
          to="/build"
          className="font-mono text-xs uppercase px-6 py-3 text-primary border-2 border-primary font-bold inline-flex items-center justify-center gap-2 hover:bg-primary/10 btn-interactive cursor-pointer"
        >
          <span className="material-symbols-outlined text-base">edit_note</span>
          MODIFY IN BUILDER
        </Link>

        <Link
          to="/dashboard"
          className="font-mono text-xs uppercase px-6 py-3 text-secondary-soft border-2 border-secondary-soft font-bold inline-flex items-center justify-center gap-2 hover:bg-secondary/10 btn-interactive cursor-pointer"
        >
          <span className="material-symbols-outlined text-base">dashboard</span>
          VIEW DASHBOARD
        </Link>
      </div>

      {/* 4. Below buttons */}
      <div>
        <button
          onClick={() => setShowLogModal(true)}
          className="font-mono text-xs text-tertiary hover:underline tracking-wider uppercase inline-flex items-center gap-1 hover:text-tertiary-bright btn-interactive cursor-pointer"
        >
          <span className="text-tertiary font-bold">&gt;</span>
          VIEW TECHNICAL LOG
        </button>
      </div>

      {/* Technical Log Modal */}
      {showLogModal &&
        createPortal(
          <div
            className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/95 backdrop-blur-sm ${
              isClosingModal ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
            }`}
            onClick={(e) => {
              if (e.target === e.currentTarget && !isClosingModal) handleCloseModal();
            }}
            role="dialog"
            aria-modal="true"
            aria-label="Technical Log"
          >
            <div
              className={`w-full max-w-3xl max-h-[90vh] overflow-y-auto bg-surface border-2 border-error rounded-sm flex flex-col shadow-[0_0_30px_rgba(255,77,77,0.15)] ${
                isClosingModal ? 'modal-exit' : 'modal-enter'
              }`}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="bg-terminal-header border-b border-error/30 p-3 flex justify-between items-center shrink-0">
                <div className="flex items-center gap-2 text-error">
                  <span className="material-symbols-outlined text-sm">terminal</span>
                  <span className="font-mono text-sm tracking-widest font-bold uppercase">COMPILER_LOG.TXT</span>
                </div>
                <button
                  ref={closeBtnRef}
                  onClick={handleCloseModal}
                  className="text-on-surface-variant hover:text-error p-1 icon-interactive focus:outline-none focus:ring-1 focus:ring-error cursor-pointer"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
              <div className="p-4 bg-terminal-bg font-mono text-xs h-96 overflow-y-auto space-y-1">
                {state.compilerLogs.map((log, i) => (
                  <div
                    key={i}
                    className={
                      log.includes('FATAL') || log.includes('ERROR')
                        ? 'text-error font-bold'
                        : log.includes('[MOD]') || log.includes('[PHASER]')
                        ? 'text-secondary-soft'
                        : 'text-primary/80'
                    }
                  >
                    {log}
                  </div>
                ))}
                <div className="text-error animate-pulse mt-4">_</div>
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
};

export default ErrorStatusPage;
