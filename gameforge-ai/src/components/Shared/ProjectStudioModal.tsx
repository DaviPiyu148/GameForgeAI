import React, { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import type { GameProject, ProjectVersionSummary } from '../../types';
import { useModalDialog } from '../../hooks/useModalDialog';
import { useAppContext } from '../../context/AppContext';
import { buildDiscoverySeed } from '../../utils/discovery';
import { StudioOverviewTab } from '../Studio/StudioOverviewTab';
import { StudioPlaytestsTab } from '../Studio/StudioPlaytestsTab';
import { StudioVersionsTab } from '../Studio/StudioVersionsTab';

export type StudioTabId = 'overview' | 'playtests' | 'versions';

interface ProjectStudioModalProps {
  project: GameProject;
  initialTab?: StudioTabId;
  onClose: () => void;
  onPlayCurrent: () => void;
  onRemix: () => void;
  onEditInBuilder: () => void;
  onPlayHistoricalVersion: (version: ProjectVersionSummary) => void;
  onProjectUpdated: (updated: GameProject) => void;
}

export const ProjectStudioModal: React.FC<ProjectStudioModalProps> = ({
  project,
  initialTab = 'overview',
  onClose,
  onPlayCurrent,
  onRemix,
  onEditInBuilder,
  onPlayHistoricalVersion,
  onProjectUpdated,
}) => {
  const navigate = useNavigate();
  const { searchDiscovery } = useAppContext();
  const [activeTab, setActiveTab] = useState<StudioTabId>(initialTab);
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  const { isClosing, handleClose, handleBackdropClick, dialogRef } = useModalDialog({
    isOpen: true,
    onClose,
    initialFocusRef: closeBtnRef,
    closeDelayMs: 200,
  });

  const handleDiscoverSimilar = () => {
    const seed = buildDiscoverySeed(project);
    handleClose();
    searchDiscovery(seed, navigate, 'BEST_MATCH');
  };

  return createPortal(
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-background/90 backdrop-blur-sm ${
        isClosing ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
      }`}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label={`Project Studio for ${project.title}`}
    >
      <div
        ref={dialogRef}
        className={`w-full max-w-4xl max-h-[92vh] overflow-y-auto bg-surface border-2 border-primary/50 rounded-lg flex flex-col shadow-[0_0_40px_rgba(76,224,210,0.2)] ${
          isClosing ? 'modal-exit' : 'modal-enter'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Terminal Header */}
        <div className="bg-terminal-header border-b border-primary/30 p-3 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-2.5 text-primary">
            <span className="material-symbols-outlined text-lg animate-pulse" aria-hidden="true">
              developer_board
            </span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm tracking-widest font-bold uppercase">
                PROJECT STUDIO // {project.title}
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary/20 text-primary border border-primary/40 uppercase font-bold">
                v{project.currentVersion || 1}
              </span>
            </div>
          </div>
          <button
            ref={closeBtnRef}
            onClick={handleClose}
            className="text-on-surface-variant icon-interactive hover:text-primary transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center focus:outline-none focus:ring-1 focus:ring-primary rounded cursor-pointer"
            aria-label="Close Project Studio"
          >
            <span className="material-symbols-outlined" aria-hidden="true">close</span>
          </button>
        </div>

        {/* Studio Command Bar */}
        <div className="bg-surface-container-low border-b border-outline-variant/40 p-3 sm:p-4 flex flex-wrap justify-between items-center gap-3 shrink-0">
          <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
            <span className="text-secondary font-bold uppercase">{project.genre}</span>
            <span className="text-outline">•</span>
            <span className="text-on-surface-variant">
              Status: <span className="text-primary font-bold">{project.status}</span>
            </span>
            <span className="text-outline">•</span>
            <span className="text-on-surface-variant text-[11px]">
              Modified: {project.lastModified || 'Recent'}
            </span>
          </div>

          {/* Top-Level Quick Actions */}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={onPlayCurrent}
              className="px-3.5 py-1.5 bg-primary text-surface font-mono font-bold text-xs rounded hover:bg-primary/90 transition-all flex items-center gap-1.5 cursor-pointer shadow-[0_0_15px_rgba(76,224,210,0.4)]"
            >
              <span className="material-symbols-outlined text-sm">play_arrow</span>
              <span>PLAY PROTOTYPE</span>
            </button>

            <button
              onClick={onRemix}
              className="px-3 py-1.5 bg-surface border border-secondary text-secondary font-mono font-bold text-xs rounded hover:bg-secondary/10 transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <span className="material-symbols-outlined text-sm">shuffle</span>
              <span>REMIX</span>
            </button>

            <button
              onClick={onEditInBuilder}
              className="px-3 py-1.5 bg-surface border border-outline-variant hover:border-primary text-on-surface hover:text-primary font-mono font-bold text-xs rounded transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <span className="material-symbols-outlined text-sm">edit</span>
              <span>EDIT IN BUILDER</span>
            </button>

            <button
              onClick={handleDiscoverSimilar}
              className="px-3 py-1.5 bg-surface border border-outline-variant hover:border-cyan-400 text-on-surface-variant hover:text-cyan-400 font-mono text-xs rounded transition-colors flex items-center gap-1.5 cursor-pointer"
              title="Find similar games in Discovery catalog"
            >
              <span className="material-symbols-outlined text-sm">travel_explore</span>
              <span className="hidden sm:inline">DISCOVER SIMILAR</span>
            </button>
          </div>
        </div>

        {/* 3-Tab Bar */}
        <div className="bg-surface-container-highest border-b border-primary/20 px-4 flex gap-1 shrink-0 font-mono text-xs overflow-x-auto" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === 'overview'}
            onClick={() => setActiveTab('overview')}
            className={`py-2.5 px-4 font-bold border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'overview'
                ? 'border-primary text-primary bg-surface/50'
                : 'border-transparent text-on-surface-variant hover:text-on-surface'
            }`}
          >
            <span className="material-symbols-outlined text-sm">assignment</span>
            <span>OVERVIEW & BLUEPRINT</span>
          </button>

          <button
            role="tab"
            aria-selected={activeTab === 'playtests'}
            onClick={() => setActiveTab('playtests')}
            className={`py-2.5 px-4 font-bold border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'playtests'
                ? 'border-primary text-primary bg-surface/50'
                : 'border-transparent text-on-surface-variant hover:text-on-surface'
            }`}
          >
            <span className="material-symbols-outlined text-sm">sports_esports</span>
            <span>PLAYTEST & AI INSIGHTS</span>
          </button>

          <button
            role="tab"
            aria-selected={activeTab === 'versions'}
            onClick={() => setActiveTab('versions')}
            className={`py-2.5 px-4 font-bold border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'versions'
                ? 'border-primary text-primary bg-surface/50'
                : 'border-transparent text-on-surface-variant hover:text-on-surface'
            }`}
          >
            <span className="material-symbols-outlined text-sm">history</span>
            <span>VERSION HISTORY</span>
          </button>
        </div>

        {/* Tab Body */}
        <div className="p-4 sm:p-6 bg-terminal-bg flex-1">
          {activeTab === 'overview' && (
            <StudioOverviewTab
              project={project}
              onCloseStudio={handleClose}
              onPlayCurrent={onPlayCurrent}
              onProjectUpdated={onProjectUpdated}
            />
          )}
          {activeTab === 'playtests' && (
            <StudioPlaytestsTab
              project={project}
              onPlayNewSession={onPlayCurrent}
              onProjectUpdated={onProjectUpdated}
            />
          )}
          {activeTab === 'versions' && (
            <StudioVersionsTab
              project={project}
              onPlayVersion={(ver) => {
                if (ver.version_number === project.currentVersion) {
                  onPlayCurrent();
                } else {
                  onPlayHistoricalVersion(ver);
                }
              }}
              onProjectUpdated={onProjectUpdated}
            />
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};
