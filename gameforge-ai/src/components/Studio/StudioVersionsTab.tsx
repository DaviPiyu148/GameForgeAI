import React, { useEffect, useState, useCallback } from 'react';
import type { GameProject, ProjectVersionSummary } from '../../types';
import { projectService } from '../../services/projects';
import { ApiError } from '../../services/api';
import { useAppContext } from '../../context/AppContext';

interface StudioVersionsTabProps {
  project: GameProject;
  onPlayVersion: (version: ProjectVersionSummary) => void;
  onProjectUpdated: (updated: GameProject) => void;
}

export const StudioVersionsTab: React.FC<StudioVersionsTabProps> = ({
  project,
  onPlayVersion,
  onProjectUpdated,
}) => {
  const { refreshProgress } = useAppContext();
  const [versions, setVersions] = useState<ProjectVersionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [restoringVersionNumber, setRestoringVersionNumber] = useState<number | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [restoreSuccess, setRestoreSuccess] = useState<string | null>(null);
  const [expandedDiffVersion, setExpandedDiffVersion] = useState<number | null>(null);

  const fetchVersions = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await projectService.getVersions(project.id);
      // Sort reverse chronological: highest version number first
      data.sort((a, b) => b.version_number - a.version_number);
      setVersions(data);
    } catch (err) {
      console.warn('Could not fetch versions in StudioVersionsTab:', err);
    } finally {
      setIsLoading(false);
    }
  }, [project.id]);

  useEffect(() => {
    fetchVersions();
  }, [fetchVersions, project.currentVersion]);

  const handleRestore = async (version: ProjectVersionSummary) => {
    const nextVer = (project.currentVersion || 1) + 1;
    const confirmed = window.confirm(
      `Restore Version ${version.version_number} as new Version ${nextVer}?\n\nThis will promote v${version.version_number}'s design rules into a new immutable version without modifying history.`
    );
    if (!confirmed) return;

    setRestoringVersionNumber(version.version_number);
    setRestoreError(null);
    setRestoreSuccess(null);

    try {
      const restored = await projectService.restoreVersion(project.id, version.version_number);
      setRestoreSuccess(`Version ${version.version_number} successfully restored as v${restored.currentVersion}!`);
      onProjectUpdated(restored);
      await refreshProgress();
      await fetchVersions();
    } catch (err) {
      setRestoreError(err instanceof ApiError ? err.message : 'Failed to restore version.');
    } finally {
      setRestoringVersionNumber(null);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center font-mono text-xs text-primary space-y-2">
        <span className="material-symbols-outlined animate-spin text-xl text-secondary">sync</span>
        <div>LOADING REVISION TIMELINE...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 font-mono text-sm">
      <div className="flex justify-between items-center flex-wrap gap-2 pb-2 border-b border-outline-variant/30">
        <div className="text-xs text-secondary font-bold uppercase tracking-wider">
          Immutable Revision History ({versions.length} {versions.length === 1 ? 'Version' : 'Versions'})
        </div>
        <div className="text-[11px] text-on-surface-variant">
          Current Active: <span className="text-primary font-bold">v{project.currentVersion}</span>
        </div>
      </div>

      {restoreSuccess && (
        <div className="p-3 rounded bg-green-500/10 border border-green-500/40 text-green-400 text-xs flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">check_circle</span>
          <span>{restoreSuccess}</span>
        </div>
      )}

      {restoreError && (
        <div className="p-3 rounded bg-red-500/10 border border-red-500/40 text-red-400 text-xs flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">error</span>
          <span>{restoreError}</span>
        </div>
      )}

      {/* Timeline List */}
      <div className="space-y-3">
        {versions.map((ver) => {
          const isCurrent = ver.version_number === project.currentVersion;
          const isRestoringThis = restoringVersionNumber === ver.version_number;

          return (
            <div
              key={ver.id || ver.version_number}
              className={`p-4 rounded border transition-all ${
                isCurrent
                  ? 'bg-surface-container-low border-primary/50 shadow-[0_0_15px_rgba(76,224,210,0.1)]'
                  : 'bg-surface-container-lowest border-outline-variant/40 hover:border-outline-variant'
              }`}
            >
              <div className="flex justify-between items-start flex-wrap gap-2">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-on-surface">
                      Version {ver.version_number}
                    </span>
                    {isCurrent && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-primary/20 text-primary border border-primary/40 font-bold uppercase">
                        Current Active
                      </span>
                    )}
                    {ver.remix_intent && ver.remix_intent.length > 0 && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-secondary/20 text-secondary border border-secondary/40 font-bold uppercase flex items-center gap-1">
                        <span className="material-symbols-outlined text-[10px]">shuffle</span>
                        <span>Remix</span>
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-on-surface-variant font-sans">
                    {ver.change_summary || (ver.version_number === 1 ? 'Initial prototype generated from prompt.' : 'Revision update.')}
                  </div>
                </div>

                <div className="text-[10px] text-outline text-right">
                  {ver.created_at ? new Date(ver.created_at).toLocaleString() : ''}
                </div>
              </div>

              {/* Remix Intents badges */}
              {ver.remix_intent && ver.remix_intent.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-1.5 pt-2 border-t border-outline-variant/20">
                  <span className="text-[10px] text-on-surface-variant">Remix Intents:</span>
                  {ver.remix_intent.map((intent, i) => (
                    <span
                      key={i}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-surface border border-outline-variant text-on-surface uppercase"
                    >
                      {intent.type.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}

              {/* Action Buttons */}
              <div className="mt-3 pt-2.5 border-t border-outline-variant/20 flex justify-between items-center flex-wrap gap-2">
                <button
                  onClick={() =>
                    setExpandedDiffVersion(
                      expandedDiffVersion === ver.version_number ? null : ver.version_number
                    )
                  }
                  className="text-[11px] text-on-surface-variant hover:text-primary transition-colors flex items-center gap-1 cursor-pointer"
                >
                  <span className="material-symbols-outlined text-xs">
                    {expandedDiffVersion === ver.version_number ? 'expand_less' : 'expand_more'}
                  </span>
                  <span>{expandedDiffVersion === ver.version_number ? 'Hide Specs' : 'View Specs & Rules'}</span>
                </button>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onPlayVersion(ver)}
                    className={`px-3 py-1 text-xs font-bold rounded flex items-center gap-1.5 cursor-pointer transition-all ${
                      isCurrent
                        ? 'bg-primary text-surface hover:bg-primary/90 shadow-[0_0_10px_rgba(76,224,210,0.3)]'
                        : 'bg-surface border border-primary/40 text-primary hover:bg-primary/10'
                    }`}
                  >
                    <span className="material-symbols-outlined text-xs">play_arrow</span>
                    <span>{isCurrent ? 'PLAY CURRENT' : `PLAY v${ver.version_number} (READ-ONLY)`}</span>
                  </button>

                  {!isCurrent && (
                    <button
                      onClick={() => handleRestore(ver)}
                      disabled={isRestoringThis}
                      className="px-3 py-1 text-xs font-bold rounded bg-surface border border-outline-variant hover:border-secondary text-secondary hover:bg-secondary/10 transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                    >
                      <span className="material-symbols-outlined text-xs">restore</span>
                      <span>{isRestoringThis ? 'RESTORING...' : `RESTORE AS v${(project.currentVersion || 1) + 1}`}</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Specs Drawer */}
              {expandedDiffVersion === ver.version_number && ver.game_dsl && (
                <div className="mt-3 p-3 bg-terminal-bg rounded border border-outline-variant/30 text-xs space-y-2 animate-fadeIn">
                  <div className="text-[10px] text-secondary font-bold uppercase">Configuration Snapshot:</div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                    <div>
                      <span className="text-outline">Archetype:</span>{' '}
                      <span className="text-on-surface font-bold uppercase">{ver.game_dsl.metadata?.archetype || 'standard'}</span>
                    </div>
                    <div>
                      <span className="text-outline">Player Speed:</span>{' '}
                      <span className="text-primary font-bold">{ver.game_dsl.player?.speed ?? 250}</span>
                    </div>
                    <div>
                      <span className="text-outline">Max Health:</span>{' '}
                      <span className="text-red-400 font-bold">{ver.game_dsl.player?.max_health ?? 100}</span>
                    </div>
                    <div>
                      <span className="text-outline">Entities:</span>{' '}
                      <span className="text-cyan-400 font-bold">{ver.game_dsl.entities?.length ?? 0}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
