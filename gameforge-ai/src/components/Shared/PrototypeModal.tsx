import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import type { GameDSL, Archetype, PlaytestSummary, PlaytestAnalysis, PlaytestRecommendation } from '../../runtime/types';
import type { GameProject, GameBlueprint, RemixIntentType } from '../../types';
import {
  SURVIVAL_FIXTURE,
  SHOOTER_FIXTURE,
  PLATFORMER_FIXTURE,
  COLLECTOR_FIXTURE,
} from '../../runtime/fixtures';
import { apiClient, ApiError } from '../../services/api';
import { useAppContext } from '../../context/AppContext';
import { buildDiscoverySeed } from '../../utils/discovery';

const PhaserCanvas = React.lazy(() => import('../../runtime/PhaserCanvas').then(m => ({ default: m.PhaserCanvas })));
import { projectService } from '../../services/projects';
import { GameBlueprintPanel } from './GameBlueprintPanel';
import { RemixPanel } from './RemixPanel';

// Top-level GameDSL sections a locally-applied improvement patch may target when the
// backend improvement endpoint is unreachable. Keep in sync with GameDSL (runtime/types.ts).
const DSL_PATCHABLE_SECTIONS = new Set(['player', 'world', 'entities', 'rules', 'ui', 'metadata']);

interface PrototypeModalProps {
  onClose: () => void;
  project?: GameProject | null;
  gameDsl?: GameDSL;
  onProjectUpdated?: (updatedProject: GameProject) => void;
  initialTab?: 'play' | 'remix';
}

const ARCHETYPE_FIXTURES: Record<Archetype, GameDSL> = {
  survival: SURVIVAL_FIXTURE,
  shooter: SHOOTER_FIXTURE,
  platformer: PLATFORMER_FIXTURE,
  collector: COLLECTOR_FIXTURE,
  arena: SHOOTER_FIXTURE,
  runner: PLATFORMER_FIXTURE,
};

import { useModalDialog } from '../../hooks/useModalDialog';

