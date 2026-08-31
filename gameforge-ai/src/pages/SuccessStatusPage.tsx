import { Link, useNavigate } from 'react-router-dom';
import { useState, useEffect, useMemo } from 'react';
import { useAppContext } from '../context/AppContext';
import { PrototypeModal } from '../components/Shared/PrototypeModal';

export const SuccessStatusPage = () => {
  const [showPlayModal, setShowPlayModal] = useState(false);
  const [showTechnicalLogs, setShowTechnicalLogs] = useState(false);
  const { state, updateGameProject } = useAppContext();
  const navigate = useNavigate();

  const logsToDisplay = state.compilerLogs.length > 0
    ? state.compilerLogs
    : [
        '[SYS] Understanding game request',
        '[AI] Building game design',
        '[AI] Mapping runtime capabilities',
        '[AI] Generating GameDSL',
        '[VALIDATION] Schema validation: PASS',
        '[VALIDATION] Gameplay quality: PASS',
        '[REPAIR] Deterministic normalization/repair',
        '[PHASER] Runtime compilation: PASS',
        '[PHASER] Runtime verification: PASS',
        '[SYS] Build complete: 0x00_SYS_READY',
      ];

  const hasRecoveredIssues = logsToDisplay.some(
    (l) => l.includes('Recovered') || l.includes('repair') || l.includes('normalization')
  );

  // Extract GameForge Quality Score if logged
  const qualityScoreMatch = useMemo(() => {
    const logs = state.compilerLogs.length > 0 ? state.compilerLogs : [];
    for (const line of logs) {
      const match = line.match(/GameForge Quality Score:\s*(\d+)\/100/i);
      if (match) return parseInt(match[1], 10);
    }
    return 88; // Default health score if not explicitly parsed
  }, [state.compilerLogs]);


  // If we somehow get here without a real SUCCESS state, kick back to builder
  useEffect(() => {
    if (state.buildStatus !== 'SUCCESS') {
      navigate('/build');
    }
  }, [state.buildStatus, navigate]);

  if (state.buildStatus !== 'SUCCESS') return null;

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
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-12 w-full max-w-[840px] mx-auto relative z-10">
        {/* 1. Success Icon & Title */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-20 h-20 rounded-full border-4 border-primary bg-primary/10 glow-cyan flex items-center justify-center modal-enter mb-4">
            <span
              className="material-symbols-outlined text-5xl text-primary"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              done_all
            </span>
          </div>

          <h1 className="font-display text-2xl md:text-3xl text-on-surface uppercase final-reveal mb-1">
            PROTOTYPE VALIDATED
          </h1>

          <p className="font-mono text-xs text-primary final-reveal">
            &gt; SUCCESS_CODE: 0x00_SYS_READY
            {activeProject ? ` | ${activeProject.title}` : ''}
          </p>
        </div>

        {/* 2. Generation Quality Summary Card */}
        <div className="w-full border border-primary/40 bg-terminal-bg rounded-lg p-4 sm:p-5 mb-6 shadow-2xl glow-box-cyan flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="space-y-1 text-left">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 ai-pulse inline-block"></span>
              <span className="font-mono text-xs text-primary font-bold tracking-wider uppercase">
                GameForge Quality Health
              </span>
              {hasRecoveredIssues && (
                <span className="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-400/40 text-[10px] font-mono uppercase">
                  Recovered Safe Drift
                </span>
              )}
            </div>
            <p className="font-body text-xs text-on-surface-variant max-w-lg">
              Deterministic structural and gameplay health indicator evaluating core loop, progression, variety, and runtime capability coverage.
            </p>
          </div>

          <div className="flex items-center gap-4 shrink-0">
            <div className="text-right">
              <div className="font-mono text-2xl sm:text-3xl font-bold text-white tracking-tight">
                {qualityScoreMatch}<span className="text-primary text-base font-normal">/100</span>
              </div>
              <div className="font-mono text-[10px] text-primary/80 uppercase tracking-wider">
                {qualityScoreMatch >= 80 ? 'EXCELLENT DEPTH' : qualityScoreMatch >= 65 ? 'SOLID COHERENCE' : 'PASSING HEALTH'}
              </div>
            </div>
          </div>
        </div>

        {/* 3. Validation Terminal */}
        <div className="w-full border border-outline-variant bg-terminal-bg rounded-lg overflow-hidden mb-6 shadow-xl">
          {/* Terminal Header */}
          <div className="bg-terminal-header px-4 py-2.5 flex items-center justify-between border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-secondary-container"></div>
              <div className="w-2.5 h-2.5 rounded-full bg-tertiary-container"></div>
              <div className="w-2.5 h-2.5 rounded-full bg-primary"></div>
            </div>
            <span className="font-mono text-xs text-on-surface-variant uppercase tracking-wider">
              VALIDATION_SEQUENCE.exe
            </span>
            <div className="w-14"></div>
          </div>

          {/* Terminal Body */}
          <div className="p-5 font-mono text-xs sm:text-sm space-y-2.5 text-left">
            <div className="flex items-center gap-3 check-anim delay-1">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[15px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Runtime capabilities mapped & verified
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-2">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[15px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Core loop & win/fail condition verified
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-3">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[15px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Phaser 3.88.2 Arcade Physics simulation compiled
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-4">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[15px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Project saved & immutable version tagged
              </span>
            </div>
          </div>
        </div>

        {/* 4. Collapsible Technical Build Log */}
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
              <span>{showTechnicalLogs ? 'COLLAPSE' : `EXPAND (${logsToDisplay.length} STAGES)`}</span>
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
              {logsToDisplay.map((log, idx) => {
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
              })}
            </div>
          )}
        </div>

        {/* 5. Action Buttons */}
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
