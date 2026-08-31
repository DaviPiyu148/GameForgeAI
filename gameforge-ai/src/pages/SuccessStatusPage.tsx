import { Link, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { useAppContext } from '../context/AppContext';
import { PrototypeModal } from '../components/Shared/PrototypeModal';

const SuccessStatusPage = () => {
  const [showPlayModal, setShowPlayModal] = useState(false);
  const [showTechnicalLogs, setShowTechnicalLogs] = useState(false);
  const { state, updateGameProject } = useAppContext();
  const navigate = useNavigate();

  const logsToDisplay = state.compilerLogs.length > 0
    ? state.compilerLogs
    : [
        '[SYS] Pipeline initialized.',
        '[AI] Game specification generated & validated.',
        '[PHASER] 2D Runtime initialized.',
        '[SYS] Prototype ready.',
      ];

  const hasRecoveredIssues = logsToDisplay.some(
    (l) => l.includes('WARNING') || l.includes('repair') || l.includes('normalization') || l.includes('remediation')
  );


  // If we somehow get here without a real SUCCESS state (direct refresh/navigation,
  // bookmarked URL, or after logout cleared build state), kick back to builder rather
  // than rendering a stale/unrelated "just built" success screen — mirrors
  // ErrorStatusPage's identical guard.
  useEffect(() => {
    if (state.buildStatus !== 'SUCCESS') {
      navigate('/build');
    }
  }, [state.buildStatus, navigate]);

  if (state.buildStatus !== 'SUCCESS') return null;

  // FS-024 fix: Do not silently fall back to an unrelated myGames[0] when
  // activeProjectId is set but the project has not yet loaded.
  // Three cases:
  //   1. activeProjectId present and project found → render as normal
  //   2. activeProjectId present but project still loading → show loading state
  //   3. activeProjectId missing / invalid after load completes → recovery state
  const activeProject =
    state.activeProjectId
      ? state.myGames.find((p) => p.id === state.activeProjectId) ?? null
      : state.myGames[0] ?? null;

  const isProjectLoading =
    !activeProject &&
    state.activeProjectId != null &&
    (state.isProjectsLoading === true);

  if (isProjectLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-primary font-mono text-xs border border-primary/30 bg-surface-container-low p-6 text-center animate-pulse">
          &gt; LOADING_PROJECT_DATA...
        </div>
      </div>
    );
  }

  const projectMissing = !activeProject && state.activeProjectId != null && !state.isProjectsLoading;

  if (projectMissing) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 gap-4">
        <span className="material-symbols-outlined text-4xl text-error">error_outline</span>
        <p className="font-mono text-xs text-on-surface-variant text-center max-w-sm">
          Build succeeded but project data could not be retrieved. Please visit the Dashboard to access your project.
        </p>
        <div className="flex gap-3">
          <a href="#/dashboard" className="px-4 py-2 font-mono text-xs uppercase bg-primary text-on-primary rounded cursor-pointer">
            Dashboard
          </a>
          <a href="#/build" className="px-4 py-2 font-mono text-xs uppercase border border-outline-variant text-on-surface rounded cursor-pointer">
            Build Again
          </a>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-16 w-full max-w-[800px] mx-auto relative z-10">
        {/* 1. Success Icon & Title */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-24 h-24 rounded-full border-4 border-primary bg-primary/10 glow-cyan flex items-center justify-center modal-enter mb-6">
            <span
              className="material-symbols-outlined text-6xl text-primary"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              done_all
            </span>
          </div>

          <h1 className="font-display text-2xl md:text-3xl text-on-surface uppercase final-reveal mb-2">
            PROTOTYPE VALIDATED
          </h1>

          <p className="font-mono text-xs text-primary final-reveal">
            &gt; SUCCESS_CODE: 0x00_SYS_READY
            {activeProject ? ` | ${activeProject.title}` : ''}
          </p>
        </div>

        {/* 2. Validation Terminal */}
        <div className="w-full border border-outline-variant bg-terminal-bg rounded-lg overflow-hidden mb-6 shadow-2xl">
          {/* Terminal Header */}
          <div className="bg-terminal-header px-4 py-3 flex items-center justify-between border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-secondary-container"></div>
              <div className="w-3 h-3 rounded-full bg-tertiary-container"></div>
              <div className="w-3 h-3 rounded-full bg-primary"></div>
            </div>
            <span className="font-mono text-xs text-on-surface-variant uppercase tracking-wider">
              VALIDATION_SEQUENCE.exe
            </span>
            <div className="w-14"></div>
          </div>

          {/* Terminal Body */}
          <div className="p-6 font-mono text-sm space-y-3.5 text-left">
            <div className="flex items-center gap-3 check-anim delay-1">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[16px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Game DSL generated & schema validated
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-2">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[16px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Runtime compatibility verified (Phaser 3.88.2)
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-3">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[16px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Project persisted to backend database
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-4">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[16px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Deterministic runtime metadata attached
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-5">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[16px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Playable prototype ready for browser simulation
              </span>
            </div>

            <div className="flex items-center gap-2 pt-2 text-on-surface-variant final-reveal">
              <span className="text-primary font-bold">~ $</span>
              <span>System standing by for user input...</span>
              <span className="inline-block w-2 h-[1em] bg-primary terminal-cursor align-middle ml-0.5"></span>
            </div>
          </div>
        </div>

        {/* 2B. Collapsible Technical Build Log */}
        <div className="w-full border border-outline-variant bg-surface-container-low rounded-lg overflow-hidden mb-8 shadow-xl">
          <button
            type="button"
            onClick={() => setShowTechnicalLogs((prev) => !prev)}
            className="w-full px-4 py-3 bg-terminal-header border-b border-outline-variant flex items-center justify-between font-mono text-xs text-on-surface hover:text-primary transition-colors cursor-pointer"
            aria-expanded={showTechnicalLogs}
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-sm text-primary">terminal</span>
              <span className="font-bold uppercase tracking-wider">TECHNICAL BUILD LOG</span>
              {hasRecoveredIssues && (
                <span className="px-2 py-0.5 text-[10px] bg-amber-400/10 border border-amber-400/40 text-amber-300 rounded uppercase font-bold">
                  RECOVERED
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 text-on-surface-variant text-[11px]">
              <span>{showTechnicalLogs ? 'COLLAPSE' : `EXPAND (${logsToDisplay.length} EVENTS)`}</span>
              <span
                className="material-symbols-outlined text-sm transition-transform duration-200"
                style={{ transform: showTechnicalLogs ? 'rotate(180deg)' : 'rotate(0deg)' }}
              >
                expand_more
              </span>
            </div>
          </button>

          {showTechnicalLogs && (
            <div className="p-4 bg-terminal-bg font-mono text-xs max-h-72 overflow-y-auto space-y-1.5 border-t border-outline-variant/40 text-left">
              {logsToDisplay.length === 0 ? (
                <div className="text-on-surface-variant opacity-70">[SYS] Build log stream completed.</div>
              ) : (
                logsToDisplay.map((log, idx) => {
                  const isErr = log.includes('ERROR') || log.includes('FATAL');
                  const isWarn = log.includes('WARNING') || log.includes('repair') || log.includes('Semantic validation');
                  const isSuccess = log.includes('SUCCESS') || log.includes('PASS') || log.includes('ready');
                  const isMod = log.includes('[MOD]');
                  const colorClass = isErr
                    ? 'text-error'
                    : isWarn
                    ? 'text-amber-300'
                    : isSuccess
                    ? 'text-emerald-400'
                    : isMod
                    ? 'text-secondary-soft'
                    : 'text-primary/90';
                  return (
                    <div key={idx} className={`leading-relaxed break-words ${colorClass}`}>
                      {log}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* 3. Action Buttons */}
        <div className="flex flex-row flex-wrap items-center justify-center gap-4 final-reveal w-full">
          <button
            onClick={() => setShowPlayModal(true)}
            className="bg-primary text-on-primary glow-cyan btn-interactive energy-sweep font-mono uppercase px-8 py-4 flex items-center justify-center gap-2 font-bold tracking-wider rounded cursor-pointer"
          >
            <span
              className="material-symbols-outlined text-xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              play_arrow
            </span>
            <span>PLAY PROTOTYPE</span>
          </button>

          <Link
            to="/build"
            className="border border-secondary-soft text-secondary-soft hover:bg-secondary/10 font-mono uppercase px-8 py-4 flex items-center justify-center gap-2 font-bold tracking-wider rounded btn-interactive cursor-pointer"
          >
            <span className="material-symbols-outlined text-xl">edit</span>
            <span>MODIFY</span>
          </Link>

          <Link
            to="/dashboard"
            className="border border-outline-variant text-on-surface hover:text-primary hover:border-primary font-mono uppercase px-8 py-4 flex items-center justify-center gap-2 font-bold tracking-wider rounded btn-interactive cursor-pointer"
          >
            <span className="material-symbols-outlined text-xl">dashboard</span>
            <span>DASHBOARD</span>
          </Link>
        </div>
      </div>

      {/* Play Prototype Modal */}
      {showPlayModal && (
        <PrototypeModal
          project={activeProject}
          onClose={() => setShowPlayModal(false)}
          onProjectUpdated={updateGameProject}
        />
      )}
    </>
  );
};

export default SuccessStatusPage;