export const PrototypeModal: React.FC<PrototypeModalProps> = ({
  onClose,
  project,
  gameDsl,
  onProjectUpdated,
  initialTab = 'play',
}) => {
  const navigate = useNavigate();
  const { refreshProgress, searchDiscovery } = useAppContext();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fullscreenPulse, setFullscreenPulse] = useState(false);
  const [currentDsl, setCurrentDsl] = useState<GameDSL>(
    project?.gameDsl || gameDsl || SURVIVAL_FIXTURE
  );
  const [currentVersion, setCurrentVersion] = useState<number>(project?.currentVersion || 1);
  const [resolvedSeed, setResolvedSeed] = useState<number>(project?.runtimeMetadata?.seed ?? 18492031);

  const [activeArchetype, setActiveArchetype] = useState<Archetype>(
    currentDsl.metadata.archetype || 'survival'
  );
  const modalContainerRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  const { isClosing, handleClose, handleBackdropClick, dialogRef } = useModalDialog({
    isOpen: true,
    onClose,
    initialFocusRef: closeBtnRef,
    closeDelayMs: 200,
  });

  // Playtest state
  const [playtestSummary, setPlaytestSummary] = useState<PlaytestSummary | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState<PlaytestAnalysis | null>(null);
  const [selectedRecIds, setSelectedRecIds] = useState<string[]>([]);
  const [isApplyingImprovement, setIsApplyingImprovement] = useState(false);
  const [improvementSuccess, setImprovementSuccess] = useState<string | null>(null);

  // Phase 4: Game Blueprint & Remix state
  const [blueprint, setBlueprint] = useState<GameBlueprint | null>(null);
  const [isLoadingBlueprint, setIsLoadingBlueprint] = useState(false);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);
  const [isRemixPanelOpen, setIsRemixPanelOpen] = useState(initialTab === 'remix');
  const [isApplyingRemix, setIsApplyingRemix] = useState(false);
  const [remixError, setRemixError] = useState<string | null>(null);

  const projectId = project?.id;

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    setIsLoadingBlueprint(true);
    setBlueprintError(null);
    projectService
      .getBlueprint(projectId)
      .then((bp) => {
        if (!cancelled) setBlueprint(bp);
      })
      .catch((err) => {
        if (!cancelled) setBlueprintError(err instanceof ApiError ? err.message : 'Unable to load blueprint.');
      })
      .finally(() => {
        if (!cancelled) setIsLoadingBlueprint(false);
      });
    return () => {
      cancelled = true;
    };
    // Refetch whenever the project's version changes (remix or improvement applied)
    // so the blueprint always reflects the currently playable DSL/design spec.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, currentVersion]);

  // Fullscreen toggle — targets the modal outer container so the entire dialog
  // including header, canvas, and AI panel enters fullscreen (not just the canvas).
  const handleToggleFullscreen = useCallback(() => {
    const elem = modalContainerRef.current;
    if (!elem) return;

    const fsElem = document.fullscreenElement || (document as unknown as { webkitFullscreenElement?: Element }).webkitFullscreenElement;
    if (!fsElem) {
      const requestFs = elem.requestFullscreen || (elem as unknown as { webkitRequestFullscreen?: () => Promise<void> }).webkitRequestFullscreen;
      if (requestFs) {
        requestFs.call(elem).catch((err: unknown) => {
          console.warn('Fullscreen request failed:', err);
        });
      }
    } else {
      const exitFs = document.exitFullscreen || (document as unknown as { webkitExitFullscreen?: () => Promise<void> }).webkitExitFullscreen;
      if (exitFs) {
        exitFs.call(document).catch((err: unknown) => {
          console.warn('Exit fullscreen failed:', err);
        });
      }
    }
  }, []);

  // Keep isFullscreen in sync with the browser's native fullscreen state
  // (e.g. user presses ESC to exit fullscreen — browser handles it natively
  // but we need to update the icon back to fullscreen).
  useEffect(() => {
    const onFullscreenChange = () => {
      const fsElem = document.fullscreenElement || (document as unknown as { webkitFullscreenElement?: Element }).webkitFullscreenElement;
      setIsFullscreen(Boolean(fsElem));
      // Brief scale/opacity pulse to mark the fullscreen transition itself
      setFullscreenPulse(true);
      setTimeout(() => setFullscreenPulse(false), 260);
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);
    document.addEventListener('webkitfullscreenchange', onFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', onFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', onFullscreenChange);
    };
  }, []);

  // Handlers for playtesting and remixing

  const handlePlaytestComplete = async (summary: PlaytestSummary) => {
    setPlaytestSummary(summary);

    // If authenticated with a backend project, record session
    if (project?.id) {
      try {
        await apiClient.post(`/projects/${project.id}/playtests`, summary);
        // REQ-4: Exactly one progress refresh per completed playtest action
        await refreshProgress();
      } catch (err) {
        console.warn('Could not record playtest session to backend:', err);
      }
    }
  };

  const handleAnalyzeWithAI = async () => {
    if (!playtestSummary) return;
    setIsAnalyzing(true);
    setAiAnalysis(null);

    const projectId = project?.id;

    if (projectId) {
      try {
        const data = await apiClient.post<PlaytestAnalysis>(
          `/projects/${projectId}/analyze-playtest`,
          { telemetry: playtestSummary }
        );
        setAiAnalysis(data);
        setSelectedRecIds(data.recommendations.map((r) => r.id));
        setIsAnalyzing(false);
        return;
      } catch (err) {
        console.warn('AI analysis request failed, falling back to local critique:', err);
      }
    }

    // Local deterministic analysis fallback
    setTimeout(() => {
      const fallbackCritique: PlaytestAnalysis = {
        fun_rating: 8.0,
        difficulty_rating: 6.8,
        clarity_rating: 8.5,
        strengths: [
          'Evasion and locomotion feel responsive with smooth physics acceleration',
          'Collectible feedback encourages map traversal and score pursuit',
        ],
        problems: [
          playtestSummary.damage_taken > 50
            ? 'Player received heavy damage from fast enemy collisions'
            : 'Early wave enemies could scale difficulty faster',
        ],
        recommendations: [
          {
            id: 'rec_speed_boost',
            category: 'mobility',
            description: 'Increase player speed by 15% to enhance evasion mobility against chaser enemies.',
            dsl_change_type: 'player_speed',
            suggested_patch: { player: { speed: Math.round((currentDsl.player.speed || 250) * 1.15) } },
          },
          {
            id: 'rec_extra_gem',
            category: 'economy',
            description: 'Add bonus energy pickups to reward tactical exploration.',
            dsl_change_type: 'add_collectibles',
            suggested_patch: { add_collectibles_count: 2 },
          },
        ],
      };
      setAiAnalysis(fallbackCritique);
      setSelectedRecIds(fallbackCritique.recommendations.map((r) => r.id));
      setIsAnalyzing(false);
    }, 800);
  };

  const toggleRecommendation = (id: string) => {
    setSelectedRecIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleApplyImprovements = async () => {
    if (!aiAnalysis || selectedRecIds.length === 0) return;
    setIsApplyingImprovement(true);

    const chosenRecs = aiAnalysis.recommendations.filter((r) => selectedRecIds.includes(r.id));
    const projectId = project?.id;

    if (projectId) {
      try {
        const data = await apiClient.post<{ game_dsl: GameDSL; version_number: number }>(
          `/projects/${projectId}/improvements`,
          { selected_recommendations: chosenRecs }
        );
        setCurrentDsl(data.game_dsl);
        setCurrentVersion(data.version_number);
        setResolvedSeed((prev) => prev + 100);
        setImprovementSuccess(`Successfully upgraded to Version ${data.version_number}!`);
        setIsApplyingImprovement(false);
        setPlaytestSummary(null);
        setAiAnalysis(null);
        if (onProjectUpdated && project) {
          onProjectUpdated({
            ...project,
            gameDsl: data.game_dsl,
            currentVersion: data.version_number,
          });
        }
        // REQ-4: Exactly one progress refresh per completed improvement action
        await refreshProgress();
        return;
      } catch (err) {
        console.warn('Backend improvement application failed, applying local patch:', err);
      }
    }

    // Local (offline) patch application: mirrors the backend's generic top-level-section
    // merge (see game_generation_service.apply_improvements' fallback), but — unlike a
    // silent partial patch — never claims full success for recommendations it can't apply.
    const clonedDsl = JSON.parse(JSON.stringify(currentDsl));
    const appliedRecs: PlaytestRecommendation[] = [];
    const unsupportedRecs: PlaytestRecommendation[] = [];

    chosenRecs.forEach((r) => {
      const patch = r.suggested_patch || {};
      const patchableKeys = Object.keys(patch).filter((k) => DSL_PATCHABLE_SECTIONS.has(k));
      if (patchableKeys.length === 0) {
        unsupportedRecs.push(r);
        return;
      }
      patchableKeys.forEach((k) => {
        const value = patch[k];
        if (value && typeof value === 'object' && !Array.isArray(value) && clonedDsl[k] && typeof clonedDsl[k] === 'object') {
          clonedDsl[k] = { ...clonedDsl[k], ...value };
        } else {
          clonedDsl[k] = value;
        }
      });
      appliedRecs.push(r);
    });

    const newVer = currentVersion + 1;
    setCurrentDsl(clonedDsl);
    setCurrentVersion(newVer);
    setResolvedSeed((prev) => prev + 100);
    if (unsupportedRecs.length > 0) {
      setImprovementSuccess(
        `Applied ${appliedRecs.length}/${chosenRecs.length} improvement(s) offline (Version ${newVer}). ` +
          `${unsupportedRecs.length} recommendation(s) could not be applied without a backend connection: ` +
          unsupportedRecs.map((r) => `"${r.description}"`).join(', ') +
          '.'
      );
    } else {
      setImprovementSuccess(`Successfully upgraded to Version ${newVer}! (offline patch)`);
    }
    setIsApplyingImprovement(false);
    setPlaytestSummary(null);
    setAiAnalysis(null);
  };

  const handleApplyRemix = async (intents: RemixIntentType[]) => {
    if (!projectId || intents.length === 0) return;
    setIsApplyingRemix(true);
    setRemixError(null);

    try {
      const data = await projectService.applyRemix(
        projectId,
        intents.map((type) => ({ type }))
      );
      setCurrentDsl(data.game_dsl);
      setCurrentVersion(data.version_number);
      setBlueprint(data.blueprint);
      setResolvedSeed((prev) => prev + 100);
      setIsRemixPanelOpen(false);
      setImprovementSuccess(`Remix applied! Now on Version ${data.version_number}.`);
      if (onProjectUpdated && project) {
        onProjectUpdated({
          ...project,
          gameDsl: data.game_dsl,
          designSpec: data.design_spec ?? project.designSpec,
          currentVersion: data.version_number,
        });
      }
      // REQ-4: Exactly one progress refresh per completed remix action
      await refreshProgress();
    } catch (err) {
      setRemixError(err instanceof ApiError ? err.message : 'Remix failed. Please try again.');
    } finally {
      setIsApplyingRemix(false);
    }
  };

  const handleDiscoverMoreLikeThis = () => {
    if (!project) return;
    const seed = buildDiscoverySeed(project);
    handleClose();
    searchDiscovery(seed, navigate, 'BEST_MATCH');
  };

  return createPortal(
    <div
      ref={modalContainerRef}
      className={`fixed inset-0 z-50 flex items-center justify-center ${
        isFullscreen ? 'p-0 bg-background' : 'p-2 sm:p-4 bg-background/90 backdrop-blur-sm'
      } ${
        isClosing ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
      }`}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label="Playable 2D Prototype (Phaser Runtime)"
    >
      <div
        ref={dialogRef}
        className={`w-full ${
          isFullscreen
            ? 'h-full max-h-screen max-w-none rounded-none border-0'
            : 'max-w-5xl max-h-[95vh] rounded-lg border-2 border-primary shadow-[0_0_50px_rgba(76,224,210,0.2)]'
        } overflow-y-auto bg-surface flex flex-col ${
          isClosing ? 'modal-exit' : 'modal-enter'
        } ${fullscreenPulse ? 'fullscreen-transition' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header */}
        <div className="bg-terminal-header border-b border-primary/30 p-3 flex flex-wrap justify-between items-center gap-2 shrink-0">
          <div className="flex items-center gap-3 text-primary">
            <span className="material-symbols-outlined animate-pulse" aria-hidden="true">
              videogame_asset
            </span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm tracking-widest font-bold">
                {currentDsl.metadata.title.toUpperCase()}
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary/20 text-primary border border-primary/40 uppercase font-bold">
                v{currentVersion}.0
              </span>
            </div>
          </div>

          {!project && !gameDsl && (
            <div className="flex items-center gap-1 bg-surface/80 p-1 rounded border border-primary/30">
              <span className="text-[11px] font-mono text-on-surface-variant px-2 hidden sm:inline">
                Archetypes:
              </span>
              {(['survival', 'shooter', 'platformer', 'collector'] as Archetype[]).map((arch) => (
                <button
                  key={arch}
                  onClick={() => {
                    setActiveArchetype(arch);
                    setCurrentDsl(ARCHETYPE_FIXTURES[arch]);
                  }}
                  className={`px-2.5 py-1 text-xs font-mono rounded transition-colors uppercase ${
                    activeArchetype === arch
                      ? 'bg-primary text-surface font-bold shadow-[0_0_10px_rgba(76,224,210,0.4)]'
                      : 'text-on-surface-variant hover:text-primary hover:bg-primary/10'
                  }`}
                >
                  {arch}
                </button>
              ))}
            </div>
          )}

          {/* Right header actions: fullscreen + close */}
          <div className="flex items-center gap-1 ml-auto">
            <button
              onClick={handleToggleFullscreen}
              className="text-on-surface-variant icon-interactive hover:text-primary transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center rounded focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer"
              aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
              title={isFullscreen ? 'Exit fullscreen (ESC)' : 'Enter fullscreen'}
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                {isFullscreen ? 'fullscreen_exit' : 'fullscreen'}
              </span>
            </button>

            <button
              ref={closeBtnRef}
              onClick={handleClose}
              className="text-on-surface-variant icon-interactive hover:text-error transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center rounded focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer"
              aria-label="Close prototype preview"
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                close
              </span>
            </button>
          </div>
        </div>

        {/* Improvement Success Banner with Creator Loop Actions */}
        {improvementSuccess && (
          <div className="bg-primary/20 border-b border-primary/40 px-4 py-2 flex items-center justify-between text-xs font-mono text-primary animate-fadeIn flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-sm">check_circle</span>
              <span>{improvementSuccess} Prototype hot-reloaded.</span>
            </div>
            <div className="flex items-center gap-2">
              {projectId && !isRemixPanelOpen && (
                <button
                  type="button"
                  onClick={() => setIsRemixPanelOpen(true)}
                  className="px-2.5 py-1 text-[11px] font-mono font-bold rounded bg-secondary text-on-secondary hover:bg-secondary/90 transition-colors flex items-center gap-1 cursor-pointer"
                >
                  <span className="material-symbols-outlined text-xs">shuffle</span>
                  <span>Try a Remix →</span>
                </button>
              )}
              {projectId && (
                <button
                  type="button"
                  onClick={handleDiscoverMoreLikeThis}
                  className="px-2.5 py-1 text-[11px] font-mono font-bold rounded border border-primary/50 text-primary hover:bg-primary/10 transition-colors flex items-center gap-1 cursor-pointer"
                >
                  <span className="material-symbols-outlined text-xs">explore</span>
                  <span>Discover More →</span>
                </button>
              )}
              <button
                type="button"
                onClick={() => setImprovementSuccess(null)}
                className="hover:text-white p-0.5 transition-colors cursor-pointer"
                aria-label="Dismiss banner"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* Game Blueprint & Remix (authenticated backend projects only) */}
        {projectId && (
          <div className="bg-surface border-b border-primary/20 p-3 flex flex-col gap-2 shrink-0">
            <GameBlueprintPanel blueprint={blueprint} isLoading={isLoadingBlueprint} error={blueprintError} />
            {!isRemixPanelOpen ? (
              <button
                type="button"
                onClick={() => setIsRemixPanelOpen(true)}
                className="self-start px-4 py-1.5 text-xs font-mono font-bold rounded border border-secondary/50 text-secondary hover:bg-secondary/10 transition-colors flex items-center gap-2 cursor-pointer"
              >
                <span className="material-symbols-outlined text-sm">shuffle</span>
                <span>REMIX THIS GAME</span>
              </button>
            ) : (
              <RemixPanel
                isOpen={isRemixPanelOpen}
                isApplying={isApplyingRemix}
                error={remixError}
                onApply={handleApplyRemix}
                onCancel={() => {
                  setIsRemixPanelOpen(false);
                  setRemixError(null);
                }}
              />
            )}
          </div>
        )}

        {/* Live Phaser Canvas Container */}
        <div className="w-full bg-terminal-bg flex flex-col items-center justify-center p-2 relative min-h-[420px]">
          <div className="w-full max-w-4xl flex justify-center">
            <React.Suspense
              fallback={
                <div className="w-full min-h-[420px] max-h-[500px] flex flex-col items-center justify-center gap-3 bg-[#070810] border border-primary/30 font-mono text-xs text-primary">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined animate-spin text-secondary">sync</span>
                    <span className="tracking-widest">[SYS] INITIALIZING PHASER RUNTIME ENGINE...</span>
                  </div>
                  <div className="text-[10px] text-on-surface-variant uppercase">Loading physics subsystems & texture synthesizers</div>
                </div>
              }
            >
              <PhaserCanvas
                key={`phaser-${currentVersion}-${resolvedSeed}`}
                gameDsl={currentDsl}
                seed={resolvedSeed}
                onClose={handleClose}
                onPlaytestComplete={handlePlaytestComplete}
              />
            </React.Suspense>
          </div>
        </div>

        {/* Playtest Session Results & AI Analysis Deck */}
        {playtestSummary && (
          <div className="bg-surface border-t border-primary/30 p-4 shrink-0 animate-fadeIn">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-amber-400">analytics</span>
                  <span className="font-mono text-sm font-bold text-on-surface">PLAYTEST SESSION SUMMARY</span>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                      playtestSummary.outcome === 'WON'
                        ? 'bg-green-500/20 text-green-400 border border-green-500/40'
                        : 'bg-red-500/20 text-red-400 border border-red-500/40'
                    }`}
                  >
                    {playtestSummary.outcome}
                  </span>
                </div>
                {!aiAnalysis && (
                  <button
                    onClick={handleAnalyzeWithAI}
                    disabled={isAnalyzing}
                    className="px-4 py-1.5 text-xs font-mono font-bold rounded bg-primary text-surface hover:bg-primary/90 transition-all flex items-center gap-2 cursor-pointer shadow-[0_0_20px_rgba(76,224,210,0.5)] ai-pulse disabled:opacity-50"
                  >
                    <span className="material-symbols-outlined text-sm">psychology</span>
                    <span>{isAnalyzing ? 'ANALYZING PLAYTEST...' : 'ANALYZE WITH AI'}</span>
                  </button>
                )}
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 font-mono text-xs">
                <div className="bg-terminal-bg p-2 rounded border border-primary/20">
                  <div className="text-on-surface-variant text-[10px]">DURATION</div>
                  <div className="text-white font-bold">{playtestSummary.duration_seconds}s</div>
                </div>
                <div className="bg-terminal-bg p-2 rounded border border-primary/20">
                  <div className="text-on-surface-variant text-[10px]">FINAL SCORE</div>
                  <div className="text-amber-400 font-bold">{playtestSummary.score}</div>
                </div>
                <div className="bg-terminal-bg p-2 rounded border border-primary/20">
                  <div className="text-on-surface-variant text-[10px]">ENEMIES DEFEATED</div>
                  <div className="text-primary font-bold">{playtestSummary.enemies_defeated}</div>
                </div>
                <div className="bg-terminal-bg p-2 rounded border border-primary/20">
                  <div className="text-on-surface-variant text-[10px]">DAMAGE TAKEN</div>
                  <div className="text-red-400 font-bold">{playtestSummary.damage_taken} HP</div>
                </div>
                <div className="bg-terminal-bg p-2 rounded border border-primary/20">
                  <div className="text-on-surface-variant text-[10px]">COLLECTIBLES</div>
                  <div className="text-cyan-400 font-bold">{playtestSummary.collectibles_gathered}</div>
                </div>
              </div>

              {/* AI Critique Panel */}
              {aiAnalysis && (
                <div className="bg-terminal-bg border border-primary/30 rounded p-3 flex flex-col gap-3 mt-1 animate-fadeIn">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-primary text-sm">smart_toy</span>
                      <span className="font-mono text-xs font-bold text-primary uppercase">
                        AI Game Design Critique
                      </span>
                    </div>
                    <div className="flex items-center gap-3 font-mono text-xs">
                      <span>Fun: <strong className="text-primary">{aiAnalysis.fun_rating}/10</strong></span>
                      <span>Difficulty: <strong className="text-amber-400">{aiAnalysis.difficulty_rating}/10</strong></span>
                      <span>Clarity: <strong className="text-cyan-400">{aiAnalysis.clarity_rating}/10</strong></span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
                    <div className="bg-surface/60 p-2.5 rounded border border-green-500/30">
                      <div className="text-green-400 font-bold mb-1 flex items-center gap-1">
                        <span className="material-symbols-outlined text-xs">thumb_up</span> STRENGTHS
                      </div>
                      <ul className="list-disc list-inside space-y-0.5 text-on-surface">
                        {aiAnalysis.strengths.map((s, idx) => (
                          <li key={idx}>{s}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="bg-surface/60 p-2.5 rounded border border-amber-500/30">
                      <div className="text-amber-400 font-bold mb-1 flex items-center gap-1">
                        <span className="material-symbols-outlined text-xs">warning</span> AREAS FOR IMPROVEMENT
                      </div>
                      <ul className="list-disc list-inside space-y-1 text-on-surface">
                        {aiAnalysis.problems.map((p, idx) => (
                          <li key={idx}>
                            {typeof p === 'string' ? (
                              p
                            ) : (
                              <span>
                                <strong className="text-amber-300">[{p.category?.toUpperCase()}]</strong> {p.diagnosis || p.evidence}{' '}
                                {p.evidence && p.diagnosis ? <span className="text-amber-200/80 text-[10px]">({p.evidence})</span> : null}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* Recommendations Selection */}
                  <div>
                    <div className="text-xs font-mono font-bold text-on-surface mb-1.5 flex items-center gap-1">
                      <span className="material-symbols-outlined text-xs text-primary">auto_fix_high</span>
                      RECOMMENDED DSL PATCHES (Select to apply):
                    </div>
                    <div className="space-y-1.5">
                      {aiAnalysis.recommendations.map((rec) => (
                        <label
                          key={rec.id}
                          className={`flex items-start gap-2 p-2 rounded border cursor-pointer font-mono text-xs transition-colors ${
                            selectedRecIds.includes(rec.id)
                              ? 'bg-primary/15 border-primary text-on-surface'
                              : 'bg-surface/40 border-primary/20 text-on-surface-variant hover:bg-surface/80'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedRecIds.includes(rec.id)}
                            onChange={() => toggleRecommendation(rec.id)}
                            className="mt-0.5 accent-primary"
                          />
                          <div className="flex-1">
                            <div>
                              <span className="font-bold text-primary mr-1.5">[{rec.category?.toUpperCase()}]</span>
                              <span>{rec.description}</span>
                            </div>
                            {rec.evidence && (
                              <div className="text-[10px] text-primary/70 mt-0.5">Observed: {rec.evidence}</div>
                            )}
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Apply Improvement Button */}
                  <div className="flex justify-end pt-1">
                    <button
                      onClick={handleApplyImprovements}
                      disabled={isApplyingImprovement || selectedRecIds.length === 0}
                      className="px-5 py-2 text-xs font-mono font-bold rounded bg-primary text-surface hover:bg-primary/90 transition-colors flex items-center gap-2 cursor-pointer shadow-[0_0_20px_rgba(76,224,210,0.4)] disabled:opacity-50"
                    >
                      <span className="material-symbols-outlined text-sm">build_circle</span>
                      <span>
                        {isApplyingImprovement ? 'APPLYING DSL PATCH...' : `APPLY IMPROVEMENTS → VERSION ${currentVersion + 1}`}
                      </span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};
