import React, { useEffect, useState, useCallback } from 'react';
import type { GameProject, PlaytestSessionRecord, ProjectVersionSummary } from '../../types';
import type { PlaytestAnalysis } from '../../runtime/types';
import { projectService } from '../../services/projects';
import { ApiError } from '../../services/api';
import { useAppContext } from '../../context/AppContext';

interface StudioPlaytestsTabProps {
  project: GameProject;
  onPlayNewSession: () => void;
  onProjectUpdated: (updated: GameProject) => void;
}

export const StudioPlaytestsTab: React.FC<StudioPlaytestsTabProps> = ({
  project,
  onPlayNewSession,
  onProjectUpdated,
}) => {
  const { refreshProgress } = useAppContext();
  const [playtests, setPlaytests] = useState<PlaytestSessionRecord[]>([]);
  const [versions, setVersions] = useState<ProjectVersionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isApplyingPatches, setIsApplyingPatches] = useState(false);
  const [selectedPatches, setSelectedPatches] = useState<number[]>([]);
  const [activeAnalysis, setActiveAnalysis] = useState<PlaytestAnalysis | null>(null);
  const [patchSuccessMessage, setPatchSuccessMessage] = useState<string | null>(null);
  const [patchErrorMessage, setPatchErrorMessage] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [ptData, verData] = await Promise.all([
        projectService.getPlaytests(project.id),
        projectService.getVersions(project.id).catch(() => [] as ProjectVersionSummary[]),
      ]);
      setPlaytests(ptData);
      setVersions(verData);
      if (ptData.length > 0 && ptData[0].ai_analysis) {
        setActiveAnalysis(ptData[0].ai_analysis);
        if (ptData[0].ai_analysis.recommendations) {
          setSelectedPatches(ptData[0].ai_analysis.recommendations.map((_, i) => i));
        }
      }
    } catch (err) {
      console.warn('Could not fetch playtests in StudioPlaytestsTab:', err);
    } finally {
      setIsLoading(false);
    }
  }, [project.id]);

  useEffect(() => {
    fetchData();
  }, [fetchData, project.currentVersion]);

  const latestSession = playtests.length > 0 ? playtests[0] : null;
  const currentVerNum = project.currentVersion || 1;
  const currentVersionRecord = versions.find((v) => v.version_number === currentVerNum);

  // Version-Aware Stale Recommendation Guard:
  // Analysis is only marked stale if a new project version was created AFTER the playtest session.
  // Project metadata renames / edits do NOT invalidate playtest recommendations.
  const isAnalysisStale = Boolean(
    latestSession?.created_at &&
    currentVersionRecord?.created_at &&
    new Date(latestSession.created_at).getTime() < new Date(currentVersionRecord.created_at).getTime()
  );

  // Compute summary stats
  const totalRuns = playtests.length;
  const winCount = playtests.filter((p) => p.outcome.toUpperCase() === 'WON').length;
  const winRate = totalRuns > 0 ? Math.round((winCount / totalRuns) * 100) : 0;
  const highScore = playtests.length > 0 ? Math.max(...playtests.map((p) => p.score)) : 0;

  const [showPatchPreview, setShowPatchPreview] = useState(false);

  const handleAnalyzeLatest = async () => {
    if (!latestSession) return;
    setIsAnalyzing(true);
    setPatchErrorMessage(null);
    try {
      const res = await projectService.analyzePlaytest(project.id, latestSession.id);
      setActiveAnalysis(res);
      if (res.recommendations) {
        // Automatically select actionable recommendations by default
        const actionableIndices = res.recommendations
          .map((r, i) => (r.suggested_patch && Object.keys(r.suggested_patch).length > 0 ? i : -1))
          .filter((i) => i >= 0);
        setSelectedPatches(actionableIndices);
      }
      await refreshProgress();
      await fetchData();
    } catch (err) {
      setPatchErrorMessage(err instanceof ApiError ? err.message : 'Analysis failed. Please try again.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleApplySelectedPatches = async () => {
    if (!activeAnalysis || isAnalysisStale) return;
    setIsApplyingPatches(true);
    setPatchErrorMessage(null);
    setPatchSuccessMessage(null);

    const chosenRecs = selectedPatches
      .map((idx) => activeAnalysis.recommendations[idx])
      .filter((r) => Boolean(r && r.suggested_patch && Object.keys(r.suggested_patch).length > 0));

    try {
      const res = await projectService.applyImprovements(project.id, {
        recommendations: chosenRecs,
        sessionId: latestSession?.id,
        baseVersionNumber: project.currentVersion || 1,
      });

      setPatchSuccessMessage(`Patches applied successfully! Project updated to v${res.newVersionNumber}.`);
      setShowPatchPreview(false);
      onProjectUpdated({
        ...project,
        gameDsl: res.gameDsl,
        designSpec: res.designSpec ?? project.designSpec,
        currentVersion: res.newVersionNumber,
      });
      await refreshProgress();
      await fetchData();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setPatchErrorMessage('Stale analysis conflict: Project has advanced to a newer version. Please refresh and analyze a current playtest.');
      } else {
        setPatchErrorMessage(err instanceof ApiError ? err.message : 'Could not apply patches.');
      }
    } finally {
      setIsApplyingPatches(false);
    }
  };

  // Helper to compute preview diffs for selected recommendations
  const computeSelectedDiffs = () => {
    if (!activeAnalysis?.recommendations || !project.gameDsl) return [];
    const diffs: Array<{ field: string; current: string; proposed: string; desc: string }> = [];
    const chosenRecs = selectedPatches.map((idx) => activeAnalysis.recommendations[idx]).filter(Boolean);

    for (const rec of chosenRecs) {
      const patch = rec.suggested_patch;
      if (!patch || typeof patch !== 'object') continue;
      for (const [topKey, topVal] of Object.entries(patch)) {
        if (topVal && typeof topVal === 'object' && !Array.isArray(topVal)) {
          for (const [subKey, subVal] of Object.entries(topVal)) {
            const curVal = (project.gameDsl as any)?.[topKey]?.[subKey];
            diffs.push({
              field: `${topKey}.${subKey}`,
              current: curVal !== undefined ? JSON.stringify(curVal) : '(undefined)',
              proposed: JSON.stringify(subVal),
              desc: rec.description,
            });
          }
        } else {
          const curVal = (project.gameDsl as any)?.[topKey];
          diffs.push({
            field: topKey,
            current: curVal !== undefined ? JSON.stringify(curVal) : '(undefined)',
            proposed: JSON.stringify(topVal),
            desc: rec.description,
          });
        }
      }
    }
    return diffs;
  };

  const selectedDiffs = computeSelectedDiffs();

  if (isLoading) {
    return (
      <div className="p-8 text-center font-mono text-xs text-primary space-y-2">
        <span className="material-symbols-outlined animate-spin text-xl text-secondary">sync</span>
        <div>LOADING PLAYTEST TELEMETRY...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 font-mono text-sm">
      {/* Metrics Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-surface-container-low border border-primary/30 p-3 rounded">
          <div className="text-on-surface-variant text-[10px] uppercase">Total Sessions</div>
          <div className="text-xl font-bold text-primary">{totalRuns}</div>
        </div>
        <div className="bg-surface-container-low border border-primary/30 p-3 rounded">
          <div className="text-on-surface-variant text-[10px] uppercase">Win Rate</div>
          <div className="text-xl font-bold text-green-400">{winRate}%</div>
        </div>
        <div className="bg-surface-container-low border border-primary/30 p-3 rounded">
          <div className="text-on-surface-variant text-[10px] uppercase">High Score</div>
          <div className="text-xl font-bold text-amber-400">{highScore}</div>
        </div>
        <div className="bg-surface-container-low border border-primary/30 p-3 rounded flex flex-col justify-center">
          <button
            onClick={onPlayNewSession}
            className="w-full py-1.5 px-2 bg-primary text-surface font-bold text-xs rounded hover:bg-primary/90 transition-all flex items-center justify-center gap-1.5 cursor-pointer shadow-[0_0_15px_rgba(76,224,210,0.3)]"
          >
            <span className="material-symbols-outlined text-sm">sports_esports</span>
            <span>NEW PLAYTEST</span>
          </button>
        </div>
      </div>

      {/* Empty State */}
      {playtests.length === 0 ? (
        <div className="bg-surface-container-low border border-outline-variant/50 p-6 rounded text-center space-y-3">
          <span className="material-symbols-outlined text-3xl text-outline">sports_esports</span>
          <div className="text-xs text-on-surface-variant">No playtest sessions recorded for this game yet.</div>
          <p className="text-[11px] text-outline max-w-md mx-auto font-sans">
            Playtesting records telemetry (score, survivability, enemies defeated) and unlocks AI qualitative design critique with 1-click balance patches.
          </p>
          <button
            onClick={onPlayNewSession}
            className="px-4 py-2 bg-primary text-surface font-bold text-xs rounded hover:bg-primary/90 transition-all cursor-pointer shadow-[0_0_20px_rgba(76,224,210,0.4)]"
          >
            START FIRST PLAYTEST SESSION
          </button>
        </div>
      ) : (
        <>
          {/* Latest Session & AI Critique Hub */}
          <div className="bg-surface-container-low border border-primary/30 p-4 rounded space-y-4">
            <div className="flex justify-between items-center flex-wrap gap-2 pb-3 border-b border-outline-variant/30">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-amber-400 text-sm">analytics</span>
                <span className="text-xs font-bold text-on-surface uppercase">Latest Playtest Session</span>
                <span
                  className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase border ${
                    latestSession?.outcome.toUpperCase() === 'WON'
                      ? 'bg-green-500/20 text-green-400 border-green-500/40'
                      : 'bg-red-500/20 text-red-400 border-red-500/40'
                  }`}
                >
                  {latestSession?.outcome}
                </span>
              </div>
              <span className="text-[10px] text-outline">
                {latestSession?.created_at ? new Date(latestSession.created_at).toLocaleString() : ''}
              </span>
            </div>

            {/* Metrics Breakdown */}
            {latestSession && (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                <div className="bg-surface p-2 rounded border border-outline-variant/30">
                  <div className="text-on-surface-variant text-[10px]">DURATION</div>
                  <div className="text-white font-bold">{latestSession.duration_seconds}s</div>
                </div>
                <div className="bg-surface p-2 rounded border border-outline-variant/30">
                  <div className="text-on-surface-variant text-[10px]">SCORE</div>
                  <div className="text-amber-400 font-bold">{latestSession.score}</div>
                </div>
                <div className="bg-surface p-2 rounded border border-outline-variant/30">
                  <div className="text-on-surface-variant text-[10px]">ENEMIES DEFEATED</div>
                  <div className="text-primary font-bold">{latestSession.enemies_defeated}</div>
                </div>
                <div className="bg-surface p-2 rounded border border-outline-variant/30">
                  <div className="text-on-surface-variant text-[10px]">DAMAGE TAKEN</div>
                  <div className="text-red-400 font-bold">{latestSession.damage_taken} HP</div>
                </div>
                <div className="bg-surface p-2 rounded border border-outline-variant/30">
                  <div className="text-on-surface-variant text-[10px]">COLLECTIBLES</div>
                  <div className="text-cyan-400 font-bold">{latestSession.collectibles_gathered}</div>
                </div>
              </div>
            )}

            {/* AI Analysis Deck */}
            {activeAnalysis ? (
              <div className="bg-terminal-bg border border-primary/40 rounded p-4 space-y-4">
                <div className="flex justify-between items-center flex-wrap gap-2">
                  <div className="flex items-center gap-2 text-primary font-bold text-xs uppercase">
                    <span className="material-symbols-outlined text-sm">psychology</span>
                    <span>AI Qualitative Game Critique</span>
                  </div>
                  <div className="flex gap-2 text-[10px]">
                    <span className="bg-surface px-2 py-0.5 rounded border border-outline-variant text-secondary">
                      FUN: {activeAnalysis.fun_rating}/10
                    </span>
                    <span className="bg-surface px-2 py-0.5 rounded border border-outline-variant text-amber-400">
                      DIFF: {activeAnalysis.difficulty_rating}/10
                    </span>
                    <span className="bg-surface px-2 py-0.5 rounded border border-outline-variant text-cyan-400">
                      CLARITY: {activeAnalysis.clarity_rating}/10
                    </span>
                  </div>
                </div>

                {/* Stale Warning Alert */}
                {isAnalysisStale && (
                  <div className="p-2.5 rounded bg-amber-500/10 border border-amber-500/40 text-amber-400 text-xs flex items-start gap-2">
                    <span className="material-symbols-outlined text-sm mt-0.5">warning</span>
                    <div>
                      <span className="font-bold">Recommendations are Stale:</span> This analysis was recorded for an earlier version of this game (prior to v{currentVerNum}). Play a new session to generate updated patches.
                    </div>
                  </div>
                )}

                {patchSuccessMessage && (
                  <div className="p-2.5 rounded bg-green-500/10 border border-green-500/40 text-green-400 text-xs flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">check_circle</span>
                    <span>{patchSuccessMessage}</span>
                  </div>
                )}

                {patchErrorMessage && (
                  <div className="p-2.5 rounded bg-red-500/10 border border-red-500/40 text-red-400 text-xs flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">error</span>
                    <span>{patchErrorMessage}</span>
                  </div>
                )}

                {/* Strengths & Problems */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="bg-surface/60 p-3 rounded border border-green-500/20 space-y-1">
                    <div className="text-green-400 font-bold text-[10px] uppercase flex items-center gap-1">
                      <span className="material-symbols-outlined text-xs">thumb_up</span>
                      <span>Strengths</span>
                    </div>
                    <ul className="space-y-1 text-on-surface/80 text-[11px] font-sans">
                      {activeAnalysis.strengths?.map((s, i) => (
                        <li key={i}>• {s}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="bg-surface/60 p-3 rounded border border-red-500/20 space-y-1">
                    <div className="text-red-400 font-bold text-[10px] uppercase flex items-center gap-1">
                      <span className="material-symbols-outlined text-xs">report_problem</span>
                      <span>Friction Points</span>
                    </div>
                    <ul className="space-y-1 text-on-surface/80 text-[11px] font-sans">
                      {activeAnalysis.problems?.map((p, i) => (
                        <li key={i}>• {typeof p === 'string' ? p : p.diagnosis || p.evidence}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Recommendations & Patch Apply */}
                {activeAnalysis.recommendations && activeAnalysis.recommendations.length > 0 && (
                  <div className="space-y-3 pt-2 border-t border-outline-variant/20">
                    <div className="flex justify-between items-center">
                      <div className="text-[10px] text-secondary font-bold uppercase">
                        Recommended Gameplay Patches ({activeAnalysis.recommendations.length}):
                      </div>
                      {selectedDiffs.length > 0 && (
                        <button
                          type="button"
                          onClick={() => setShowPatchPreview(!showPatchPreview)}
                          className="text-[10px] text-primary hover:underline flex items-center gap-1 cursor-pointer"
                        >
                          <span className="material-symbols-outlined text-xs">
                            {showPatchPreview ? 'visibility_off' : 'visibility'}
                          </span>
                          <span>{showPatchPreview ? 'Hide Diff Preview' : `Preview Diff (${selectedDiffs.length} changes)`}</span>
                        </button>
                      )}
                    </div>

                    {/* Diff Preview Accordion */}
                    {showPatchPreview && selectedDiffs.length > 0 && (
                      <div className="bg-surface/80 border border-primary/30 p-3 rounded space-y-2 text-xs font-mono">
                        <div className="text-[10px] text-primary font-bold uppercase">Proposed DSL Modifications:</div>
                        <div className="divide-y divide-outline-variant/20 max-h-48 overflow-y-auto">
                          {selectedDiffs.map((d, i) => (
                            <div key={i} className="py-1.5 flex flex-col gap-0.5">
                              <div className="flex justify-between items-center text-[11px]">
                                <span className="text-secondary font-bold">{d.field}</span>
                                <span className="text-[9px] text-outline truncate max-w-[200px]">{d.desc}</span>
                              </div>
                              <div className="flex items-center gap-2 text-[10px]">
                                <span className="text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">
                                  Current: {d.current}
                                </span>
                                <span className="material-symbols-outlined text-xs text-outline">arrow_forward</span>
                                <span className="text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded font-bold">
                                  Proposed: {d.proposed}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="space-y-1.5">
                      {activeAnalysis.recommendations.map((rec, idx) => {
                        const isActionable = Boolean(rec.suggested_patch && Object.keys(rec.suggested_patch).length > 0);
                        const isSelected = selectedPatches.includes(idx);

                        return (
                          <div
                            key={idx}
                            className={`flex items-start gap-2.5 p-2.5 rounded text-xs border transition-colors ${
                              !isActionable
                                ? 'bg-surface/30 border-outline-variant/20 opacity-80'
                                : isSelected
                                ? 'bg-primary/10 border-primary/40 text-on-surface'
                                : 'bg-surface/40 border-outline-variant/30 text-outline hover:text-on-surface'
                            }`}
                          >
                            {isActionable ? (
                              <input
                                type="checkbox"
                                disabled={isAnalysisStale}
                                checked={isSelected}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedPatches((prev) => [...prev, idx]);
                                  } else {
                                    setSelectedPatches((prev) => prev.filter((i) => i !== idx));
                                  }
                                }}
                                className="mt-0.5 cursor-pointer"
                              />
                            ) : (
                              <span className="material-symbols-outlined text-xs text-outline mt-0.5" title="Informational critique (no direct parameter patch)">
                                info
                              </span>
                            )}
                            <div className="space-y-1 flex-1">
                              <div className="flex items-center justify-between gap-2">
                                <div className="font-bold font-sans text-xs">{rec.description}</div>
                                <span
                                  className={`text-[9px] px-1.5 py-0.2 rounded uppercase font-mono font-bold ${
                                    isActionable
                                      ? 'bg-primary/20 text-primary border border-primary/40'
                                      : 'bg-outline-variant/30 text-outline'
                                  }`}
                                >
                                  {isActionable ? 'ACTIONABLE PATCH' : 'INFORMATIONAL'}
                                </span>
                              </div>
                              <div className="text-[10px] text-outline font-mono">
                                Target: {rec.dsl_change_type} {rec.evidence ? `• Evidence: ${rec.evidence}` : ''}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    <div className="pt-2 flex justify-between items-center flex-wrap gap-2">
                      <div className="text-[10px] text-outline">
                        {isAnalysisStale ? (
                          <span className="text-amber-400 font-bold">Stale: Play new session to enable patching</span>
                        ) : (
                          <span>{selectedPatches.length} of {activeAnalysis.recommendations.filter(r => r.suggested_patch && Object.keys(r.suggested_patch).length > 0).length} actionable patches selected</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {patchSuccessMessage && (
                          <button
                            type="button"
                            onClick={onPlayNewSession}
                            className="px-3 py-1.5 bg-secondary text-surface font-bold text-xs rounded hover:bg-secondary/90 transition-all flex items-center gap-1.5 cursor-pointer shadow-[0_0_15px_rgba(202,189,255,0.4)]"
                          >
                            <span className="material-symbols-outlined text-sm">play_arrow</span>
                            <span>PLAY PROTOTYPE v{project.currentVersion || 1}</span>
                          </button>
                        )}
                        <button
                          onClick={handleApplySelectedPatches}
                          disabled={isApplyingPatches || selectedPatches.length === 0 || isAnalysisStale}
                          className="px-4 py-2 bg-primary text-surface font-bold text-xs rounded hover:bg-primary/90 transition-all flex items-center gap-2 cursor-pointer shadow-[0_0_20px_rgba(76,224,210,0.4)] disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          <span className="material-symbols-outlined text-sm">build</span>
                          <span>
                            {isApplyingPatches
                              ? 'APPLYING PATCHES...'
                              : `APPLY ${selectedPatches.length} PATCHES → v${(project.currentVersion || 1) + 1}`}
                          </span>
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-3 bg-surface rounded border border-outline-variant/30 flex justify-between items-center flex-wrap gap-2">
                <div className="text-xs text-on-surface-variant">
                  This playtest session has not been analyzed by AI yet.
                </div>
                <button
                  onClick={handleAnalyzeLatest}
                  disabled={isAnalyzing}
                  className="px-3.5 py-1.5 bg-primary text-surface font-bold text-xs rounded hover:bg-primary/90 transition-all flex items-center gap-1.5 cursor-pointer shadow-[0_0_15px_rgba(76,224,210,0.3)] ai-pulse disabled:opacity-50"
                >
                  <span className="material-symbols-outlined text-sm">psychology</span>
                  <span>{isAnalyzing ? 'ANALYZING...' : 'ANALYZE WITH AI'}</span>
                </button>
              </div>
            )}
          </div>

          {/* Historical Playtest Sessions Table */}
          {playtests.length > 1 && (
            <div className="space-y-2">
              <div className="text-xs text-secondary font-bold uppercase tracking-wider">Session History ({playtests.length})</div>
              <div className="bg-surface-container-low border border-outline-variant/30 rounded overflow-hidden">
                <table className="w-full text-xs text-left">
                  <thead className="bg-surface-container-highest text-on-surface-variant text-[10px] uppercase border-b border-outline-variant/30">
                    <tr>
                      <th className="p-2.5">Date</th>
                      <th className="p-2.5">Outcome</th>
                      <th className="p-2.5">Score</th>
                      <th className="p-2.5">Duration</th>
                      <th className="p-2.5">Enemies</th>
                      <th className="p-2.5">Damage</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/20">
                    {playtests.map((pt) => (
                      <tr key={pt.id} className="hover:bg-surface/50 transition-colors">
                        <td className="p-2.5 text-[11px] text-on-surface-variant">
                          {new Date(pt.created_at).toLocaleString()}
                        </td>
                        <td className="p-2.5">
                          <span
                            className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                              pt.outcome.toUpperCase() === 'WON'
                                ? 'bg-green-500/20 text-green-400'
                                : 'bg-red-500/20 text-red-400'
                            }`}
                          >
                            {pt.outcome}
                          </span>
                        </td>
                        <td className="p-2.5 font-bold text-amber-400">{pt.score}</td>
                        <td className="p-2.5">{pt.duration_seconds}s</td>
                        <td className="p-2.5 text-primary">{pt.enemies_defeated}</td>
                        <td className="p-2.5 text-red-400">{pt.damage_taken} HP</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
